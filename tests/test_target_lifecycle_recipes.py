from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import tempfile
import time
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
LYRA_LAUNCHER = LYRA_HELPER.with_name("gar-app@.service")
PI_INSTALLER = PI_HELPER.with_name("gar-target-install")
LYRA_INSTALLER = LYRA_HELPER.with_name("gar-target-install")


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

    def test_lifecycle_keeps_reading_the_legacy_marker_name(self) -> None:
        for sandbox_factory in (self._systemd_sandbox, self._busybox_sandbox):
            with self.subTest(sandbox=sandbox_factory.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                helper = sandbox_factory(root)
                self._exercise_contract(helper, root, marker_name=".gar-artifact.json")

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

    def test_busybox_stop_rejects_reused_pid_identity_without_killing_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app_dir = root / "apps" / "demo"
            app_dir.mkdir(parents=True)
            pid_file = root / "gar-demo.pid"
            log_dir = root / "log"
            reboot_required = root / "state" / "demo.reboot-required"
            content = LYRA_LAUNCHER.read_text(encoding="utf-8")
            replacements = {
                "app=@GAR_APP@": "app=demo",
                'app_dir="/opt/gar/apps/$app"': f"app_dir={shlex.quote(str(app_dir))}",
                'pid_file="/var/run/gar-$app.pid"': f"pid_file={shlex.quote(str(pid_file))}",
                "log_dir=/var/log/gar": f"log_dir={shlex.quote(str(log_dir))}",
                'reboot_required_file="/var/lib/gar-target/state/$app.reboot-required"': (
                    f"reboot_required_file={shlex.quote(str(reboot_required))}"
                ),
            }
            for original, replacement in replacements.items():
                self.assertIn(original, content)
                content = content.replace(original, replacement, 1)
            launcher = root / "S95gar-demo"
            self._write_executable(launcher, content)

            unrelated = subprocess.Popen(("sleep", "30"))
            try:
                pid_file.write_text(f"{unrelated.pid} 0\n", encoding="utf-8")

                stopped = self._run(launcher, "stop")

                self.assertEqual(0, stopped.returncode, stopped.stderr)
                self.assertIsNone(unrelated.poll())
                self.assertFalse(pid_file.exists())
            finally:
                if unrelated.poll() is None:
                    unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_busybox_stop_terminates_the_recorded_process_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app_dir = root / "apps" / "demo"
            app_dir.mkdir(parents=True)
            self._write_executable(app_dir / "run", "#!/bin/sh\nexec sleep 30\n")
            pid_file = root / "gar-demo.pid"
            log_dir = root / "log"
            reboot_required = root / "state" / "demo.reboot-required"
            content = LYRA_LAUNCHER.read_text(encoding="utf-8")
            replacements = {
                "app=@GAR_APP@": "app=demo",
                'app_dir="/opt/gar/apps/$app"': f"app_dir={shlex.quote(str(app_dir))}",
                'pid_file="/var/run/gar-$app.pid"': f"pid_file={shlex.quote(str(pid_file))}",
                "log_dir=/var/log/gar": f"log_dir={shlex.quote(str(log_dir))}",
                'reboot_required_file="/var/lib/gar-target/state/$app.reboot-required"': (
                    f"reboot_required_file={shlex.quote(str(reboot_required))}"
                ),
            }
            for original, replacement in replacements.items():
                self.assertIn(original, content)
                content = content.replace(original, replacement, 1)
            launcher = root / "S95gar-demo"
            self._write_executable(launcher, content)

            started = self._run(launcher, "start")
            self.assertEqual(0, started.returncode, started.stderr)
            pid_text, start_time = pid_file.read_text(encoding="utf-8").split()
            pid = int(pid_text)
            self.assertGreater(int(start_time), 0)
            try:
                stopped = self._run(launcher, "stop")

                self.assertEqual(0, stopped.returncode, stopped.stderr)
                self.assertFalse(pid_file.exists())
                deadline = time.monotonic() + 2
                while Path(f"/proc/{pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertFalse(Path(f"/proc/{pid}").exists())
            finally:
                if Path(f"/proc/{pid}").exists():
                    os.kill(pid, signal.SIGKILL)

    def test_installers_harden_only_app_root_and_provenance_marker_modes(self) -> None:
        for source_installer in (PI_INSTALLER, LYRA_INSTALLER):
            with self.subTest(installer=source_installer), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                installer = self._sandbox_installer(source_installer, root)
                destination = root / "apps" / "demo"
                with tempfile.TemporaryDirectory(prefix="gar-stage-") as stage:
                    payload = Path(stage) / "payload"
                    payload.mkdir()
                    marker = payload / ".artifact-info.json"
                    marker.write_text('{"build_id":"build:one"}\n', encoding="utf-8")
                    marker.chmod(0o666)
                    run = payload / "run"
                    self._write_executable(run, "#!/bin/sh\nexit 0\n")
                    run.chmod(0o751)

                    result = subprocess.run(
                        (str(installer), "install", str(payload), str(destination), "0777"),
                        check=False,
                        capture_output=True,
                        text=True,
                    )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(0, destination.stat().st_mode & 0o022)
                self.assertEqual(0o444, (destination / ".artifact-info.json").stat().st_mode & 0o777)
                self.assertEqual(0o751, (destination / "run").stat().st_mode & 0o777)

    def test_installers_keep_previous_destination_when_staging_copy_fails(self) -> None:
        for source_installer in (PI_INSTALLER, LYRA_INSTALLER):
            with self.subTest(installer=source_installer), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                installer = self._sandbox_installer(source_installer, root)
                destination = root / "apps" / "demo"
                destination.mkdir(parents=True)
                (destination / "old-release").write_text("old\n", encoding="utf-8")
                fake_bin = root / "bin"
                fake_bin.mkdir()
                self._write_executable(fake_bin / "cp", "#!/bin/sh\nexit 9\n")
                environment = os.environ.copy()
                environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
                with tempfile.TemporaryDirectory(prefix="gar-stage-") as stage:
                    payload = Path(stage) / "payload"
                    payload.mkdir()
                    (payload / "run").write_text("new\n", encoding="utf-8")

                    result = subprocess.run(
                        (str(installer), "install", str(payload), str(destination), "0755"),
                        check=False,
                        capture_output=True,
                        text=True,
                        env=environment,
                    )

                self.assertEqual(2, result.returncode)
                self.assertEqual("old\n", (destination / "old-release").read_text(encoding="utf-8"))
                self.assertEqual([], list((root / "apps").glob("demo.gar-*")))

    def test_installers_allow_only_exact_runtime_environment_destination(self) -> None:
        for source_installer in (PI_INSTALLER, LYRA_INSTALLER):
            with self.subTest(installer=source_installer), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                installer = self._sandbox_installer(source_installer, root)
                runtime_destination = root / "system" / "demo.env"
                with tempfile.TemporaryDirectory(prefix="gar-stage-") as stage:
                    payload = Path(stage) / "payload"
                    payload.write_text("OVERRIDE=runtime\n", encoding="utf-8")
                    installed = self._run(installer, "install", str(payload), str(runtime_destination), "0644")
                    nested = self._run(
                        installer,
                        "install",
                        str(payload),
                        str(root / "system" / "nested" / "demo.env"),
                        "0644",
                    )
                    unsafe_mode = self._run(
                        installer, "install", str(payload), str(runtime_destination), "0600"
                    )

                self.assertEqual(0, installed.returncode, installed.stderr)
                self.assertEqual("OVERRIDE=runtime\n", runtime_destination.read_text(encoding="utf-8"))
                self.assertEqual(0o644, runtime_destination.stat().st_mode & 0o777)
                self.assertEqual(2, nested.returncode)
                self.assertIn("destination is not permitted", nested.stderr)
                self.assertEqual(2, unsafe_mode.returncode)
                self.assertIn("require mode 0644", unsafe_mode.stderr)

    def test_busybox_runtime_environment_overrides_persistent_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app_dir = root / "apps" / "demo"
            app_dir.mkdir(parents=True)
            output = root / "environment.txt"
            command_substitution_marker = root / "must-not-exist"
            self._write_executable(
                app_dir / "run",
                "#!/bin/sh\n"
                f"printf '%s|%s|%s|%s\\n' \"$PERSISTENT\" \"$OVERRIDE\" \"$RUNTIME\" \"$UNSAFE\" > {shlex.quote(str(output))}\n"
                "exec sleep 30\n",
            )
            persistent_environment = root / "gar" / "demo.env"
            runtime_environment = root / "gar" / "system" / "demo.env"
            persistent_environment.parent.mkdir(parents=True)
            runtime_environment.parent.mkdir(parents=True)
            persistent_environment.write_text("PERSISTENT=base\nOVERRIDE=persistent\n", encoding="utf-8")
            unsafe_value = f"$(touch {command_substitution_marker})"
            runtime_environment.write_text(
                f"OVERRIDE=runtime\nRUNTIME=enabled\nUNSAFE={unsafe_value}\n", encoding="utf-8"
            )
            launcher = self._sandbox_launcher(
                root,
                {
                    'app_dir="/opt/gar/apps/$app"': f"app_dir={shlex.quote(str(app_dir))}",
                    'pid_file="/var/run/gar-$app.pid"': f"pid_file={shlex.quote(str(root / 'gar-demo.pid'))}",
                    "log_dir=/var/log/gar": f"log_dir={shlex.quote(str(root / 'log'))}",
                    'reboot_required_file="/var/lib/gar-target/state/$app.reboot-required"': (
                        f"reboot_required_file={shlex.quote(str(root / 'state' / 'demo.reboot-required'))}"
                    ),
                    'persistent_environment_file="/etc/gar/$app.env"': (
                        f"persistent_environment_file={shlex.quote(str(persistent_environment))}"
                    ),
                    'runtime_environment_file="/etc/gar/system/$app.env"': (
                        f"runtime_environment_file={shlex.quote(str(runtime_environment))}"
                    ),
                },
            )
            started = self._run(launcher, "start")
            self.assertEqual(0, started.returncode, started.stderr)
            deadline = time.monotonic() + 2
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(
                f"base|runtime|enabled|{unsafe_value}\n", output.read_text(encoding="utf-8")
            )
            self.assertFalse(command_substitution_marker.exists())
            stopped = self._run(launcher, "stop")
            self.assertEqual(0, stopped.returncode, stopped.stderr)

    def _exercise_contract(
        self,
        helper: Path,
        root: Path,
        *,
        marker_name: str = ".artifact-info.json",
    ) -> None:
        app = root / "apps" / "demo"
        app.mkdir(parents=True)
        self._write_executable(app / "run", "#!/bin/sh\nexit 0\n")
        self._write_executable(app / "health", "#!/bin/sh\nexit 0\n")
        marker = app / marker_name
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

    def _sandbox_installer(self, source: Path, root: Path) -> Path:
        content = source.read_text(encoding="utf-8")
        content = content.replace("/opt/gar/apps", str(root / "apps"))
        content = content.replace("/etc/gar/system", str(root / "system"))
        ownership_commands = (
            'chown -R root:root "$temporary"',
            'chown root:root "$marker"',
            'chown -R 0:0 "$temporary"',
            'chown 0:0 "$marker"',
        )
        replaced = False
        for command in ownership_commands:
            if command in content:
                content = content.replace(command, "true")
                replaced = True
        self.assertTrue(replaced)
        installer = root / f"{source.parent.parent.name}-installer"
        self._write_executable(installer, content)
        return installer

    def _sandbox_launcher(self, root: Path, replacements: dict[str, str]) -> Path:
        content = LYRA_LAUNCHER.read_text(encoding="utf-8").replace("app=@GAR_APP@", "app=demo", 1)
        for original, replacement in replacements.items():
            self.assertIn(original, content)
            content = content.replace(original, replacement, 1)
        launcher = root / "S95gar-demo"
        self._write_executable(launcher, content)
        return launcher

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
