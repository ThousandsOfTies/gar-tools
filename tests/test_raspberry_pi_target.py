from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "targets" / "raspberry-pi-5"
RECIPE = TARGET / "provisioning" / "raspberry-pi-os-systemd"


class RaspberryPiTargetRecipeTest(unittest.TestCase):
    def test_manifest_selects_the_ssh_systemd_recipe(self) -> None:
        manifest = json.loads((TARGET / "target.json").read_text(encoding="utf-8"))

        self.assertEqual("raspberry-pi-5", manifest["id"])
        self.assertEqual("ssh_scp", manifest["defaultBackends"]["target"])
        self.assertEqual(
            {
                "architecture": "aarch64",
                "abi": "gnu",
                "libc": "glibc",
                "toolchainTriple": "aarch64-linux-gnu",
            },
            manifest["compatibility"],
        )
        self.assertEqual(
            {
                "type": "ssh-script",
                "path": "provisioning/raspberry-pi-os-systemd",
                "recipeVersion": 3,
                "lifecycle": {
                    "type": "gar-app-lifecycle-v1",
                    "command": "/usr/local/lib/gar/gar-target-lifecycle",
                },
            },
            manifest["provisioning"]["ssh_scp"],
        )

    def test_recipe_contains_the_standard_boot_contract(self) -> None:
        prepare = (RECIPE / "prepare.sh").read_text(encoding="utf-8")
        service = (RECIPE / "gar-app@.service").read_text(encoding="utf-8")
        lifecycle = (RECIPE / "gar-target-lifecycle").read_text(encoding="utf-8")

        self.assertIn("Raspberry Pi 5", prepare)
        self.assertIn("gar-target-install", prepare)
        self.assertIn("gar-target-lifecycle", prepare)
        self.assertIn("/etc/gar/target-id", prepare)
        self.assertIn("/etc/gar/recipe-version", prepare)
        self.assertIn("identity_source", prepare)
        self.assertIn(
            "NOPASSWD: /usr/local/lib/gar/gar-target-install, "
            "/usr/local/lib/gar/gar-target-lifecycle",
            prepare,
        )
        self.assertNotIn("NOPASSWD: ALL", prepare)
        installer = (RECIPE / "gar-target-install").read_text(encoding="utf-8")
        self.assertIn("register-app", installer)
        self.assertIn('chmod 0444 "$marker"', installer)
        self.assertIn('chmod go-w "$application_root"', installer)
        self.assertIn('chown root:root "$marker"', installer)
        self.assertIn('.gar-old.$$', installer)
        self.assertIn("User=gar", service)
        self.assertIn("ExecStart=/opt/gar/apps/%i/run", service)
        self.assertIn("EnvironmentFile=-/etc/gar/%i.env", service)
        self.assertIn("EnvironmentFile=-/etc/gar/system/%i.env", service)
        self.assertLess(
            service.index("EnvironmentFile=-/etc/gar/%i.env"),
            service.index("EnvironmentFile=-/etc/gar/system/%i.env"),
        )
        self.assertIn("/etc/gar/system", prepare)
        self.assertIn("/etc/gar/system/*.env", installer)
        self.assertNotIn("ConditionPathExists", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertNotIn("gpio-sim", prepare)
        self.assertIn("/usr/bin/systemctl", lifecycle)
        self.assertIn("/usr/bin/journalctl", lifecycle)
        self.assertIn(".gar-artifact.json", lifecycle)
        self.assertIn("running-build-id", lifecycle)
        self.assertIn("--build-id", lifecycle)

    def test_installer_rejects_paths_outside_the_application_contract(self) -> None:
        installer = RECIPE / "gar-target-install"

        result = subprocess.run(
            (str(installer), "install", "/tmp/not-a-gar-stage", "/etc/systemd/system/evil.service", "0644"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("destination is not permitted", result.stderr)

    def test_installer_rejects_nested_application_names(self) -> None:
        installer = RECIPE / "gar-target-install"

        result = subprocess.run(
            (str(installer), "install", "/tmp/not-a-gar-stage", "/opt/gar/apps/demo/nested", "0755"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("destination is not permitted", result.stderr)

    def test_installer_rejects_nested_runtime_environment_paths(self) -> None:
        installer = RECIPE / "gar-target-install"

        result = subprocess.run(
            (
                str(installer),
                "install",
                "/tmp/not-a-gar-stage",
                "/etc/gar/system/demo/nested.env",
                "0644",
            ),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("destination is not permitted", result.stderr)


if __name__ == "__main__":
    unittest.main()
