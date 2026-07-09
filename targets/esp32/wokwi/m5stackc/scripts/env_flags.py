from __future__ import annotations

import os
from pathlib import Path

Import("env")

PROJECT_DIR = Path(env.subst("$PROJECT_DIR"))
ENV_FILE = PROJECT_DIR / ".env.local"


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]
        values[key] = value
    return values


def config_value(values: dict[str, str], key: str) -> str | None:
    if key in os.environ:
        return os.environ[key]
    return values.get(key)


def c_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'\\"{escaped}\\"'


dotenv = read_dotenv(ENV_FILE)

string_keys = (
    "VIBE_WIFI_SSID",
    "VIBE_WIFI_PASS",
    "VIBE_REMOTE_HOST",
    "VIBE_REMOTE_TOKEN",
    "VIBE_SERVICE_TYPE",
    "VIBE_DEVICE_NAME",
)
defines = []

for key in string_keys:
    value = config_value(dotenv, key)
    if value is not None:
        defines.append((key, c_string(value)))

port = config_value(dotenv, "VIBE_REMOTE_PORT")
if port is not None:
    defines.append(("VIBE_REMOTE_PORT", port))

battery_percent = config_value(dotenv, "VIBE_BATTERY_PERCENT")
if battery_percent is not None:
    defines.append(("VIBE_BATTERY_PERCENT", battery_percent))

if defines:
    env.Append(CPPDEFINES=defines)
