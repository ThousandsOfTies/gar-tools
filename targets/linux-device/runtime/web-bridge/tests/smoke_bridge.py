#!/usr/bin/env python3
"""Run transport-level smoke checks against a live bridge process.

Unlike the standard-library unit tests in this directory, this script requires
aiohttp because it verifies the runtime HTTP and WebSocket integration.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from aiohttp import ClientConnectorError, ClientSession, WSServerHandshakeError


WEB_BRIDGE_DIR = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = WEB_BRIDGE_DIR / "bridge.py"
STUB_CONNECTION_LIMIT = 16

SMOKE_HARDWARE_FILES = {
    "linux-device": {
        "gpio.csv": """name,chip,line,direction,role,active,initial,pull,sim_control,description
power_button,/dev/gpiochip0,17,input,button,high,,pull-down,pull,test button
status_led,/dev/gpiochip0,18,output,led,high,0,,value,test status LED
activity_led,/dev/gpiochip0,24,output,led,high,0,,value,test activity LED
aux_button,/dev/gpiochip0,27,input,button,high,,pull-down,pull,test auxiliary button
""",
        "i2c.csv": """name,bus,dev,address,driver,sim,description
display,1,/dev/i2c-1,0x3c,ssd1306,ssd1306,test display
range,1,/dev/i2c-1,0x29,vl53l0x,vl53l0x,test range sensor
servo,1,/dev/i2c-1,0x40,pca9685,pca9685,test PWM controller
""",
        "spi.csv": """name,bus,chip_select,dev,mode,max_speed_hz,driver,sim,description
rfid,0,0,/dev/spidev0.0,0,1000000,mfrc522,mfrc522,test RFID reader
""",
    },
    "luckfox-rv1106": {
        "gpio.csv": """name,chip,line,direction,role,active,initial,pull,sim_control,description
encoder_a,/dev/gpiochip0,20,input,encoder,high,,pull-up,,test encoder phase A
encoder_b,/dev/gpiochip0,21,input,encoder,high,,pull-up,,test encoder phase B
encoder_sw,/dev/gpiochip0,22,input,button,low,,pull-up,,test encoder switch
lcd_dc,/dev/gpiochip0,23,output,display_ctrl,high,1,,,test display DC
lcd_rst,/dev/gpiochip0,24,output,display_ctrl,high,1,,,test display reset
""",
        "spi.csv": """name,bus,chip_select,dev,mode,max_speed_hz,driver,sim,description
