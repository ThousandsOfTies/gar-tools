#!/usr/bin/env python3
"""Generate a Wokwi workspace from the shared M5Stick template."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


IGNORED_TEMPLATE_PARTS = {".git", ".pio", "__pycache__"}
TEMPLATE_FILES = {"platformio.ini.template", "wokwi.toml.template"}


def environment_path(name: str, default: Path | None = None) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser().resolve()
    if default is None:
        raise RuntimeError(f"{name} is required")
    return default.resolve()


def copy_template(template_dir: Path, project_dir: Path) -> None:
    for source in sorted(template_dir.rglob("*")):
        relative_path = source.relative_to(template_dir)
        if any(part in IGNORED_TEMPLATE_PARTS for part in relative_path.parts):
            continue
        if not source.is_file() or source.name in TEMPLATE_FILES:
            continue
        if relative_path == Path("scripts/prepare_workspace.py"):
            continue
        destination = project_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def render_workspace(
    template_dir: Path,
    project_dir: Path,
    app_src_dir: Path,
    app_config_path: Path | None,
) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    copy_template(template_dir, project_dir)

    legacy_src = project_dir / "src"
    if legacy_src.is_symlink():
        legacy_src.unlink()
    elif legacy_src.is_dir():
        shutil.rmtree(legacy_src)

    app_config = ""
    if app_config_path is not None:
        if not app_config_path.is_file():
            raise RuntimeError(f"Wokwi application config not found: {app_config_path}")
        (project_dir / ".gar-app.ini").write_text(app_config_path.read_text(encoding="utf-8"), encoding="utf-8")
        app_config = "extra_configs = .gar-app.ini"

    app_src = Path(os.path.relpath(app_src_dir, project_dir)).as_posix()
    platformio_template = template_dir / "platformio.ini.template"
    (project_dir / "platformio.ini").write_text(
        platformio_template.read_text(encoding="utf-8").format(app_src=app_src, app_config=app_config),
        encoding="utf-8",
    )

    firmware = os.environ.get("GAR_WOKWI_FIRMWARE", ".pio/build/m5stackc/firmware.bin")
    elf = os.environ.get("GAR_WOKWI_ELF", ".pio/build/m5stackc/firmware.elf")
    wokwi_template = template_dir / "wokwi.toml.template"
    (project_dir / "wokwi.toml").write_text(
        wokwi_template.read_text(encoding="utf-8").format(firmware=firmware, elf=elf),
        encoding="utf-8",
    )


def main() -> int:
    template_dir = environment_path("GAR_WOKWI_TEMPLATE_DIR", Path(__file__).resolve().parents[1])
    project_dir = environment_path("GAR_WOKWI_PROJECT_DIR")
    app_src_dir = environment_path("GAR_WOKWI_APP_SRC_DIR")
    raw_app_config = os.environ.get("GAR_WOKWI_APP_CONFIG")
    app_config_path = Path(raw_app_config).expanduser().resolve() if raw_app_config else None

    if not template_dir.is_dir():
        raise RuntimeError(f"Wokwi template directory not found: {template_dir}")
    if not app_src_dir.is_dir():
        raise RuntimeError(f"Wokwi application source directory not found: {app_src_dir}")

    render_workspace(template_dir, project_dir, app_src_dir, app_config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
