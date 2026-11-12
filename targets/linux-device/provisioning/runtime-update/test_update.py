import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "runtime_update", Path(__file__).with_name("configure.py")
)
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


def artifact(files):
    value = {
        "schema_version": 1,
        "kind": "GAR_RUNTIME_SCRIPT_UPDATE",
        "sources": {},
        "files": {
            name: {
                "sha256": hashlib.sha256(data).hexdigest(),
                "contentBase64": base64.b64encode(data).decode(),
            }
            for name, data in files.items()
        },
    }
    value["buildId"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


class UpdateTests(unittest.TestCase):
    def test_corruption_and_non_script_paths_rejected(self):
        for name in (
            "../outside.cjs",
            "/absolute.cjs",
            "C:/outside.cjs",
            "hardware/wiring.csv",
            "native.bin",
        ):
            with self.assertRaises(ValueError):
                provider.files_of(artifact({name: b"public code"}))
        value = artifact({"app.cjs": b"public code"})
        value["files"]["app.cjs"]["contentBase64"] = base64.b64encode(
            b"corrupt"
        ).decode()
        with self.assertRaises(ValueError):
            provider.files_of(value)

    def transaction(self, failure=None, stale=False):
        with tempfile.TemporaryDirectory(prefix="gar-script-update-test-") as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            previous = root / "releases/base"
            previous.mkdir(parents=True)
            (previous / "app.cjs").write_bytes(b"module.exports='old';")
            (previous / "native.bin").write_bytes(b"UNCHANGED_NATIVE")
            (root / "private.env").write_bytes(b"UNCHANGED_PRIVATE")
            value = artifact(
                {
                    "app.cjs": b"module.exports='new';",
                    "extra.cjs": b"module.exports=true;",
                }
            )
            settings = {
                "deployRoot": str(root),
                "service": "example.service",
                "node": "node",
                "artifact": value,
            }
            current = {"release": previous, "pid": 10}

            def inspect(_):
                return {
                    "release": str(current["release"]),
                    "pid": current["pid"],
                    "active": True,
                    "hashes": {
                        name: provider.digest(current["release"] / name)
                        for name in value["files"]
                    },
                }

            settings["preflight"] = inspect(settings)
            if stale:
                (previous / "app.cjs").write_bytes(b"changed_since_preflight")
            links = {}

            def symlink(path, target, **_):
                links[str(path)] = Path(target)

            def replace(source, target):
                self.assertEqual(Path(target), root / "app")
                current["release"] = links.pop(str(source))

            calls = []

            def run(command, **_):
                calls.append(command)
                if "--check" in command and failure == "syntax":
                    raise subprocess.CalledProcessError(1, command)
                if command[:2] == ["systemctl", "restart"]:
                    if failure == "restart" and current["release"] != previous:
                        raise subprocess.CalledProcessError(1, command)
                    current["pid"] += 1
                return subprocess.CompletedProcess(command, 0)

            with patch.object(
                provider.os, "geteuid", return_value=0, create=True
            ), patch.object(provider, "inspect", side_effect=inspect), patch.object(
                Path, "symlink_to", symlink
            ), patch.object(provider.os, "replace", side_effect=replace), patch.object(
                provider.subprocess, "run", side_effect=run
            ):
                if stale or failure == "syntax":
                    with self.assertRaises(
                        (RuntimeError, subprocess.CalledProcessError)
                    ):
                        provider.deploy(settings)
                    self.assertEqual(current["release"], previous)
                    self.assertFalse(any(call[0] == "systemctl" for call in calls))
                else:
                    result = provider.deploy(settings)
                    self.assertEqual(result["ok"], failure is None)
                    if failure:
                        self.assertEqual(result["state"], "rolled_back")
                        self.assertEqual(current["release"], previous)
                    else:
                        self.assertNotEqual(current["release"], previous)
                        self.assertEqual(
                            (current["release"] / "app.cjs").read_bytes(),
                            b"module.exports='new';",
                        )
                        self.assertEqual(
                            (current["release"] / "native.bin").read_bytes(),
                            b"UNCHANGED_NATIVE",
                        )
                        self.assertTrue(
                            provider.diagnose(settings)["deployment"]["matched"]
                        )
            self.assertEqual((root / "private.env").read_bytes(), b"UNCHANGED_PRIVATE")
            self.assertEqual(
                (previous / "native.bin").read_bytes(), b"UNCHANGED_NATIVE"
            )

    def test_script_update_preserves_native_files_and_private_config(self):
        self.transaction()

    def test_restart_failure_restores_previous_release(self):
        self.transaction(failure="restart")

    def test_syntax_failure_does_not_switch_or_restart(self):
        self.transaction(failure="syntax")

    def test_changed_baseline_refuses_install(self):
        self.transaction(stale=True)


if __name__ == "__main__":
    unittest.main()
