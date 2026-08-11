from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "targets" / "luckfox-rk3506"


class LuckfoxLyraTargetTests(unittest.TestCase):
    def test_manifest_identifies_rk3506_buildroot_target(self) -> None:
        manifest = json.loads((TARGET / "target.json").read_text(encoding="utf-8"))

        self.assertEqual("luckfox-rk3506", manifest["id"])
        self.assertEqual("Luckfox Lyra Plus (RK3506)", manifest["displayName"])
        self.assertEqual("targets/luckfox-rk3506", manifest["toolsRoot"])
        self.assertEqual(
            {
                "architecture": "armv7l",
                "abi": "gnueabihf",
                "libc": "glibc",
                "toolchainTriple": "arm-buildroot-linux-gnueabihf",
            },
            manifest["compatibility"],
        )
        self.assertEqual(
            {
                "codespace": "local",
                "simulator": "ssh_remote",
                "target": "ssh_scp",
            },
            manifest["defaultBackends"],
        )
        self.assertIn("Buildroot", manifest["description"])
        self.assertIn("BusyBox", manifest["description"])
        self.assertEqual(
            {
                "type": "ssh-script",
                "path": "provisioning/buildroot-busybox",
                "recipeVersion": 3,
                "lifecycle": {
                    "type": "gar-app-lifecycle-v1",
                    "command": "/usr/local/lib/gar/gar-target-lifecycle",
                },
            },
            manifest["provisioning"]["ssh_scp"],
        )

    def test_target_documents_runtime_boundary(self) -> None:
        readme = (TARGET / "README.md").read_text(encoding="utf-8")

        self.assertIn("armv7l", readme)
        self.assertIn("BusyBox init", readme)
        self.assertIn("Do not install systemd units", readme)

    def test_target_has_busybox_prepare_recipe(self) -> None:
        recipe = TARGET / "provisioning" / "buildroot-busybox"

        prepare = (recipe / "prepare.sh").read_text(encoding="utf-8")
        installer = (recipe / "gar-target-install").read_text(encoding="utf-8")
        launcher = (recipe / "gar-app@.service").read_text(encoding="utf-8")
        lifecycle = (recipe / "gar-target-lifecycle").read_text(encoding="utf-8")
        self.assertIn("rk3506", prepare)
        self.assertIn("/usr/local/lib/gar/gar-target-install", prepare)
        self.assertIn("/usr/local/lib/gar/gar-target-lifecycle", prepare)
        self.assertIn("/etc/gar/target-id", prepare)
        self.assertIn("/etc/gar/recipe-version", prepare)
        self.assertIn("identity_source", prepare)
        self.assertIn("enable-app", installer)
        self.assertIn("register-app", installer)
        self.assertIn("/etc/init.d/S95$init_name", installer)
        self.assertIn("configure-target", installer)
        self.assertIn('configure_status" -eq 10', installer)
        self.assertIn(".reboot-required", installer)
        self.assertIn('chmod 0444 "$marker"', installer)
        self.assertIn('chmod go-w "$application_root"', installer)
        self.assertIn('chown 0:0 "$marker"', installer)
        self.assertIn('.gar-old.$$', installer)
        self.assertIn("/etc/gar/system", prepare)
        self.assertIn("/etc/gar/system/*.env", installer)
        self.assertIn("target reboot is required", lifecycle)
        self.assertIn('rm -f "$reboot_required_file"', launcher)
        self.assertIn("@GAR_APP@", launcher)
        self.assertIn('/proc/$process_pid/stat', launcher)
        self.assertIn("recorded_start_time", launcher)
        self.assertIn('persistent_environment_file="/etc/gar/$app.env"', launcher)
        self.assertIn('runtime_environment_file="/etc/gar/system/$app.env"', launcher)
        self.assertLess(
            launcher.index('load_environment_file "$persistent_environment_file"'),
            launcher.index('load_environment_file "$runtime_environment_file"'),
        )
        self.assertIn("running-build-id", lifecycle)
        self.assertIn(".gar-artifact.json", lifecycle)
        self.assertNotIn("systemctl", prepare + installer + launcher + lifecycle)
        self.assertNotIn("sudo", prepare + installer + launcher + lifecycle)

    def test_simulation_hardware_matches_rx_device_contract(self) -> None:
        gpio = (TARGET / "hardware" / "gpio.csv").read_text(encoding="utf-8")
        spi = (TARGET / "hardware" / "spi.csv").read_text(encoding="utf-8")

        self.assertIn("encoder_a,/dev/gpiochip0,20,input,encoder", gpio)
        self.assertIn("encoder_sw,/dev/gpiochip0,22,input,button,low", gpio)
        self.assertIn("lcd_dc,/dev/gpiochip0,23,output,display_ctrl", gpio)
        self.assertIn("lcd_rst,/dev/gpiochip0,24,output,display_ctrl", gpio)
        self.assertIn("/dev/spidev0.0,0,40000000,ili9341,ili9341", spi)


if __name__ == "__main__":
    unittest.main()
