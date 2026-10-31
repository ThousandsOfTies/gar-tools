from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "composition"))
from package import configure_script, launch_script, package_product, render_service
from product import Product, inside


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.board = {"schema_version": 1, "id": "test-board", "profiles": {"os": "profiles/os.json"}}
        self.profile = {"schema_version": 1, "board": "test-board", "os": "fixture",
                        "architecture": "armv7l", "identity": {"architecture": "armv7l", "model": "Generic test board"},
                        "startup": {"init": "busybox", "prefix": "S99zz", "device_wait_seconds": 20},
                        "gpio": [{"device": "/dev/gpiochip0", "lines": [3, 4, 5]}],
                        "spi": [{"device": "/dev/spidev0.0", "bus": 0, "chip_select": 0, "modes": [0],
                                 "max_speed_hz": 40000000, "routing": {"sclk": 24, "mosi": 25, "cs": 27}}],
                        "preparation": {"kind": "luckfox-config-spi", "config_file": "/etc/luckfox-config.json"}}
        self.data = {"schema_version": 1, "id": "generic-product",
                     "components": {"application": "sources/app", "tools": "sources/tools", "board": "sources/board"},
                     "board_profile": "os", "hardware": {"physical": "hardware/real", "simulation": "hardware/sim", "spi_miso": False},
                     "build": {"script": "build.sh", "directory": "build/target", "outputs": ["reader"]},
                     "launch": {"entrypoint": "run.cjs"}, "deployment": {"root": "/opt/generic-product", "user": "root"},
                     "payload": ["run.cjs"]}
        self.save("sources/board/board.json", self.board)
        self.save("sources/board/profiles/os.json", self.profile)
        self.save("product.json", self.data)
        self.save("sources/app/build.sh", "#!/bin/sh\nexit 0\n")
        self.save("run.cjs", "// Unrelated application fixture\n")
        self.save("hardware/real/gpio.csv", "name,chip,line,direction,debounce_us\nknob,/dev/gpiochip0,3,input,1000\n")
        self.save("hardware/real/spi.csv", "name,bus,chip_select,dev,mode,max_speed_hz\nscreen,0,0,/dev/spidev0.0,0,8000000\n")
        for relative in ("targets/luckfox-rk3506/provisioning/buildroot-busybox/gar-app@.service",
                         "targets/raspberry-pi-5/provisioning/raspberry-pi-os-systemd/gar-app@.service", "composition/preflight.py"):
            self.save("sources/tools/" + relative, (TOOLS / relative).read_text())

    def save(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def target_binary(self, *, mode="target", machine=40):
        self.save("build/target/composition-build.json", {"mode": mode, "board": "test-board", "profile": "os", "architecture": "armv7l"})
        header = bytearray(64)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<H", header, 18, machine)
        struct.pack_into("<I", header, 36, 0x400)
        (self.root / "build/target/reader").write_bytes(header)

    def test_hardware_binding_is_checked_against_independent_board_resources(self):
        self.assertEqual(1, Product(self.root).describe()["validated"]["gpio_lines"])
        self.profile["gpio"][0]["lines"] = [100]
        self.save("sources/board/profiles/os.json", self.profile)
        with self.assertRaisesRegex(ValueError, "outside"):
            Product(self.root).validate()

    def test_paths_and_spi_limits_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            inside(self.root, "../outside", exists=False)
        self.profile["spi"][0]["max_speed_hz"] = 1000000
        self.save("sources/board/profiles/os.json", self.profile)
        with self.assertRaisesRegex(ValueError, "speed"):
            Product(self.root).validate()

    def test_board_selects_boot_mechanism_product_selects_entry_and_speed(self):
        product = Product(self.root).validate()
        name, service = render_service(product)
        self.assertEqual("S99zz-generic-product", name)
        self.assertIn('app_dir=/opt/generic-product/app', service)
        self.assertIn("recorded_start_time", service, "Reuse the existing PID identity protection")
        self.assertIn("/opt/generic-product/app/run.cjs", launch_script(product))
        self.assertIn("--speed 8000000", configure_script(product))
        self.assertNotIn("generic-product", configure_script(product), "Board preparation must be application-neutral")
        self.profile["startup"] = {"init": "systemd", "after": "systemd-udev-trigger.service", "device_wait_seconds": 15}
        self.save("sources/board/profiles/os.json", self.profile)
        name, service = render_service(Product(self.root))
        self.assertEqual("generic-product.service", name)
        self.assertIn("After=systemd-udev-trigger.service", service)
        self.assertIn("ExecStart=/opt/generic-product/app/run", service)

    def test_native_or_wrong_architecture_cannot_become_target_payload(self):
        self.target_binary(mode="native")
        with self.assertRaisesRegex(ValueError, "native"):
            package_product(Product(self.root), "artifacts/native")
        self.target_binary(machine=62)
        with self.assertRaisesRegex(ValueError, "architecture"):
            package_product(Product(self.root), "artifacts/wrong")

    def test_bundle_pins_all_components_and_keeps_sdk_bytes_external(self):
        self.target_binary()
        destination = package_product(Product(self.root), "artifacts/target")
        self.assertTrue((destination / "files/app/.board/profiles/os.json").is_file())
        self.assertTrue((destination / "files/app/.startup/S99zz-generic-product").is_file())
        self.assertTrue((destination / "files/app/build/target/reader").is_file())
        manifest = json.loads((destination / "artifact.json").read_text())
        self.assertEqual({"application", "tools", "board"}, set(manifest["composition"]["components"]))
        self.assertEqual("/opt/generic-product/app", manifest["deploy"]["app"]["files"][0]["dest"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            package_product(Product(self.root), "artifacts/target")


if __name__ == "__main__":
    unittest.main()
