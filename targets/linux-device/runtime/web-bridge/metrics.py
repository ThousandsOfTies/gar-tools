"""Safe read-only loading of application telemetry published under ``/run``."""

from __future__ import annotations

import json
import errno
import os
import re
import stat
from pathlib import Path
from typing import Any


SAFE_APPLICATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
MAX_METRICS_BYTES = 1024 * 1024


class MetricsError(ValueError):
    def __init__(self, code: str, message: str, *, status: int):
        self.code = code
        self.status = status
        super().__init__(message)


def load_metrics(metrics_dir: Path, application: str) -> dict[str, Any]:
    """Load one bounded, regular JSON-object telemetry file without following links."""

    if not SAFE_APPLICATION.fullmatch(application):
        raise MetricsError("metrics_invalid_application", "application name is invalid", status=400)
    path = metrics_dir / f"{application}.json"
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as error:
        raise MetricsError("metrics_not_found", "metrics file does not exist", status=404) from error
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise MetricsError("metrics_invalid", "metrics file must be a regular non-symlink", status=422) from error
        raise MetricsError("metrics_unavailable", "metrics file cannot be inspected", status=503) from error
    try:
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise MetricsError("metrics_invalid", "metrics file must be a regular non-symlink", status=422)
            if info.st_size > MAX_METRICS_BYTES:
                raise MetricsError("metrics_invalid", "metrics file exceeds the size limit", status=422)
            raw_bytes = stream.read(MAX_METRICS_BYTES + 1)
        if len(raw_bytes) > MAX_METRICS_BYTES:
            raise MetricsError("metrics_invalid", "metrics file exceeds the size limit", status=422)
        raw = raw_bytes.decode("utf-8")
        payload = json.loads(raw, parse_constant=_reject_json_constant)
    except MetricsError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MetricsError("metrics_invalid", "metrics file must contain valid JSON", status=422) from error
    if not isinstance(payload, dict):
        raise MetricsError("metrics_invalid", "metrics JSON root must be an object", status=422)
    return payload


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"JSON numeric constant is not allowed: {value}")
