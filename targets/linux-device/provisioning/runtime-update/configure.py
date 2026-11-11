"""Hash-checked Node script updates; keep the base native payload and private config."""

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def files_of(artifact):
    if (
        artifact.get("kind") != "GAR_RUNTIME_SCRIPT_UPDATE"
        or artifact.get("schema_version") != 1
    ):
        raise ValueError("invalid_update_artifact")
    unsigned = {key: value for key, value in artifact.items() if key != "buildId"}
    if (
        hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != artifact["buildId"]
    ):
        raise ValueError("artifact_digest_mismatch")
    files = artifact["files"]
    if not 1 <= len(files) <= 32:
        raise ValueError("invalid_file_count")
    total = 0
    for name, entry in files.items():
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or relative.suffix not in (".cjs", ".mjs", ".js")
        ):
            raise ValueError("invalid_script_path")
        data = base64.b64decode(entry["contentBase64"], validate=True)
        total += len(data)
        if hashlib.sha256(data).hexdigest() != entry["sha256"] or total > 1024 * 1024:
            raise ValueError("invalid_script_content")
    return files


def target_file(root, relative):
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("script_path_escapes_release")
    return result


def service_state(settings):
    values = subprocess.check_output(
        [
            "systemctl",
            "show",
            settings["service"],
            "-p",
            "MainPID",
            "-p",
            "ActiveState",
        ],
        text=True,
        timeout=8,
    )
    return dict(line.split("=", 1) for line in values.splitlines() if "=" in line)


def inspect(settings):
    root = Path(settings["deployRoot"])
    if not root.is_absolute() or root == Path("/"):
        raise ValueError("invalid_deploy_root")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}\.service", settings["service"]):
        raise ValueError("invalid_service")
    if platform.machine() != settings["architecture"]:
        raise ValueError("architecture_mismatch")
    active = root / "app"
    release = active.resolve(strict=True)
    if (
        not active.is_symlink()
        or not release.is_relative_to((root / "releases").resolve())
        or not release.is_dir()
    ):
        raise ValueError("unexpected_active_release")
    files = files_of(settings["artifact"])
    hashes = {name: digest(target_file(release, name)) for name in files}
    state = service_state(settings)
    launch = subprocess.check_output(
        ["systemctl", "show", settings["service"], "-p", "ExecStart", "--value"],
        text=True,
        timeout=8,
    )
    if str(active) + "/" not in launch:
        raise ValueError("service_not_bound_to_active_release")
    return {
        "release": str(release),
        "hashes": hashes,
        "pid": int(state.get("MainPID", 0)),
        "active": state.get("ActiveState") == "active",
    }


def diagnose(settings):
    observed = inspect(settings)
    receipt = Path(observed["release"]) / ".gar-runtime-update.json"
    running = (
        json.loads(receipt.read_text()).get("buildId") if receipt.is_file() else None
    )
    expected = settings["artifact"]["buildId"]
    matched = (
        observed["active"]
        and running == expected
        and all(
            observed["hashes"][name] == entry["sha256"]
            for name, entry in settings["artifact"]["files"].items()
        )
    )
    return {
        "ok": matched,
        "state": "running" if matched else "mismatch",
        "deployment": {
            "expectedBuildId": expected,
            "runningBuildId": running,
            "matched": matched,
            "pid": observed["pid"],
        },
    }


def deploy(settings):
    if os.geteuid() != 0:
        raise RuntimeError("root_required")
    observed = inspect(settings)
    if diagnose(settings)["ok"]:
        return diagnose(settings)
    baseline = settings["preflight"]
    if (
        not observed["active"]
        or observed["release"] != baseline["release"]
        or observed["hashes"] != baseline["hashes"]
    ):
        raise RuntimeError("preflight_changed_rebuild_required")
    root = Path(settings["deployRoot"])
    previous = Path(observed["release"])
    release = root / "releases" / ("scripts-" + settings["artifact"]["buildId"][:24])
    if release.exists():
        raise RuntimeError("release_already_exists")
    shutil.copytree(previous, release, symlinks=True)
    for name, entry in settings["artifact"]["files"].items():
        destination = target_file(release, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(entry["contentBase64"], validate=True))
        destination.chmod(0o644)
        subprocess.run(
            [settings["node"], "--check", str(destination)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        if settings.get("validateImports"):
            owner = subprocess.check_output(
                ["systemctl", "show", settings["service"], "-p", "User", "--value"],
                text=True,
                timeout=8,
            ).strip()
            if not re.fullmatch(r"[a-z_][a-z0-9_-]*", owner) or owner == "root":
                raise ValueError("nonroot_service_user_required")
            subprocess.run(
                [
                    "runuser",
                    "-u",
                    owner,
                    "--",
                    settings["node"],
                    "--input-type=module",
                    "-e",
                    "await import(process.argv[1])",
                    destination.as_uri(),
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
    receipt = {
        "buildId": settings["artifact"]["buildId"],
        "previousRelease": str(previous),
        "previousPid": observed["pid"],
        "sources": settings["artifact"].get("sources", {}),
    }
    (release / ".gar-runtime-update.json").write_text(json.dumps(receipt))
    temporary = root / (".app-" + uuid.uuid4().hex)
    temporary.symlink_to(release, target_is_directory=True)
    os.replace(temporary, root / "app")
    try:
        subprocess.run(
            ["systemctl", "restart", settings["service"]],
            check=True,
            capture_output=True,
            timeout=30,
        )
        for _ in range(30):
            result = diagnose(settings)
            if result["ok"] and result["deployment"]["pid"] not in (0, observed["pid"]):
                return result
            time.sleep(1)
        raise RuntimeError("updated_service_not_healthy")
    except Exception:
        temporary.symlink_to(previous, target_is_directory=True)
        os.replace(temporary, root / "app")
        subprocess.run(
            ["systemctl", "restart", settings["service"]],
            capture_output=True,
            timeout=30,
        )
        return {
            "ok": False,
            "state": "rolled_back",
            "error": "updated_service_not_healthy",
            "deployment": {"rolledBack": True},
        }


def run(settings):
    if settings["phase"] == "preflight":
        result = inspect(settings)
        return {"ok": result["active"], "state": "compatible", "preflight": result}
    if settings["phase"] == "diag":
        return diagnose(settings)
    if settings["phase"] == "deploy":
        return deploy(settings)
    raise ValueError("invalid_update_phase")


if __name__ == "__main__":
    print("__GAR_WIFI_INPUT__", flush=True)
    try:
        result = run(json.loads(sys.stdin.readline()))
    except Exception as error:
        message = str(error)
        result = {
            "ok": False,
            "state": "failed",
            "error": message
            if re.fullmatch(r"[a-z_]+", message)
            else "runtime_update_failed",
        }
    print("__GAR_WIFI_RESULT__" + json.dumps(result), flush=True)
