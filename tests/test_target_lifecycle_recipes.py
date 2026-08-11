from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI_HELPER = (
    ROOT
    / "targets"
    / "raspberry-pi-5"
    / "provisioning"
    / "raspberry-pi-os-systemd"
    / "gar-target-lifecycle"
)
LYRA_HELPER = (
    ROOT
    / "targets"
    / "luckfox-rk3506"
    / "provisioning"
    / "buildroot-busybox"
    / "gar-target-lifecycle"
)


class TargetLifecycleRecipeTests(unittest.TestCase):
    def test_systemd_recipe_converges_and_reports_the_verified_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = self._systemd_sandbox(root)
            self._exercise_contract(helper, root)

    def test_busybox_recipe_converges_and_reports_the_verified_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = self._busybox_sandbox(root)
            self._exercise_contract(helper, root)
            (root / "state" / "demo.reboot-required").write_text("demo\n", encoding="utf-8")

            reboot_required = self._run(
                helper,
                "reload",
                "demo",
                "--build-id",
                "build:two",
            )

            self.assertEqual(1, reboot_required.returncode)
            self.assertIn("target reboot is required", reboot_required.stderr)
            self.assertFalse((root / "state" / "demo.build-id").exists())

    def test_helpers_reject_unsafe_application_names_and_build_ids(self) -> None:
        for helper in (PI_HELPER, LYRA_HELPER):
            with self.subTest(helper=helper):
                invalid_app = subprocess.run(
                    (str(helper), "status", "../escape"),
                    check=False,
                    capture_output=True,
                    text=True,
                )
                invalid_build = subprocess.run(
                    (str(helper), "reload", "demo", "--build-id", "bad id"),
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(2, invalid_app.returncode)
                self.assertIn("invalid application name", invalid_app.stderr)
                self.assertEqual(2, invalid_build.returncode)
                self.assertIn("invalid build ID", invalid_build.stderr)

    def _exercise_contract(self, helper: Path, root: Path) -> None:
        app = root / "apps" / "demo"
        app.mkdir(parents=True)
        self._write_executable(app / "run", "#!/bin/sh\nexit 0\n")
        self._write_executable(app / "health", "#!/bin/sh\nexit 0\n")
        marker = app / ".gar-artifact.json"
        marker.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "kind": "target_app",
                    "build_id": "build:one",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        reload_result = self._run(helper, "reload", "demo", "--build-id", "build:one")
        self.assertEqual(0, reload_result.returncode, reload_result.stderr)
        self.assertIn("running build build:one", reload_result.stdout)

        status = self._run(helper, "status", "demo")
        health = self._run(helper, "health", "demo")
        running = self._run(helper, "running-build-id", "demo")
        logs = self._run(helper, "log", "demo", "--lines", "12")
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertIn("demo is running", status.stdout)
        self.assertEqual(0, health.returncode, health.stderr)
        self.assertIn("demo is healthy", health.stdout)
        self.assertEqual(0, running.returncode, running.stderr)
        self.assertEqual("build:one", running.stdout.strip())
        self.assertEqual(0, logs.returncode, logs.stderr)
        self.assertIn("lifecycle test log", logs.stdout)

        marker.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "kind": "target_app",
                    "build_id": "build:two",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        stale = self._run(helper, "running-build-id", "demo")
        self.assertEqual(1, stale.returncode)
        self.assertIn("does not match", stale.stderr)

    def _systemd_sandbox(self, root: Path) -> Path:
        bin_dir = root / "bin"
        bin_dir.mkdir()
        running = root / "systemd-running"
        systemctl = bin_dir / "systemctl"
        self._write_executable(
            systemctl,
            "#!/bin/sh\n"
            f"running={shlex.quote(str(running))}\n"
            'case "$1" in\n'
            '  is-active) [ -f "$running" ] ;;\n'
            '  restart) : >"$running" ;;\n'
            "  *) exit 2 ;;\n"
            "esac\n",
        )
        journalctl = bin_dir / "journalctl"
        self._write_executable(journalctl, "#!/bin/sh\necho lifecycle test log\n")
        runuser = bin_dir / "runuser"
        self._write_executable(runuser, "#!/bin/sh\nshift 3\nexec \"$@\"\n")

        replacements = {
            "apps_root=/opt/gar/apps": f"apps_root={shlex.quote(str(root / 'apps'))}",
            "state_root=/var/lib/gar-target/state": f"state_root={shlex.quote(str(root / 'state'))}",
            "systemctl=/usr/bin/systemctl": f"systemctl={shlex.quote(str(systemctl))}",
            "journalctl=/usr/bin/journalctl": f"journalctl={shlex.quote(str(journalctl))}",
            "runuser=/usr/sbin/runuser": f"runuser={shlex.quote(str(runuser))}",
        }
        return self._sandbox_helper(PI_HELPER, root, replacements)

    def _busybox_sandbox(self, root: Path) -> Path:
        init_root = root / "init.d"
        init_root.mkdir()
        running = root / "busybox-running"
        self._write_executable(
            init_root / "S95gar-demo",
            "#!/bin/sh\n"
            f"running={shlex.quote(str(running))}\n"
            'case "$1" in\n'
            '  status) [ -f "$running" ] ;;\n'
            '  restart) : >"$running" ;;\n'
            "  *) exit 2 ;;\n"
            "esac\n",
        )
        log_root = root / "log"
        log_root.mkdir()
        (log_root / "demo.log").write_text("lifecycle test log\n", encoding="utf-8")
        replacements = {
            "apps_root=/opt/gar/apps": f"apps_root={shlex.quote(str(root / 'apps'))}",
            "state_root=/var/lib/gar-target/state": f"state_root={shlex.quote(str(root / 'state'))}",
            "init_root=/etc/init.d": f"init_root={shlex.quote(str(init_root))}",
            "log_root=/var/log/gar": f"log_root={shlex.quote(str(log_root))}",
        }
        return self._sandbox_helper(LYRA_HELPER, root, replacements)

    def _sandbox_helper(
        self,
        source: Path,
        root: Path,
        replacements: dict[str, str],
    ) -> Path:
        content = source.read_text(encoding="utf-8")
        for original, replacement in replacements.items():
            self.assertIn(original, content)
            content = content.replace(original, replacement, 1)
        helper = root / f"{source.parent.parent.name}-lifecycle"
        self._write_executable(helper, content)
        return helper

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o755)

    @staticmethod
    def _run(helper: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (str(helper), *args),
            check=False,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
