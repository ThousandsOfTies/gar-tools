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
                "type": "ssh-script",
                "path": "provisioning/raspberry-pi-os-systemd",
            },
            manifest["provisioning"]["ssh_scp"],
        )

    def test_recipe_contains_the_standard_boot_contract(self) -> None:
        prepare = (RECIPE / "prepare.sh").read_text(encoding="utf-8")
        service = (RECIPE / "gar-app@.service").read_text(encoding="utf-8")

        self.assertIn("Raspberry Pi 5", prepare)
        self.assertIn("gar-target-install", prepare)
        self.assertIn("User=gar", service)
        self.assertIn("ExecStart=/opt/gar/apps/%i/run", service)
        self.assertIn("EnvironmentFile=-/etc/gar/%i.env", service)
        self.assertNotIn("ConditionPathExists", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertNotIn("gpio-sim", prepare)

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


if __name__ == "__main__":
    unittest.main()
