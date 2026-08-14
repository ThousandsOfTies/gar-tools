"""Hardware simulator bridge for C stubs and the browser control panel.

The bridge has one HTTP endpoint.  It serves the panel, its JSON API, and a
WebSocket at ``/ws``.  CUSE stubs communicate through a separate Unix socket.
GPIO assignments and available simulated devices come from
``GAR_HARDWARE_DIR`` CSV files when they are available.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import errno
import json
import logging
import os
import socket
import stat
import threading
from pathlib import Path
from typing import Mapping

from aiohttp import WSMsgType, web

from hardware_config import GpioLine, HardwareConfig, load_hardware_config
from request_validation import (
    RequestValidationError,
    boolean_value,
    bounded_int,
    browser_request_allowed,
    configured_line,
    parse_json_object,
    resolve_panel_file,
    rfid_uid,
)
from metrics import MetricsError, load_metrics


LOGGER = logging.getLogger("gar.hardware_bridge")

HTTP_HOST = os.environ.get("GAR_BRIDGE_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("GAR_BRIDGE_PORT", "8080"))
PANEL_DIR = Path(__file__).parent / "panel"
COMPONENTS_DIR = Path(__file__).parent / "components"
# Application artifacts select their screen by writing an absolute directory
# here.  Reading it for each request deliberately makes `gar sim app deploy`
# switch a screen without restarting the bridge or the simulated hardware.
PANEL_DIR_CONFIG = Path("/etc/gar/panel-dir")
METRICS_DIR = Path(os.environ.get("GAR_METRICS_DIR", "/run/gar/metrics"))


def _allowed_http_hosts() -> frozenset[str]:
    configured = os.environ.get("GAR_BRIDGE_ALLOWED_HOSTS")
    if configured:
        values = configured.split(",")
    else:
        values = ["127.0.0.1", "localhost", "::1"]
        if HTTP_HOST not in {"", "0.0.0.0", "::"}:
            values.append(HTTP_HOST)
    return frozenset(value.strip().casefold() for value in values if value.strip())


ALLOWED_HTTP_HOSTS = _allowed_http_hosts()

MAX_BROWSER_MESSAGE_BYTES = 64 * 1024
# A 2048x1536 JPEG from a real UVC camera can exceed 2 MiB for detailed scenes.
# Keep a finite per-frame limit, while allowing the native 3 MP GarStream camera
# mode to reach the simulator without an artificial downscale.
MAX_CAMERA_FRAME_BYTES = 8 * 1024 * 1024
MAX_STUB_LINE_BYTES = 2 * 1024 * 1024
MAX_PIXEL_DATA_CHARS = 1_500_000
MAX_BUTTON_PRESS_MS = 10_000
MAX_RANGE_MM = 4_000
MAX_STUB_CONNECTIONS = 16
MAX_PENDING_STUB_BROADCASTS = 64
FIRST_STUB_MESSAGE_TIMEOUT_SECONDS = 5.0
ROTARY_STEP_DELAY_SECONDS = 0.02
DEFAULT_RFID_UID = "04:AB:CD:EF:01:23"


def _runtime_socket_path() -> str:
    explicit = os.environ.get("GAR_HW_SIM_SOCK")
    if explicit:
        return explicit
    runtime_dir = os.environ.get("GAR_RUNTIME_DIR")
    if runtime_dir:
        return str(Path(runtime_dir) / "hw_sim.sock")
    return "/tmp/hw_sim.sock"


UNIX_SOCKET_PATH = _runtime_socket_path()
HARDWARE_CONFIG: HardwareConfig = load_hardware_config(
    os.environ.get("GAR_HARDWARE_DIR")
)
GPIO_BY_LINE = HARDWARE_CONFIG.gpio_by_line


state: dict[str, object] = {
    "hardware": HARDWARE_CONFIG.public_mapping(),
    "gpio": {
        "leds": {line: False for line in HARDWARE_CONFIG.led_lines},
        "buttons": {line: False for line in HARDWARE_CONFIG.button_lines},
        "rotary": {"counter": 0},
    },
    "i2c": {
        "vl53l0x": {"range_mm": 300, "status": 0x01},
        "ssd1306": {"framebuf": None},
    },
    "spi": {
        "mfrc522": {"uid": None, "present": False},
        "lcd": {"pixels": None},
        "ili9341": {"pixels": None, "width": 320, "height": 240},
    },
}

websocket_clients: set[web.WebSocketResponse] = set()
camera_input_lock = asyncio.Lock()
_button_press_tokens: dict[int, object] = {}
_rotary_lock = asyncio.Lock()
_stub_connection_slots = threading.BoundedSemaphore(MAX_STUB_CONNECTIONS)
_stub_broadcast_slots = threading.BoundedSemaphore(MAX_PENDING_STUB_BROADCASTS)


# ---------------------------------------------------------------------------
# gpio-sim sysfs synchronisation
# ---------------------------------------------------------------------------


def _gpio_sim_roots() -> tuple[Path, ...]:
    """Discover roots on demand because gpio-sim may appear after startup."""
    return tuple(Path("/sys/devices/platform").glob("gpio-sim.*/gpiochip*"))


def _gpio_sim_line_dir(line: int) -> Path | None:
    for root in _gpio_sim_roots():
        line_dir = root / f"sim_gpio{line}"
        if line_dir.exists():
            return line_dir
    return None


def _gpio_sim_value(line: int) -> bool | None:
    line_dir = _gpio_sim_line_dir(line)
    if line_dir is None:
        return None
    try:
        return (line_dir / "value").read_text(encoding="utf-8").strip() == "1"
    except OSError as exc:
        LOGGER.warning("gpio-sim read failed for line %s: %s", line, exc)
        return None


def _gpio_sim_set_level(line: int, high: bool) -> None:
    line_dir = _gpio_sim_line_dir(line)
    if line_dir is None:
        return
    try:
        pull = "pull-up\n" if high else "pull-down\n"
        (line_dir / "pull").write_text(pull, encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("gpio-sim input sync failed for line %s: %s", line, exc)


def _gpio_sim_set_button(line: int, pressed: bool) -> None:
    definition = GPIO_BY_LINE[line]
    electrical_high = definition.electrical_level_for(pressed)
    _gpio_sim_set_level(line, electrical_high)


async def poll_gpio_sim_outputs() -> None:
    gpio_state = state["gpio"]
    assert isinstance(gpio_state, dict)
    led_state = gpio_state["leds"]
    assert isinstance(led_state, dict)

    while True:
        for line in HARDWARE_CONFIG.led_lines:
            electrical_high = _gpio_sim_value(line)
            if electrical_high is None:
                continue
            definition = GPIO_BY_LINE[line]
            value = definition.active_at_level(electrical_high)
            if led_state.get(line) == value:
                continue
            led_state[line] = value
            await broadcast({"type": "led", "line": line, "value": value})
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Browser broadcast and virtual hardware actions
# ---------------------------------------------------------------------------


async def broadcast(message: dict[str, object]) -> None:
    if not websocket_clients:
        return

    encoded = json.dumps(message, separators=(",", ":"))
    clients = tuple(client for client in websocket_clients if not client.closed)
    results = await asyncio.gather(
        *(client.send_str(encoded) for client in clients),
        return_exceptions=True,
    )
    for client, result in zip(clients, results, strict=False):
        if isinstance(result, Exception):
            LOGGER.debug("dropping WebSocket client after send failure: %s", result)
            websocket_clients.discard(client)


async def _apply_button_state(line: int, pressed: bool) -> None:
    gpio_state = state["gpio"]
    assert isinstance(gpio_state, dict)
    buttons = gpio_state["buttons"]
    assert isinstance(buttons, dict)
    buttons[line] = pressed
    _gpio_sim_set_button(line, pressed)
    await broadcast({"type": "button", "line": line, "value": pressed})


async def set_button(line: int, pressed: bool) -> None:
    """Set a button and invalidate any delayed release from an older press."""
    _button_press_tokens.pop(line, None)
    await _apply_button_state(line, pressed)


async def press_button(line: int, duration_ms: int) -> None:
    """Press then release, without an older press releasing a newer one early."""
    token = object()
    _button_press_tokens[line] = token
    try:
        await _apply_button_state(line, True)
        await asyncio.sleep(duration_ms / 1000)
    finally:
        if _button_press_tokens.get(line) is token:
            _button_press_tokens.pop(line, None)
            await _apply_button_state(line, False)


async def tap_rfid(uid: str) -> None:
    spi_state = state["spi"]
    assert isinstance(spi_state, dict)
    spi_state["mfrc522"] = {"uid": uid, "present": True}
    await broadcast({"type": "rfid", "uid": uid, "present": True})


async def remove_rfid() -> None:
    spi_state = state["spi"]
    assert isinstance(spi_state, dict)
    spi_state["mfrc522"] = {"uid": None, "present": False}
    await broadcast({"type": "rfid", "uid": None, "present": False})


async def set_range(range_mm: int) -> None:
    i2c_state = state["i2c"]
    assert isinstance(i2c_state, dict)
    sensor = i2c_state["vl53l0x"]
    assert isinstance(sensor, dict)
    sensor["range_mm"] = range_mm
    await broadcast({"type": "range", "value": range_mm})


def _configured_rotary():
    rotary = HARDWARE_CONFIG.rotary
    if rotary is None:
        raise RequestValidationError("no rotary encoder is configured in gpio.csv")
    return rotary


def _require_device(driver: str) -> None:
    if driver not in HARDWARE_CONFIG.device_drivers:
        raise RequestValidationError(
            f"device driver {driver!r} is not configured in the hardware CSV files"
        )


async def rotary_step(direction: int) -> None:
    """Emulate one KY-040 detent using the configured A/B input lines."""
    rotary = _configured_rotary()
    async with _rotary_lock:
        if direction > 0:
            levels = (
                (rotary.clock, False),
                (rotary.data, False),
                (rotary.clock, True),
                (rotary.data, True),
            )
        else:
            levels = (
                (rotary.data, False),
                (rotary.clock, False),
                (rotary.data, True),
                (rotary.clock, True),
            )

        try:
            for index, (line, high) in enumerate(levels):
                _gpio_sim_set_level(line, high)
                if index < len(levels) - 1:
                    await asyncio.sleep(ROTARY_STEP_DELAY_SECONDS)
        finally:
            _gpio_sim_set_level(rotary.clock, True)
            _gpio_sim_set_level(rotary.data, True)

        gpio_state = state["gpio"]
        assert isinstance(gpio_state, dict)
        rotary_state = gpio_state["rotary"]
        assert isinstance(rotary_state, dict)
        counter = int(rotary_state["counter"]) + direction
        rotary_state["counter"] = counter
        await broadcast({"type": "rotary", "counter": counter})


async def rotary_press() -> None:
    """Pulse the active-low KY-040 switch while serialising rotary actions."""
    rotary = _configured_rotary()
    definition = GPIO_BY_LINE[rotary.switch]
    async with _rotary_lock:
        pressed_level = definition.electrical_level_for(True)
        try:
            _gpio_sim_set_level(rotary.switch, pressed_level)
            await broadcast({"type": "rotary_button", "value": True})
            await asyncio.sleep(0.15)
        finally:
            _gpio_sim_set_level(rotary.switch, not pressed_level)
            await broadcast({"type": "rotary_button", "value": False})


# ---------------------------------------------------------------------------
# Browser WebSocket and request validation
# ---------------------------------------------------------------------------


def _button_line(data: Mapping[str, object]) -> int:
    if not HARDWARE_CONFIG.button_lines:
        raise RequestValidationError("no push button is configured in gpio.csv")
    line = bounded_int(
        data,
        "line",
        default=HARDWARE_CONFIG.button_lines[0],
        minimum=0,
        maximum=4095,
    )
    return configured_line(line, HARDWARE_CONFIG.button_lines, "button input")


def _direction(data: Mapping[str, object]) -> int:
    direction = bounded_int(data, "direction", default=1, minimum=-1, maximum=1)
    if direction == 0:
        raise RequestValidationError("direction must be -1 or 1")
    return direction


async def _dispatch_browser_message(data: Mapping[str, object]) -> None:
    message_type = data.get("type")
    if not isinstance(message_type, str):
        raise RequestValidationError("type must be a string")

    if message_type == "button":
        await set_button(_button_line(data), boolean_value(data, "value"))
    elif message_type == "rfid_tap":
        _require_device("mfrc522")
        await tap_rfid(rfid_uid(data, DEFAULT_RFID_UID))
    elif message_type == "rfid_remove":
        _require_device("mfrc522")
        await remove_rfid()
    elif message_type == "range_set":
        _require_device("vl53l0x")
        range_mm = bounded_int(
            data, "value", default=300, minimum=0, maximum=MAX_RANGE_MM
        )
        await set_range(range_mm)
    elif message_type == "rotary_rotate":
        await rotary_step(_direction(data))
    elif message_type == "rotary_press":
        await rotary_press()
    else:
        raise RequestValidationError(f"unsupported message type: {message_type!r}")


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    websocket = web.WebSocketResponse(
        heartbeat=30,
        max_msg_size=MAX_BROWSER_MESSAGE_BYTES,
    )
    await websocket.prepare(request)
    websocket_clients.add(websocket)
    try:
        await websocket.send_json({"type": "init", "state": state})
        async for message in websocket:
            if message.type == WSMsgType.TEXT:
                try:
                    data = parse_json_object(message.data)
                    await _dispatch_browser_message(data)
                except RequestValidationError as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
            elif message.type == WSMsgType.ERROR:
                LOGGER.warning("WebSocket receive failed: %s", websocket.exception())
                break
    finally:
        websocket_clients.discard(websocket)
    return websocket


# ---------------------------------------------------------------------------
# Unix socket server for CUSE stubs
# ---------------------------------------------------------------------------


def _schedule_broadcast(
    message: dict[str, object], loop: asyncio.AbstractEventLoop
) -> None:
    if not _stub_broadcast_slots.acquire(blocking=False):
        LOGGER.debug("dropping stub broadcast because the pending queue is full")
        return

    coroutine = broadcast(message)
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    except BaseException:
        coroutine.close()
        _stub_broadcast_slots.release()
        raise

    def log_failure(completed) -> None:
        try:
            completed.result()
        except Exception as exc:  # the event loop owns the underlying exception
            LOGGER.warning("stub event broadcast failed: %s", exc)
        finally:
            _stub_broadcast_slots.release()

    future.add_done_callback(log_failure)


def _pixel_data(
    data: Mapping[str, object],
    field: str,
    *,
    expected_bytes: int,
) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestValidationError(f"{field} must be a base64 string or null")
    expected_characters = 4 * ((expected_bytes + 2) // 3)
    if expected_characters > MAX_PIXEL_DATA_CHARS:
        raise RequestValidationError(f"{field} dimensions exceed the transfer limit")
    if len(value) != expected_characters:
        raise RequestValidationError(
            f"{field} must contain {expected_characters} base64 characters, got {len(value)}"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RequestValidationError(f"{field} must be valid base64") from exc
    if len(decoded) != expected_bytes:
        raise RequestValidationError(
            f"{field} must decode to {expected_bytes} bytes, got {len(decoded)}"
        )
    return value


def handle_stub_message(raw: str, loop: asyncio.AbstractEventLoop) -> str | None:
    """Process one JSON line from a C stub and return an optional response."""
    expects_response = False
    try:
        message = parse_json_object(raw.strip())
        expects_response = "req" in message
        event = message.get("event")
        device = message.get("device")

        if expects_response and "event" in message:
            raise RequestValidationError("message cannot contain both req and event")

        if event == "set" and device == "gpio":
            line = bounded_int(message, "line", minimum=0, maximum=4095)
            configured_line(line, HARDWARE_CONFIG.output_lines, "GPIO output")
            value = boolean_value(message, "value")
            gpio_state = state["gpio"]
            assert isinstance(gpio_state, dict)
            leds = gpio_state["leds"]
            assert isinstance(leds, dict)
            if line in HARDWARE_CONFIG.led_lines:
                definition = GPIO_BY_LINE[line]
                active = definition.active_at_level(value)
                leds[line] = active
                _schedule_broadcast(
                    {"type": "led", "line": line, "value": active}, loop
                )

        elif event == "set" and device == "i2c_range":
            _require_device("vl53l0x")
            range_mm = bounded_int(
                message, "value", default=300, minimum=0, maximum=MAX_RANGE_MM
            )
            i2c_state = state["i2c"]
            assert isinstance(i2c_state, dict)
            sensor = i2c_state["vl53l0x"]
            assert isinstance(sensor, dict)
            sensor["range_mm"] = range_mm
            _schedule_broadcast({"type": "range", "value": range_mm}, loop)

        elif event == "set" and device == "lcd":
            _require_device("st7789")
            pixels = _pixel_data(message, "pixels", expected_bytes=240 * 240 * 2)
            spi_state = state["spi"]
            assert isinstance(spi_state, dict)
            lcd = spi_state["lcd"]
            assert isinstance(lcd, dict)
            lcd["pixels"] = pixels
            _schedule_broadcast({"type": "lcd", "pixels": pixels}, loop)

        elif event == "set" and device == "oled":
            _require_device("ssd1306")
            frame_buffer = _pixel_data(
                message, "framebuf", expected_bytes=128 * 64 // 8
            )
            i2c_state = state["i2c"]
            assert isinstance(i2c_state, dict)
            oled = i2c_state["ssd1306"]
            assert isinstance(oled, dict)
            oled["framebuf"] = frame_buffer
            _schedule_broadcast({"type": "oled", "framebuf": frame_buffer}, loop)

        elif event == "set" and device == "ili9341":
            _require_device("ili9341")
            width = bounded_int(message, "width", default=320, minimum=1, maximum=2048)
            height = bounded_int(
                message, "height", default=240, minimum=1, maximum=2048
            )
            pixels = _pixel_data(
                message,
                "pixels",
                expected_bytes=width * height * 2,
            )
            spi_state = state["spi"]
            assert isinstance(spi_state, dict)
            spi_state["ili9341"] = {
                "pixels": pixels,
                "width": width,
                "height": height,
            }
            _schedule_broadcast(
                {
                    "type": "ili9341",
                    "pixels": pixels,
                    "width": width,
                    "height": height,
                },
                loop,
            )

        elif message.get("req") == "get" and device == "gpio":
            line = bounded_int(message, "line", minimum=0, maximum=4095)
            configured_line(line, HARDWARE_CONFIG.input_lines, "GPIO input")
            gpio_state = state["gpio"]
            assert isinstance(gpio_state, dict)
            buttons = gpio_state["buttons"]
            assert isinstance(buttons, dict)
            electrical_high = _gpio_sim_value(line)
            if electrical_high is None and line in HARDWARE_CONFIG.button_lines:
                definition = GPIO_BY_LINE[line]
                pressed = bool(buttons.get(line))
                electrical_high = definition.electrical_level_for(pressed)
            if electrical_high is None:
                electrical_high = _initial_gpio_input_level(GPIO_BY_LINE[line])
            return json.dumps({"value": int(bool(electrical_high))}) + "\n"

        elif message.get("req") == "get" and device == "gpio_out":
            line = bounded_int(message, "line", minimum=0, maximum=4095)
            configured_line(line, HARDWARE_CONFIG.output_lines, "GPIO output")
            value = _gpio_sim_value(line)
            return json.dumps({"value": int(bool(value))}) + "\n"

        elif message.get("req") == "get" and device == "rfid":
            _require_device("mfrc522")
            spi_state = state["spi"]
            assert isinstance(spi_state, dict)
            rfid = spi_state["mfrc522"]
            assert isinstance(rfid, dict)
            return (
                json.dumps(
                    {
                        "present": bool(rfid.get("present")),
                        "uid": rfid.get("uid") or "00:00:00:00",
                    }
                )
                + "\n"
            )

        elif event == "register":
            LOGGER.info(
                "registered %s line=%s direction=%s",
                device,
                message.get("line"),
                message.get("dir"),
            )
        else:
            LOGGER.debug("ignored unsupported stub message: %s", raw[:200])
            if expects_response:
                raise RequestValidationError("unsupported stub request")

    except RequestValidationError as exc:
        LOGGER.warning("discarded invalid stub message: %s", exc)
        if expects_response:
            return json.dumps({"ok": False, "error": str(exc)}) + "\n"
    return None


def _remove_stale_unix_socket(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    original = path.lstat()
    if not stat.S_ISSOCK(original.st_mode):
        raise RuntimeError(f"refusing to replace non-socket path: {path}")

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(str(path))
        except OSError as exc:
            if exc.errno not in {errno.ECONNREFUSED, errno.ENOENT}:
                raise RuntimeError(
                    f"cannot inspect existing Unix socket {path}: {exc}"
                ) from exc
        else:
            raise RuntimeError(f"another hardware bridge is already using {path}")
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
        raise RuntimeError(f"Unix socket changed while it was being inspected: {path}")
    path.unlink()


def _complete_future(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)


def _fail_future(future: asyncio.Future[None], error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)


def _run_stub_connection(
    connection: socket.socket,
    loop: asyncio.AbstractEventLoop,
) -> None:
    try:
        handle_stub_connection(connection, loop)
    finally:
        _stub_connection_slots.release()


def unix_server_thread(
    loop: asyncio.AbstractEventLoop,
    ready: asyncio.Future[None],
    stopped: asyncio.Future[None],
) -> None:
    socket_path = Path(UNIX_SOCKET_PATH)
    server: socket.socket | None = None
    started = False
    try:
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        _remove_stale_unix_socket(socket_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(MAX_STUB_CONNECTIONS)
        os.chmod(socket_path, 0o660)
        LOGGER.info("Unix socket listening at %s", socket_path)
        started = True
        loop.call_soon_threadsafe(_complete_future, ready)

        while True:
            connection, _ = server.accept()
            try:
                _stub_connection_slots.acquire()
                threading.Thread(
                    target=_run_stub_connection,
                    args=(connection, loop),
                    daemon=True,
                ).start()
            except Exception:
                connection.close()
                _stub_connection_slots.release()
                raise
    except BaseException as exc:
        target = stopped if started else ready
        loop.call_soon_threadsafe(_fail_future, target, exc)
    finally:
        if server is not None:
            server.close()


def handle_stub_connection(
    connection: socket.socket, loop: asyncio.AbstractEventLoop
) -> None:
    buffer = bytearray()
    try:
        # The stubs intentionally keep their connection open between requests.
        # Limit only the initial handshake so idle clients cannot consume every
        # worker slot without breaking those persistent connections.
        connection.settimeout(FIRST_STUB_MESSAGE_TIMEOUT_SECONDS)
        received_first_line = False
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)

            while True:
                newline = buffer.find(b"\n")
                if newline < 0:
                    break
                raw_line = bytes(buffer[:newline])
                del buffer[: newline + 1]
                if len(raw_line) > MAX_STUB_LINE_BYTES:
                    raise RequestValidationError("stub message exceeds the line limit")
                try:
                    decoded = raw_line.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise RequestValidationError("stub message is not UTF-8") from exc
                if not received_first_line:
                    received_first_line = True
                    connection.settimeout(None)
                response = handle_stub_message(decoded, loop)
                if response:
                    connection.sendall(response.encode("utf-8"))

            if len(buffer) > MAX_STUB_LINE_BYTES:
                raise RequestValidationError("stub message exceeds the line limit")
    except RequestValidationError as exc:
        LOGGER.warning("closing invalid stub connection: %s", exc)
    except OSError as exc:
        LOGGER.warning("stub connection failed: %s", exc)
    except Exception:
        LOGGER.exception("unexpected stub connection failure")
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# HTTP JSON API and static panel
# ---------------------------------------------------------------------------


@web.middleware
async def validation_error_middleware(request, handler):
    try:
        return await handler(request)
    except RequestValidationError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


@web.middleware
async def browser_access_middleware(request, handler):
    if not browser_request_allowed(
        request.headers.get("Host", ""),
        request.headers.get("Origin"),
        ALLOWED_HTTP_HOSTS,
    ):
        return web.json_response(
            {"ok": False, "error": "bridge request host or origin is not allowed"},
            status=403,
        )
    return await handler(request)


async def _request_data(request: web.Request) -> dict[str, object]:
    data: dict[str, object] = dict(request.query)
    if not request.can_read_body:
        return data

    try:
        raw_body = await request.text()
    except (UnicodeError, LookupError) as exc:
        raise RequestValidationError("request body must be valid text") from exc
    if not raw_body.strip():
        return data
    body = parse_json_object(raw_body)
    data.update(body)
    return data


async def api_state(_request: web.Request) -> web.Response:
    return web.json_response(state)


async def api_metrics(request: web.Request) -> web.Response:
    application = request.match_info.get("application", "")
    try:
        payload = load_metrics(METRICS_DIR, application)
    except MetricsError as error:
        return web.json_response(
            {"ok": False, "error": {"code": error.code, "message": str(error)}},
            status=error.status,
        )
    return web.json_response(payload)


async def api_button(request: web.Request) -> web.Response:
    data = await _request_data(request)
    line = _button_line(data)
    pressed = boolean_value(data, "value")
    await set_button(line, pressed)
    return web.json_response({"ok": True, "line": line, "value": pressed})


async def api_button_press(request: web.Request) -> web.Response:
    data = await _request_data(request)
    line = _button_line(data)
    duration_ms = bounded_int(
        data,
        "duration_ms",
        default=150,
        minimum=0,
        maximum=MAX_BUTTON_PRESS_MS,
    )
    await press_button(line, duration_ms)
    return web.json_response({"ok": True, "line": line, "duration_ms": duration_ms})


async def api_rfid_tap(request: web.Request) -> web.Response:
    data = await _request_data(request)
    _require_device("mfrc522")
    uid = rfid_uid(data, DEFAULT_RFID_UID)
    await tap_rfid(uid)
    return web.json_response({"ok": True, "uid": uid, "present": True})


async def api_rfid_remove(_request: web.Request) -> web.Response:
    _require_device("mfrc522")
    await remove_rfid()
    return web.json_response({"ok": True, "present": False})


async def api_range(request: web.Request) -> web.Response:
    data = await _request_data(request)
    _require_device("vl53l0x")
    range_mm = bounded_int(data, "value", default=300, minimum=0, maximum=MAX_RANGE_MM)
    await set_range(range_mm)
    return web.json_response({"ok": True, "value": range_mm})


async def api_rotary_rotate(request: web.Request) -> web.Response:
    data = await _request_data(request)
    direction = _direction(data)
    await rotary_step(direction)
    return web.json_response({"ok": True, "direction": direction})


async def api_rotary_press(_request: web.Request) -> web.Response:
    await rotary_press()
    return web.json_response({"ok": True})


def _camera_input_settings(request: web.Request) -> tuple[int, int, int]:
    """Validate the V4L2 mode requested by a browser camera producer.

    The app selects its native V4L2 mode in its simulation service.  The
    browser supplies the same mode explicitly, rather than silently scaling a
    3 MP UVC source down to the Bridge's historic 640x480 default.
    """
    width = bounded_int(
        request.query,
        "width",
        default=int(os.environ.get("GAR_CAMERA_WIDTH", "640")),
        minimum=160,
        maximum=4096,
    )
    height = bounded_int(
        request.query,
        "height",
        default=int(os.environ.get("GAR_CAMERA_HEIGHT", "480")),
        minimum=120,
        maximum=3072,
    )
    fps = bounded_int(
        request.query,
        "fps",
        default=int(os.environ.get("GAR_CAMERA_FPS", "30")),
        minimum=1,
        maximum=60,
    )
    if width * height > 4_194_304:
        raise RequestValidationError("camera frame must not exceed 4194304 pixels")
    return width, height, fps


def _camera_pipeline_command(width: int, height: int, fps: int) -> tuple[str, ...]:
    # v4l2loopback defaults to 30 fps. videorate duplicates the browser's
    # 15 fps input so the capture side can negotiate the device default.
    device = os.environ.get("GAR_CAMERA_DEVICE", "/dev/video0")
    return (
        "gst-launch-1.0",
        "-q",
        "fdsrc",
        "fd=0",
        "do-timestamp=true",
        "!",
        "jpegparse",
        "!",
        "jpegdec",
        "!",
        "videoconvert",
        "!",
        "videorate",
        "!",
        f"video/x-raw,format=YUY2,width={width},height={height},framerate={fps}/1",
        "!",
        "v4l2sink",
        f"device={device}",
        "sync=false",
    )


async def camera_input_websocket(request: web.Request) -> web.WebSocketResponse:
    """Feed browser JPEG frames into the V4L2 camera used by the target app."""
    width, height, fps = _camera_input_settings(request)
    socket = web.WebSocketResponse(max_msg_size=MAX_CAMERA_FRAME_BYTES)
    await socket.prepare(request)
    if camera_input_lock.locked():
        await socket.send_json(
            {"type": "error", "error": "another camera input is active"}
        )
        await socket.close()
        return socket

    async with camera_input_lock:
        device = os.environ.get("GAR_CAMERA_DEVICE", "/dev/video0")
        if not Path(device).exists():
            await socket.send_json(
                {"type": "error", "error": f"camera device is unavailable: {device}"}
            )
            await socket.close()
            return socket
        try:
            process = await asyncio.create_subprocess_exec(
                *_camera_pipeline_command(width, height, fps),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            await socket.send_json(
                {"type": "error", "error": f"cannot start camera pipeline: {exc}"}
            )
            await socket.close()
            return socket

        await socket.send_json(
            {
                "type": "ready",
                "device": device,
                "width": width,
                "height": height,
                "fps": fps,
            }
        )
        try:
            async for incoming in socket:
                if incoming.type != WSMsgType.BINARY:
                    continue
                if process.returncode is not None or process.stdin is None:
                    await socket.send_json(
                        {"type": "error", "error": "camera pipeline stopped"}
                    )
                    break
                process.stdin.write(incoming.data)
                await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.warning("camera input pipeline closed while receiving frames")
        finally:
            if process.stdin is not None:
                process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except TimeoutError:
                process.terminate()
                await process.wait()
    return socket


async def panel_file_handler(request: web.Request) -> web.Response:
    request_path = request.match_info.get("path_info", "")
    if request_path.startswith("components/"):
        file_path = resolve_panel_file(
            COMPONENTS_DIR, request_path.removeprefix("components/")
        )
    else:
        file_path = resolve_panel_file(_active_panel_dir(), request_path)
    if file_path is None:
        return web.Response(status=404, text="Not found")
    return web.FileResponse(file_path, headers={"Cache-Control": "no-store"})


def _active_panel_dir() -> Path:
    """Return the application-selected panel, falling back to the generic one.

    The configuration file is an intentionally tiny deployment contract: its
    sole line is an absolute directory that contains an `index.html`.
    Invalid, removed, or partial application deployments keep the bridge's
    built-in diagnostic panel available.
    """
    try:
        configured = Path(PANEL_DIR_CONFIG.read_text(encoding="utf-8").strip())
    except OSError:
        return PANEL_DIR
    if not configured.is_absolute() or not configured.is_dir():
        return PANEL_DIR
    return configured


def create_application() -> web.Application:
    application = web.Application(
        middlewares=[browser_access_middleware, validation_error_middleware],
        client_max_size=MAX_BROWSER_MESSAGE_BYTES,
    )
    application.router.add_get("/ws", websocket_handler)
    application.router.add_get("/api/state", api_state)
    application.router.add_get("/api/metrics/{application}", api_metrics)
    application.router.add_post("/api/button", api_button)
    application.router.add_post("/api/button/press", api_button_press)
    application.router.add_post("/api/rfid/tap", api_rfid_tap)
    application.router.add_post("/api/rfid/remove", api_rfid_remove)
    application.router.add_post("/api/range", api_range)
    application.router.add_post("/api/rotary/rotate", api_rotary_rotate)
    application.router.add_post("/api/rotary/press", api_rotary_press)
    application.router.add_get("/camera-input/ws", camera_input_websocket)
    application.router.add_get("/{path_info:.*}", panel_file_handler)
    return application


def _initial_gpio_input_level(definition: GpioLine) -> bool:
    rotary = HARDWARE_CONFIG.rotary
    rotary_phase_lines = {rotary.clock, rotary.data} if rotary else set()
    if definition.line in rotary_phase_lines:
        return True
    if definition.role == "button":
        return definition.electrical_level_for(False)
    if definition.pull == "pull-up":
        return True
    if definition.pull == "pull-down":
        return False
    return definition.electrical_level_for(False)


def initialise_gpio_inputs() -> None:
    for definition in HARDWARE_CONFIG.gpio_lines:
        if definition.direction != "input":
            continue
        _gpio_sim_set_level(definition.line, _initial_gpio_input_level(definition))


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    LOGGER.info("hardware configuration: %s", state["hardware"])

    initialise_gpio_inputs()
    loop = asyncio.get_running_loop()
    unix_ready = loop.create_future()
    unix_stopped = loop.create_future()
    threading.Thread(
        target=unix_server_thread,
        args=(loop, unix_ready, unix_stopped),
        daemon=True,
    ).start()
    await unix_ready
    output_poll_task = asyncio.create_task(poll_gpio_sim_outputs())

    runner = web.AppRunner(create_application())
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()
    LOGGER.info("panel and WebSocket listening at http://%s:%s", HTTP_HOST, HTTP_PORT)

    try:
        await unix_stopped
    finally:
        output_poll_task.cancel()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
