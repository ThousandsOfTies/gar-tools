#!/usr/bin/env python3
"""Generate a Wokwi workspace from the shared M5Stick template."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


IGNORED_TEMPLATE_PARTS = {".git", ".pio", "__pycache__"}
TEMPLATE_FILES = {"platformio.ini.template", "wokwi.toml.template"}
WORKSPACE_MARKER = ".gar-generated"
MARKER_GENERATOR = "gar-tools-wokwi"
MARKER_VERSION = 1
LEGACY_WORKSPACE_FILES = {"platformio.ini", "wokwi.toml"}


@dataclass(frozen=True)
class WorkspaceState:
    legacy_marker: bool
    managed_files: frozenset[Path]


def environment_path(name: str, default: Path | None = None) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser().absolute()
    if default is None:
        raise RuntimeError(f"{name} is required")
    return default.absolute()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def paths_overlap(first: Path, second: Path) -> bool:
    return is_within(first, second) or is_within(second, first)


def reject_symlink_path(path: Path, label: str) -> None:
    """Reject every symlink component before writing through *path*."""

    absolute_path = path.expanduser().absolute()
    current = Path(absolute_path.anchor)
    for part in absolute_path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"{label} must not contain a symlink: {current}")


def validate_workspace_paths(
    template_dir: Path,
    project_dir: Path,
    app_src_dir: Path,
    app_config_path: Path | None,
) -> None:
    inputs = [("template", template_dir), ("application source", app_src_dir)]
    if app_config_path is not None:
        inputs.append(("application config", app_config_path))

    for label, input_path in inputs:
        if paths_overlap(project_dir, input_path):
            raise RuntimeError(
                f"Wokwi workspace must not overlap the {label}: "
                f"{project_dir} and {input_path}"
            )


def safe_relative_path(raw_path: str) -> Path:
    relative_path = Path(raw_path)
    if (
        not raw_path
        or relative_path.is_absolute()
        or relative_path == Path(".")
        or ".." in relative_path.parts
        or relative_path.name == WORKSPACE_MARKER
    ):
        raise RuntimeError(f"Invalid managed Wokwi workspace path: {raw_path!r}")
    return relative_path


def read_workspace_state(project_dir: Path) -> WorkspaceState:
    if project_dir.is_symlink():
        raise RuntimeError(f"Wokwi workspace must not be a symlink: {project_dir}")
    if not project_dir.exists():
        return WorkspaceState(False, frozenset())
    if not project_dir.is_dir():
        raise RuntimeError(f"Wokwi workspace path is not a directory: {project_dir}")
    if not any(project_dir.iterdir()):
        return WorkspaceState(False, frozenset())

    marker_path = project_dir / WORKSPACE_MARKER
    if marker_path.is_symlink() or not marker_path.is_file():
        raise RuntimeError(
            f"Refusing to update unmanaged Wokwi workspace: {project_dir}. "
            f"Remove it or choose an empty directory."
        )

    marker_text = marker_path.read_text(encoding="utf-8").strip()
    if not marker_text:
        missing = [
            name
            for name in LEGACY_WORKSPACE_FILES
            if not (project_dir / name).is_file()
        ]
        if missing:
            raise RuntimeError(
                f"Invalid legacy Wokwi workspace marker in {project_dir}: "
                f"missing {', '.join(sorted(missing))}"
            )
        return WorkspaceState(True, frozenset())

    try:
        marker = json.loads(marker_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid Wokwi workspace marker: {marker_path}") from exc

    if not isinstance(marker, dict):
        raise RuntimeError(f"Invalid Wokwi workspace marker: {marker_path}")
    if (
        marker.get("generator") != MARKER_GENERATOR
        or marker.get("version") != MARKER_VERSION
    ):
        raise RuntimeError(f"Unsupported Wokwi workspace marker: {marker_path}")

    raw_managed_files = marker.get("managedFiles")
    if not isinstance(raw_managed_files, list) or not all(
        isinstance(path, str) for path in raw_managed_files
    ):
        raise RuntimeError(
            f"Invalid managed file list in Wokwi workspace marker: {marker_path}"
        )
    managed_files = frozenset(safe_relative_path(path) for path in raw_managed_files)
    return WorkspaceState(False, managed_files)


def copy_template(template_dir: Path, staging_dir: Path) -> None:
    for source in sorted(template_dir.rglob("*")):
        relative_path = source.relative_to(template_dir)
        if any(part in IGNORED_TEMPLATE_PARTS for part in relative_path.parts):
            continue
        if source.is_symlink():
            raise RuntimeError(f"Wokwi template must not contain symlinks: {source}")
        if not source.is_file() or source.name in TEMPLATE_FILES:
            continue
        if relative_path == Path("scripts/prepare_workspace.py"):
            continue
        if relative_path.name == WORKSPACE_MARKER:
            continue
        destination = staging_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def render_staging_workspace(
    template_dir: Path,
    staging_dir: Path,
    project_dir: Path,
    app_src_dir: Path,
    app_config_path: Path | None,
) -> frozenset[Path]:
    copy_template(template_dir, staging_dir)

    app_config = ""
    if app_config_path is not None:
        if not app_config_path.is_file():
            raise RuntimeError(f"Wokwi application config not found: {app_config_path}")
        (staging_dir / ".gar-app.ini").write_text(
            app_config_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        app_config = "extra_configs = .gar-app.ini"

    app_src = Path(os.path.relpath(app_src_dir, project_dir)).as_posix()
    platformio_template = template_dir / "platformio.ini.template"
    (staging_dir / "platformio.ini").write_text(
        platformio_template.read_text(encoding="utf-8").format(
            app_src=app_src,
            app_config=app_config,
        ),
        encoding="utf-8",
    )

    firmware = os.environ.get("GAR_WOKWI_FIRMWARE", ".pio/build/m5stackc/firmware.bin")
    elf = os.environ.get("GAR_WOKWI_ELF", ".pio/build/m5stackc/firmware.elf")
    wokwi_template = template_dir / "wokwi.toml.template"
    (staging_dir / "wokwi.toml").write_text(
        wokwi_template.read_text(encoding="utf-8").format(firmware=firmware, elf=elf),
        encoding="utf-8",
    )

    return frozenset(
        path.relative_to(staging_dir)
        for path in staging_dir.rglob("*")
        if path.is_file()
    )


def marker_text(managed_files: frozenset[Path]) -> str:
    marker = {
        "generator": MARKER_GENERATOR,
        "version": MARKER_VERSION,
        "managedFiles": sorted(path.as_posix() for path in managed_files),
    }
    return json.dumps(marker, indent=2) + "\n"


def validate_destination(
    project_dir: Path,
    relative_path: Path,
    replaceable_files: frozenset[Path],
    stale_files: frozenset[Path],
) -> None:
    current = project_dir
    for part in relative_path.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Refusing to follow workspace symlink: {current}")
        if current.exists() and not current.is_dir():
            current_relative = current.relative_to(project_dir)
            if current_relative not in stale_files:
                raise RuntimeError(
                    f"Workspace path blocks generated directory: {current}"
                )

    destination = project_dir / relative_path
    if destination.is_symlink():
        raise RuntimeError(f"Refusing to replace workspace symlink: {destination}")
    if destination.exists() and destination.is_dir():
        raise RuntimeError(
            f"Generated workspace file conflicts with a directory: {destination}"
        )
    if destination.exists() and relative_path not in replaceable_files:
        raise RuntimeError(
            f"Generated workspace file conflicts with an unmanaged file: {destination}"
        )


def validate_stale_destination(project_dir: Path, relative_path: Path) -> None:
    """Ensure removing an obsolete generated file cannot follow a user symlink."""

    current = project_dir
    for part in relative_path.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Refusing to follow workspace symlink: {current}")
        if current.exists() and not current.is_dir():
            raise RuntimeError(f"Workspace path blocks managed file removal: {current}")

    destination = project_dir / relative_path
    if destination.exists() and destination.is_dir() and not destination.is_symlink():
        raise RuntimeError(f"Managed workspace file became a directory: {destination}")


def remove_stale_file(project_dir: Path, relative_path: Path) -> None:
    destination = project_dir / relative_path
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.exists():
        raise RuntimeError(f"Managed workspace file became a directory: {destination}")

    parent = destination.parent
    while parent != project_dir:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def install_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        shutil.copy2(source, temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def synchronize_workspace(
    staging_dir: Path,
    project_dir: Path,
    state: WorkspaceState,
    managed_files: frozenset[Path],
) -> None:
    stale_files = state.managed_files - managed_files
    if state.legacy_marker:
        replaceable_files = frozenset(
            path for path in managed_files if (project_dir / path).is_file()
        )
    else:
        replaceable_files = state.managed_files

    for relative_path in managed_files:
        validate_destination(project_dir, relative_path, replaceable_files, stale_files)
    for relative_path in stale_files:
        validate_stale_destination(project_dir, relative_path)

    project_dir.mkdir(parents=True, exist_ok=True)
    # Publish a recovery marker before the first mutation.  If an I/O failure or
    # interruption leaves a partially updated workspace, the next run still
    # owns both the old and new generated files and can finish the transition.
    recovery_marker = staging_dir / ".gar-recovery-marker"
    recovery_marker.write_text(
        marker_text(state.managed_files | managed_files),
        encoding="utf-8",
    )
    install_file(recovery_marker, project_dir / WORKSPACE_MARKER)
    for relative_path in sorted(
        stale_files, key=lambda path: len(path.parts), reverse=True
    ):
        remove_stale_file(project_dir, relative_path)
    for relative_path in sorted(managed_files):
        install_file(staging_dir / relative_path, project_dir / relative_path)
    install_file(
        staging_dir / WORKSPACE_MARKER,
        project_dir / WORKSPACE_MARKER,
    )


def render_workspace(
    template_dir: Path,
    project_dir: Path,
    app_src_dir: Path,
    app_config_path: Path | None,
) -> None:
    template_dir = template_dir.resolve()
    project_dir = project_dir.expanduser().absolute()
    reject_symlink_path(project_dir, "Wokwi workspace path")
    project_dir = project_dir.resolve()
    app_src_dir = app_src_dir.resolve()
    app_config_path = app_config_path.resolve() if app_config_path is not None else None

    validate_workspace_paths(template_dir, project_dir, app_src_dir, app_config_path)
    state = read_workspace_state(project_dir)
    project_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=f".{project_dir.name}.staging-", dir=project_dir.parent
    ) as temporary_directory:
        staging_dir = Path(temporary_directory)
        managed_files = render_staging_workspace(
            template_dir,
            staging_dir,
            project_dir,
            app_src_dir,
            app_config_path,
        )
        (staging_dir / WORKSPACE_MARKER).write_text(
            marker_text(managed_files), encoding="utf-8"
        )
        synchronize_workspace(staging_dir, project_dir, state, managed_files)


def main() -> int:
    template_dir = environment_path(
        "GAR_WOKWI_TEMPLATE_DIR", Path(__file__).resolve().parents[1]
    )
    project_dir = environment_path("GAR_WOKWI_PROJECT_DIR")
    app_src_dir = environment_path("GAR_WOKWI_APP_SRC_DIR")
    raw_app_config = os.environ.get("GAR_WOKWI_APP_CONFIG")
    app_config_path = (
        Path(raw_app_config).expanduser().resolve() if raw_app_config else None
    )

    if not template_dir.is_dir():
        raise RuntimeError(f"Wokwi template directory not found: {template_dir}")
    if not app_src_dir.is_dir():
        raise RuntimeError(
            f"Wokwi application source directory not found: {app_src_dir}"
        )

    render_workspace(template_dir, project_dir, app_src_dir, app_config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
