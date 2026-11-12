"""Build, preflight, deploy and diagnose a Product-declared script update."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

from configure import files_of


def main(settings, phase):
    root = Path(settings.pop("root")).resolve()
    directory = root / ".gar/runtime-updates"
    directory.mkdir(parents=True, exist_ok=True)
    current = directory / "current.json"
    if phase == "build":
        artifact = {
            "schema_version": 1,
            "kind": "GAR_RUNTIME_SCRIPT_UPDATE",
            "files": {},
            "sources": {},
        }
        for name in settings["files"]:
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ValueError("source_outside_product")
            content = path.read_bytes()
            artifact["files"][name] = {
                "sha256": hashlib.sha256(content).hexdigest(),
                "contentBase64": base64.b64encode(content).decode(),
            }
        for name in settings["sourceRepositories"]:
            repository = root / name
            commit = subprocess.check_output(
                ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
            ).strip()
            paths = [
                str((root / item).relative_to(repository))
                for item in settings["files"]
                if (root / item).is_relative_to(repository)
            ]
            dirty = bool(
                subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(repository),
                        "status",
                        "--porcelain",
                        "--",
                        *paths,
                    ],
                    text=True,
                ).strip()
            )
            artifact["sources"][name] = {"commit": commit, "updatedFilesDirty": dirty}
        artifact["buildId"] = hashlib.sha256(
            json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        files_of(artifact)
        snapshot = directory / (artifact["buildId"] + ".json")
        if not snapshot.exists():
            snapshot.write_text(json.dumps(artifact), encoding="utf-8")
        elif json.loads(snapshot.read_text()) != artifact:
            raise ValueError("immutable_snapshot_changed")
        current.write_text(
            json.dumps({"buildId": artifact["buildId"]}), encoding="utf-8"
        )
        return {
            "ok": True,
            "state": "built",
            "deployment": {
                "expectedBuildId": artifact["buildId"],
                "fileCount": len(artifact["files"]),
                "nativeFilesChanged": False,
            },
        }
    build_id = json.loads(current.read_text())["buildId"]
    artifact = json.loads((directory / (build_id + ".json")).read_text())
    files_of(artifact)
    if sorted(artifact["files"]) != sorted(settings["files"]):
        raise ValueError("update_binding_changed")
    if any(value["updatedFilesDirty"] for value in artifact["sources"].values()):
        raise ValueError("commit_updated_files_before_deployment")
    settings.update(phase=phase, artifact=artifact)
    preflight = directory / (build_id + ".preflight.json")
    if phase == "deploy":
        settings["preflight"] = json.loads(preflight.read_text())
        request = directory / (build_id + ".request.json")
        request.write_text(
            json.dumps(
                {
                    "artifact": artifact,
                    "preflight": settings["preflight"],
                    "phase": phase,
                }
            ),
            encoding="utf-8",
        )
        # The GUI receives only paths/settings in argv; public source payloads
        # are read there and travel over SSH stdin after sudo authentication.
        del settings["artifact"], settings["preflight"]
        settings.update(
            payloadFile=str(request),
            resultFile=str(directory / "deploy-result.json"),
            recipeSource=str(Path(__file__).with_name("configure.py")),
            check=False,
        )
        return subprocess.call(
            [
                sys.executable,
                str(Path(__file__).parents[1] / "audio/setup.py"),
                json.dumps(settings),
            ]
        )
    source = base64.b64encode(
        Path(__file__).with_name("configure.py").read_bytes()
    ).decode()
    command = shlex.join(
        [
            "python3",
            "-c",
            "import base64;exec(compile(base64.b64decode("
            + repr(source)
            + "),'<runtime-update>','exec'))",
        ]
    )
    # Read-only validation also verifies the public source snapshot. It travels
    # on stdin rather than in a shell argument; no credentials are in it.
    result = subprocess.run(
        [
            "ssh",
            "-T",
            "-i",
            settings["sshKey"],
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=6",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + settings["knownHosts"],
            settings["sshUser"] + "@" + settings["sshHost"],
            command,
        ],
        input=json.dumps(settings) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    lines = [
        line.removeprefix("__GAR_WIFI_RESULT__")
        for line in result.stdout.splitlines()
        if line.startswith("__GAR_WIFI_RESULT__")
    ]
    if result.returncode or not lines:
        return {
            "ok": False,
            "state": "failed",
            "error": "target_update_observation_failed",
        }
    report = json.loads(lines[-1])
    if phase == "preflight" and report.get("ok"):
        preflight.write_text(json.dumps(report["preflight"]), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings")
    parser.add_argument("--transport", choices=["ssh"], default="ssh")
    parser.add_argument(
        "--phase", choices=["build", "preflight", "deploy", "diag"], required=True
    )
    args = parser.parse_args()
    try:
        result = main(json.loads(args.settings), args.phase)
    except Exception:
        result = {"ok": False, "state": "failed", "error": "runtime_update_failed"}
    if isinstance(result, int):
        raise SystemExit(result)
    print(json.dumps(result))
    raise SystemExit(0 if result.get("ok") else 1)