display,0,0,/dev/spidev0.0,0,40000000,ili9341,ili9341,test display
""",
    },
}


def _write_smoke_hardware(root: Path) -> list[Path]:
    hardware_dirs: list[Path] = []
    for target_name, files in SMOKE_HARDWARE_FILES.items():
        hardware_dir = root / target_name / "hardware"
        hardware_dir.mkdir(parents=True)
        for filename, content in files.items():
            (hardware_dir / filename).write_text(content, encoding="utf-8")
        hardware_dirs.append(hardware_dir)
    return hardware_dirs


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _bridge_environment(
    port: int,
    hardware_dir: Path,
    runtime_dir: Path,
    unix_socket: Path,
) -> dict[str, str]:
    environment = os.environ.copy()
    # Exercise the secure loopback default, independently of the caller's env.
    environment.pop("GAR_BRIDGE_HOST", None)
    environment.pop("GAR_BRIDGE_ALLOWED_HOSTS", None)
    environment.update(
        {
            "GAR_BRIDGE_PORT": str(port),
            "GAR_HARDWARE_DIR": str(hardware_dir),
            "GAR_RUNTIME_DIR": str(runtime_dir),
            "GAR_HW_SIM_SOCK": str(unix_socket),
            "GAR_METRICS_DIR": str(runtime_dir / "metrics"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def _unix_exchange_many(
    socket_path: Path,
    messages: list[dict[str, object]],
) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(str(socket_path))
        payload = b"".join(
            json.dumps(message).encode("utf-8") + b"\n" for message in messages
        )
        client.sendall(payload)
        response = bytearray()
        while b"\n" not in response:
            chunk = client.recv(4096)
            if not chunk:
                raise AssertionError("Unix socket closed without a response")
            response.extend(chunk)
    return json.loads(response.split(b"\n", 1)[0])


def _unix_exchange(socket_path: Path, message: dict[str, object]) -> dict[str, object]:
    return _unix_exchange_many(socket_path, [message])


def _open_idle_stub_connections(socket_path: Path) -> list[socket.socket]:
    clients: list[socket.socket] = []
    try:
        for _index in range(STUB_CONNECTION_LIMIT):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(2)
            client.connect(str(socket_path))
            clients.append(client)
            # Give the accept loop time to move the connection out of the
            # small Unix-socket listen backlog before opening the next one.
            time.sleep(0.02)
    except BaseException:
        for client in clients:
            client.close()
        raise
    return clients


async def _expect_startup_failure(
    environment: dict[str, str],
    reason: str,
) -> str:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as process_log:
        process = subprocess.Popen(
            [sys.executable, str(BRIDGE_SCRIPT)],
            env=environment,
            stdout=process_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        timed_out = False
        try:
            try:
                await asyncio.to_thread(process.wait, 2)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

        process_log.seek(0)
        output = process_log.read()
        if timed_out:
            raise AssertionError(f"bridge did not reject {reason}\n{output}")
        if process.returncode == 0:
            raise AssertionError(f"bridge unexpectedly accepted {reason}\n{output}")
        return output


async def _wait_until_ready(
    session: ClientSession,
    base_url: str,
    process: subprocess.Popen[str],
) -> dict[str, object]:
    for _attempt in range(100):
        if process.poll() is not None:
            raise AssertionError(
                f"bridge exited early with status {process.returncode}"
            )
        try:
            async with session.get(f"{base_url}/api/state") as response:
                if response.status == 200:
                    return await response.json()
        except ClientConnectorError:
            pass
        await asyncio.sleep(0.05)
    raise AssertionError("bridge did not become ready within five seconds")


def _assert_hardware_mapping(
    hardware_dir: Path, state: dict[str, object]
) -> tuple[str, dict[str, object]]:
    hardware = state["hardware"]
    assert isinstance(hardware, dict)
    gpio = hardware["gpio"]
    assert isinstance(gpio, dict)
    devices = hardware["devices"]
    assert isinstance(devices, list)

    if hardware_dir.name == "hardware" and hardware_dir.parent.name == "linux-device":
        assert gpio["inputs"] == [17, 27]
        assert gpio["outputs"] == [18, 24]
        assert gpio["rotary"] is None
        assert devices == ["mfrc522", "ssd1306", "vl53l0x"]
        return "linux-device", {"req": "get", "device": "gpio", "line": 17}

    if hardware_dir.name == "hardware" and hardware_dir.parent.name == "luckfox-rv1106":
        assert gpio["inputs"] == [20, 21, 22]
        assert gpio["outputs"] == [23, 24]
        assert gpio["rotary"] == {"clock": 20, "data": 21, "switch": 22}
        assert gpio["displayDc"] == 23
        assert devices == ["ili9341"]
        return "luckfox-rv1106", {
            "req": "get",
            "device": "gpio_out",
            "line": 23,
        }

    raise AssertionError(f"no expected mapping is defined for {hardware_dir}")


async def _raw_traversal_status(port: int) -> int:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        b"GET /..%2FREADME.md HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Connection: close\r\n\r\n"
    )
    await writer.drain()
    status_line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return int(status_line.split()[1])


async def check_hardware_directory(hardware_dir: Path) -> None:
    hardware_dir = hardware_dir.resolve()
    port = _free_tcp_port()

    with tempfile.TemporaryDirectory(prefix="gar-bridge-smoke-") as runtime_dir_name:
        runtime_dir = Path(runtime_dir_name)
        unix_socket = runtime_dir / "hw_sim.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale_socket:
            stale_socket.bind(str(unix_socket))
        environment = _bridge_environment(
            port,
            hardware_dir,
            runtime_dir,
            unix_socket,
        )

        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as bridge_log:
            process = subprocess.Popen(
                [sys.executable, str(BRIDGE_SCRIPT)],
                env=environment,
                stdout=bridge_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            base_url = f"http://127.0.0.1:{port}"
            try:
                async with ClientSession() as session:
                    state = await _wait_until_ready(session, base_url, process)
                    target_name, unix_request = _assert_hardware_mapping(
                        hardware_dir, state
                    )

                    async with session.get(f"{base_url}/") as response:
                        assert response.status == 200
                        assert "Virtual Hardware Panel" in await response.text()

                    metrics_dir = runtime_dir / "metrics"
                    metrics_dir.mkdir()
                    (metrics_dir / "gar-stream-test.json").write_text(
                        json.dumps({"frames": {"sent": 1}}), encoding="utf-8"
                    )
                    async with session.get(f"{base_url}/api/metrics/gar-stream-test") as response:
                        assert response.status == 200
                        assert await response.json() == {"frames": {"sent": 1}}
                    async with session.get(f"{base_url}/api/metrics/missing") as response:
                        assert response.status == 404
                        missing_metrics = await response.json()
                        assert missing_metrics["error"]["code"] == "metrics_not_found"

                    async with session.ws_connect(
                        f"{base_url}/ws", origin=base_url
                    ) as websocket:
                        initial = await websocket.receive_json(timeout=2)
                        assert initial["type"] == "init"
                        assert initial["state"]["hardware"] == state["hardware"]

                    try:
                        unexpected_websocket = await session.ws_connect(
                            f"{base_url}/ws",
                            origin="https://malicious.example",
                        )
                    except WSServerHandshakeError as exc:
                        assert exc.status == 403
                    else:
                        await unexpected_websocket.close()
                        raise AssertionError("cross-origin WebSocket was accepted")

                    async with session.post(
                        f"{base_url}/api/button",
                        json={"line": 4095, "value": True},
                    ) as response:
                        assert response.status == 400
                        invalid_response = await response.json()
                        assert invalid_response["ok"] is False

                    async with session.post(
                        f"{base_url}/api/button",
                        data="{",
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        assert response.status == 400
                        malformed_response = await response.json()
                        assert malformed_response["ok"] is False

                    async with session.post(
                        f"{base_url}/api/button",
                        data=b"{}",
                        headers={
                            "Content-Type": "application/json; charset=not-a-charset"
                        },
                    ) as response:
                        assert response.status == 400
                        charset_response = await response.json()
                        assert charset_response["ok"] is False

                    async with session.get(
                        f"{base_url}/api/state",
                        headers={"Host": "malicious.example"},
                    ) as response:
                        assert response.status == 403

                    async with session.post(
                        f"{base_url}/api/button",
                        headers={"Origin": "https://malicious.example"},
                        json={"line": 17, "value": True},
                    ) as response:
                        assert response.status == 403

                    traversal_status = await _raw_traversal_status(port)
                    assert traversal_status in {400, 404}

                    unix_response = await asyncio.to_thread(
                        _unix_exchange, unix_socket, unix_request
                    )
                    assert unix_response == {"value": 0}
                    if target_name == "linux-device":
                        channels = [
                            {
                                "channel": channel,
                                "on": 0,
                                "off": 307 if channel == 0 else 0,
                                "fullOn": False,
                                "fullOff": False,
                            }
                            for channel in range(16)
                        ]
                        await asyncio.to_thread(
                            _unix_exchange_many,
                            unix_socket,
                            [
                                {
                                    "event": "set",
                                    "device": "pca9685",
                                    "address": 0x40,
                                    "frequencyHz": 50.0,
                                    "channels": channels,
                                },
                                unix_request,
                            ],
                        )
                        async with session.get(f"{base_url}/api/state") as response:
                            servo_state = await response.json()
                        assert servo_state["i2c"]["pca9685"]["frequencyHz"] == 50.0
                        assert servo_state["i2c"]["pca9685"]["channels"][0]["off"] == 307
                    invalid_unix_response = await asyncio.to_thread(
                        _unix_exchange,
                        unix_socket,
                        {"req": "get", "device": "gpio", "line": 4095},
                    )
                    assert invalid_unix_response["ok"] is False

                    mixed_unix_response = await asyncio.to_thread(
                        _unix_exchange,
                        unix_socket,
                        {**unix_request, "event": "set", "value": 1},
                    )
                    assert mixed_unix_response["ok"] is False
                    assert "both req and event" in mixed_unix_response["error"]

                    if target_name == "linux-device":
                        invalid_frame_event = {
                            "event": "set",
                            "device": "oled",
                            "framebuf": "AAAA",
                        }
                        frame_state_path = ("i2c", "ssd1306", "framebuf")
                    else:
                        invalid_frame_event = {
                            "event": "set",
                            "device": "ili9341",
                            "width": 320,
                            "height": 240,
                            "pixels": "AAAA",
                        }
                        frame_state_path = ("spi", "ili9341", "pixels")
                    response_after_invalid_frame = await asyncio.to_thread(
                        _unix_exchange_many,
                        unix_socket,
                        [invalid_frame_event, unix_request],
                    )
                    assert response_after_invalid_frame == {"value": 0}
                    async with session.get(f"{base_url}/api/state") as response:
                        current_state = await response.json()
                    group, device, field = frame_state_path
                    assert current_state[group][device][field] is None

                    if target_name == "linux-device":
                        idle_clients = await asyncio.to_thread(
                            _open_idle_stub_connections,
                            unix_socket,
                        )
                        try:
                            await asyncio.sleep(5.25)
                            response_after_idle_timeout = await asyncio.to_thread(
                                _unix_exchange,
                                unix_socket,
                                unix_request,
                            )
                            assert response_after_idle_timeout == {"value": 0}
                        finally:
                            for idle_client in idle_clients:
                                idle_client.close()
                    else:
                        async with session.post(
                            f"{base_url}/api/rotary/rotate", json={"direction": 1}
                        ) as response:
                            assert response.status == 200
                        async with session.post(f"{base_url}/api/rotary/press", json={}) as response:
                            assert response.status == 200
                        async with session.get(f"{base_url}/api/state") as response:
                            rotary_state = await response.json()
                        assert rotary_state["gpio"]["rotary"]["counter"] == 1

                    second_environment = dict(environment)
                    second_environment["GAR_BRIDGE_PORT"] = str(_free_tcp_port())
                    second_output = await _expect_startup_failure(
                        second_environment,
                        "a live Unix socket",
                    )
                    assert "already using" in second_output

                    still_live_response = await asyncio.to_thread(
                        _unix_exchange, unix_socket, unix_request
                    )
                    assert still_live_response == {"value": 0}

                    blocked_socket = runtime_dir / "not-a-socket"
                    blocked_socket.write_text("preserve me", encoding="utf-8")
                    blocked_environment = dict(environment)
                    blocked_environment["GAR_BRIDGE_PORT"] = str(_free_tcp_port())
                    blocked_environment["GAR_HW_SIM_SOCK"] = str(blocked_socket)
                    blocked_output = await _expect_startup_failure(
                        blocked_environment,
                        "a non-socket runtime path",
                    )
                    assert "refusing to replace non-socket path" in blocked_output
                    assert blocked_socket.read_text(encoding="utf-8") == "preserve me"

                    print(
                        f"{target_name}: HTTP, panel, same-origin WebSocket, access control, "
                        f"validation/base64, stale/live/non-socket startup, "
                        f"traversal={traversal_status}, "
                        f"single-owner Unix response={unix_response} — checks passed"
                    )
            except Exception:
                bridge_log.seek(0)
                print(bridge_log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


async def check_empty_hardware_directory() -> None:
    port = _free_tcp_port()
    with tempfile.TemporaryDirectory(prefix="gar-empty-hardware-") as hardware_name:
        with tempfile.TemporaryDirectory(prefix="gar-empty-runtime-") as runtime_name:
            hardware_dir = Path(hardware_name)
            runtime_dir = Path(runtime_name)
            unix_socket = runtime_dir / "hw_sim.sock"
            environment = _bridge_environment(
                port,
                hardware_dir,
                runtime_dir,
                unix_socket,
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as bridge_log:
                process = subprocess.Popen(
                    [sys.executable, str(BRIDGE_SCRIPT)],
                    env=environment,
                    stdout=bridge_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                base_url = f"http://127.0.0.1:{port}"
                try:
                    async with ClientSession() as session:
                        state = await _wait_until_ready(session, base_url, process)
                        hardware = state["hardware"]
                        assert hardware["gpio"]["inputs"] == []
                        assert hardware["gpio"]["outputs"] == []
                        assert hardware["devices"] == []

                        async with session.post(
                            f"{base_url}/api/button",
                            json={"line": 0, "value": True},
                        ) as response:
                            assert response.status == 400
                            error = await response.json()
                            assert "no push button" in error["error"]

                        unix_response = await asyncio.to_thread(
                            _unix_exchange,
                            unix_socket,
                            {"req": "get", "device": "gpio", "line": 0},
                        )
                        assert unix_response["ok"] is False
                        assert "configured lines: none" in unix_response["error"]

                    print(
                        "empty-hardware: no demo fallback and empty-button "
                        "validation — checks passed"
                    )
                except Exception:
                    bridge_log.seek(0)
                    print(bridge_log.read(), file=sys.stderr)
                    raise
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gar-smoke-hardware-") as root_name:
        for hardware_dir in _write_smoke_hardware(Path(root_name)):
            asyncio.run(check_hardware_directory(hardware_dir))
    asyncio.run(check_empty_hardware_directory())


if __name__ == "__main__":
    main()
