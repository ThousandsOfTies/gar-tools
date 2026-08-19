"""Pure validation helpers shared by the bridge transports."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


class RequestValidationError(ValueError):
    """An HTTP, WebSocket, or Unix-socket message contains invalid input."""


def require_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise RequestValidationError("message must be a JSON object")
    return value


def parse_json_object(raw: str) -> Mapping[str, object]:
    """Parse a JSON object and normalise parser failures as request errors."""
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise RequestValidationError("message must be valid JSON") from exc
    return require_object(value)


def bounded_int(
    data: Mapping[str, object],
    field: str,
    *,
    default: int | None = None,
    minimum: int,
    maximum: int,
) -> int:
    raw = data.get(field, default)
    if raw is None or isinstance(raw, bool):
        raise RequestValidationError(f"{field} must be an integer")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and re.fullmatch(r"[+-]?\d+", raw.strip()):
        try:
            value = int(raw, 10)
        except ValueError as exc:
            raise RequestValidationError(f"{field} must be an integer") from exc
    else:
        raise RequestValidationError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise RequestValidationError(f"{field} must be between {minimum} and {maximum}")
    return value


def boolean_value(data: Mapping[str, object], field: str) -> bool:
    raw = data.get(field)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        normalised = raw.strip().lower()
        if normalised in {"1", "true", "on"}:
            return True
        if normalised in {"0", "false", "off"}:
            return False
    raise RequestValidationError(f"{field} must be true/false or 1/0")


def pca9685_state(data: Mapping[str, object]) -> dict[str, object]:
    """Validate the complete PCA9685 state published by the I2C stub."""
    address = bounded_int(data, "address", default=0x40, minimum=0, maximum=0x7F)
    frequency_value = data.get("frequencyHz")
    if frequency_value is None:
        frequency_hz = None
    elif (
        isinstance(frequency_value, bool)
        or not isinstance(frequency_value, (int, float))
        or not math.isfinite(frequency_value)
        or not 1 <= frequency_value <= 2000
    ):
        raise RequestValidationError("frequencyHz must be null or between 1 and 2000")
    else:
        frequency_hz = float(frequency_value)

    raw_channels = data.get("channels")
    if not isinstance(raw_channels, list) or len(raw_channels) != 16:
        raise RequestValidationError("channels must contain exactly 16 entries")

    channels: list[dict[str, object]] = []
    for index, raw_channel in enumerate(raw_channels):
        if not isinstance(raw_channel, dict):
            raise RequestValidationError(f"channels[{index}] must be an object")
        channel = bounded_int(raw_channel, "channel", minimum=0, maximum=15)
        if channel != index:
            raise RequestValidationError(
                f"channels[{index}].channel must equal its array index"
            )
        channels.append(
            {
                "channel": channel,
                "on": bounded_int(raw_channel, "on", minimum=0, maximum=4095),
                "off": bounded_int(raw_channel, "off", minimum=0, maximum=4095),
                "fullOn": boolean_value(raw_channel, "fullOn"),
                "fullOff": boolean_value(raw_channel, "fullOff"),
            }
        )
    return {
        "address": address,
        "frequencyHz": frequency_hz,
        "channels": channels,
    }


_RFID_UID = re.compile(r"^[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){3,9}$")


def rfid_uid(data: Mapping[str, object], default: str) -> str:
    value = data.get("uid", default)
    if not isinstance(value, str) or not _RFID_UID.fullmatch(value.strip()):
        raise RequestValidationError(
            "uid must contain 4 to 10 hexadecimal bytes separated by colons"
        )
    return value.strip().upper()


def configured_line(line: int, allowed_lines: tuple[int, ...], purpose: str) -> int:
    if line not in allowed_lines:
        choices = ", ".join(str(value) for value in allowed_lines) or "none"
        raise RequestValidationError(
            f"GPIO line {line} is not configured for {purpose}; configured lines: {choices}"
        )
    return line


def browser_request_allowed(
    host_header: str,
    origin_header: str | None,
    allowed_hosts: frozenset[str],
) -> bool:
    """Allow configured hosts and reject cross-origin browser control requests."""

    host_header = host_header.strip()
    try:
        request_url = urlsplit(f"//{host_header}")
        request_url.port
    except ValueError:
        return False
    hostname = request_url.hostname
    if (
        hostname is None
        or hostname.casefold() not in allowed_hosts
        or request_url.username is not None
        or request_url.password is not None
        or request_url.path
        or request_url.query
        or request_url.fragment
    ):
        return False
    if origin_header is None:
        return True

    try:
        origin = urlsplit(origin_header.strip())
        origin.port
    except ValueError:
        return False
    return (
        origin.scheme in {"http", "https"}
        and origin.username is None
        and origin.password is None
        and not origin.path
        and not origin.query
        and not origin.fragment
        and origin.netloc.casefold() == host_header.casefold()
    )


def resolve_panel_file(panel_dir: Path, request_path: str) -> Path | None:
    """Return a contained regular file, rejecting traversal and directories."""
    root = panel_dir.resolve()
    relative_path = request_path.lstrip("/") or "index.html"
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None
