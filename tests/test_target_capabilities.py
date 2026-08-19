from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "raspberry-pi-5": {
        "resources": ("gpio0", "spi0.cs0", "usb-uvc", "network0"),
        "gpio_lines": (17, 22, 23, 24, 27),
        "spi_max_speed_hz": 50_000_000,
        "recipe_version": 6,
        "platform": ("aarch64", "gnu", "aarch64-linux-gnu", "systemd", "sudo-noninteractive"),
    },
    "luckfox-rk3506": {
        "resources": ("gpio0", "spi0.cs0", "network0"),
        "gpio_lines": (2, 3, 8, 9, 10),
        "spi_max_speed_hz": 40_000_000,
        "recipe_version": 5,
        "platform": ("armv7l", "gnueabihf", "arm-buildroot-linux-gnueabihf", "busybox", "root"),
    },
}


class TargetCapabilityTests(unittest.TestCase):
    def test_no_target_pack_owns_application_csv(self) -> None:
        csv_paths = sorted(path.relative_to(ROOT) for path in (ROOT / "targets").rglob("*.csv"))

        self.assertEqual([], csv_paths)

    def test_capability_schema_and_static_board_invariants(self) -> None:
        for target_id, expected in TARGETS.items():
            with self.subTest(target_id=target_id):
                target = ROOT / "targets" / target_id
                capability = json.loads(
                    (target / "hardware" / "capabilities.json").read_text(encoding="utf-8")
                )
                manifest = json.loads((target / "target.json").read_text(encoding="utf-8"))

                self.assertEqual(1, capability["schema_version"])
                self.assertEqual(target_id, capability["target_id"])
                self.assertEqual(target_id, manifest["id"])
                self.assertEqual(
                    expected["recipe_version"],
                    manifest["provisioning"]["ssh_scp"]["recipeVersion"],
                )
                platform = capability["platform"]
                self.assertEqual(
                    expected["platform"],
                    (
                        platform["architecture"],
                        platform["abi"],
                        platform["toolchain_triple"],
                        platform["init_system"],
                        platform["privilege_model"],
                    ),
                )
                self.assertEqual(manifest["compatibility"]["architecture"], platform["architecture"])
                self.assertEqual(manifest["compatibility"]["abi"], platform["abi"])
                self.assertEqual(manifest["compatibility"]["toolchainTriple"], platform["toolchain_triple"])

                resources = capability["resources"]
                self.assertEqual(expected["resources"], tuple(resource["id"] for resource in resources))
                self.assertEqual(len(resources), len({resource["id"] for resource in resources}))
                by_id = {resource["id"]: resource for resource in resources}

                gpio = by_id["gpio0"]
                self.assertEqual("gpio", gpio["kind"])
                self.assertEqual("/dev/gpiochip0", gpio["device"])
                self.assertEqual(3.3, gpio["voltage_v"])
                self.assertTrue(gpio["drivers"])
                self.assertEqual(expected["gpio_lines"], tuple(gpio["lines"]))
                self.assertEqual({str(line) for line in gpio["lines"]}, set(gpio["line_pins"]))
                self.assertEqual(("input", "output"), tuple(gpio["directions"]))

                spi = by_id["spi0.cs0"]
                self.assertEqual("spi", spi["kind"])
                self.assertEqual("/dev/spidev0.0", spi["device"])
                self.assertEqual(3.3, spi["voltage_v"])
                self.assertTrue(spi["drivers"])
                self.assertEqual(0, spi["bus"])
                self.assertEqual(0, spi["chip_select"])
                self.assertEqual(expected["spi_max_speed_hz"], spi["max_speed_hz"])
                self.assertEqual((0, 1, 2, 3), tuple(spi["modes"]))
                self.assertEqual({"MOSI", "MISO", "SCLK", "CS0"}, set(spi["signal_pins"]))
                self.assertTrue(spi["pinmux"]["id"])

                network = by_id["network0"]
                self.assertEqual("network", network["kind"])
                self.assertTrue(network["device"])
                self.assertTrue(network["drivers"])
                self.assertIn("linux-netdev", network["drivers"])
                self.assertNotIn("voltage_v", network)

                video = by_id.get("usb-uvc")
                if target_id == "raspberry-pi-5":
                    self.assertIsNotNone(video)
                    assert video is not None
                    self.assertEqual("video", video["kind"])
                    self.assertEqual("/dev/video0", video["device"])
                    self.assertEqual(5.0, video["voltage_v"])
                    self.assertTrue(video["drivers"])
                    self.assertEqual(30, video["max_fps"])
                else:
                    self.assertIsNone(video)

    def test_target_packs_do_not_embed_product_hardware(self) -> None:
        forbidden = (
            "gar" + "stream",
            "ili" + "9341",
            "ky" + "-040",
            "l" + "cd",
            "enc" + "oder",
        )
        for target_id in TARGETS:
            target = ROOT / "targets" / target_id
            for path in target.rglob("*"):
                if not path.is_file():
                    continue
                content = path.read_text(encoding="utf-8").lower()
                with self.subTest(target_id=target_id, path=path):
                    self.assertFalse(
                        any(token in content for token in forbidden),
                        f"product-specific hardware leaked into target pack: {path}",
                    )


if __name__ == "__main__":
    unittest.main()
