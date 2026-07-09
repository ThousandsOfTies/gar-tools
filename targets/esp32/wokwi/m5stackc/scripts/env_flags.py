from __future__ import annotations

import os
from pathlib import Path

Import("env")

PROJECT_DIR = Path(env.subst("$PROJECT_DIR"))
ENV_FILE = PROJECT_DIR / ".env.local"


def config_value(key: str) -> str | None:
    if key in os.environ:
        return os.environ[key]
    if not ENV_FILE.exists():
        return None
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None


battery_percent = config_value("M5STICK_BATTERY_PERCENT")
if battery_percent is not None:
    env.Append(CPPDEFINES=[("M5STICK_BATTERY_PERCENT", battery_percent)])
