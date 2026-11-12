from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "composition"))
from device import Device
from package import configure_script, install_script, launch_script, package_product, render_service
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

    def test_native_artifact_stages_verified_target_and_cleans_only_its_own_output(self):
        from native_target import run
        product=Product(self.root).validate()
        with patch.object(product,'build',side_effect=self.target_binary):
            output=run(product)
            self.assertEqual('test-board',json.loads((output/'artifact.json').read_text())['target'])
            first=(output/'files/app/build/target/reader').read_bytes()
            self.assertIn('recorded_start_time',(output/'files/app/.startup/S99zz-generic-product').read_text())
            run(product)
            self.assertEqual(first,(output/'files/app/build/target/reader').read_bytes())
        # A bad ELF cannot replace the previously verified staging directory.
        with patch.object(product,'build',side_effect=lambda:self.target_binary(machine=62)):
            with self.assertRaisesRegex(ValueError,'architecture'):run(product)
        self.assertEqual(first,(output/'files/app/build/target/reader').read_bytes())
        run(product,clean=True)
        self.assertFalse(output.exists())

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
        installer = install_script(product, name)
        self.assertLess(installer.index(" stop; fi"), installer.index("install -m 0755"), "Stop the old PID manager before replacing it")
        self.assertIn("/opt/generic-product/app/run.cjs", launch_script(product))
        self.assertIn("--speed 8000000", configure_script(product))
        self.assertNotIn("generic-product", configure_script(product), "Board preparation must be application-neutral")
        self.profile["startup"] = {"init": "systemd", "after": "systemd-udev-trigger.service", "device_wait_seconds": 15}
        self.save("sources/board/profiles/os.json", self.profile)
        product = Product(self.root)
        name, service = render_service(product)
        self.assertEqual("generic-product.service", name)
        self.assertIn("After=systemd-udev-trigger.service", service)
        self.assertIn("ExecStart=/opt/generic-product/app/run", service)
        product.data["deployment"]["legacy_services"] = ["old-application.service"]
        self.assertIn("systemctl disable --now old-application.service", install_script(product, name))

    def test_native_or_wrong_architecture_cannot_become_target_payload(self):
        self.target_binary(mode="native")
        with self.assertRaisesRegex(ValueError, "native"):
            package_product(Product(self.root), "artifacts/native")
        self.target_binary(machine=62)
        with self.assertRaisesRegex(ValueError, "architecture"):
            package_product(Product(self.root), "artifacts/wrong")

    def test_optional_i2c_is_validated_and_board_overlay_is_packaged(self):
        self.profile["i2c"] = [{"device": "/dev/i2c-2", "bus": 2}]
        self.profile["preparation"] = {"kind": "armbian-overlay", "overlay": "assets/spi.dts", "name": "generic-spi",
                                       "boot_config": "/boot/armbianEnv.txt", "resource_overlays": [
                                           {"device": "/dev/i2c-2", "overlay": "assets/i2c.dts", "name": "generic-i2c"}]}
        self.save("sources/board/profiles/os.json", self.profile)
        self.save("sources/board/assets/spi.dts", "/dts-v1/;")
        self.save("sources/board/assets/i2c.dts", "/dts-v1/;")
        self.save("hardware/real/i2c.csv", "name,bus,dev,address\ncontroller,2,/dev/i2c-2,0x40\n")
        self.target_binary()
        product = Product(self.root).validate()
        self.assertIn("generic-i2c.dtbo", configure_script(product))
        output = package_product(product, "artifacts/i2c")
        self.assertTrue((output / "files/app/.board/assets/i2c.dts").is_file())
        self.assertIn('KERNEL=="i2c-2", GROUP="i2c"', (output / "files/app/.startup/devices.rules").read_text())
        self.save("hardware/real/i2c.csv", "name,bus,dev,address\ncontroller,99,/dev/i2c-2,0x40\n")
        with self.assertRaisesRegex(ValueError, "I2C"):
            Product(self.root).validate()

    def test_declared_build_options_and_systemd_groups_are_bounded(self):
        self.data["build"]["environment"] = {"GAR_OPTION": "1"}
        self.save("product.json", self.data)
        Product(self.root).validate()
        self.data["build"]["environment"] = {"CC": "untrusted"}
        self.save("product.json", self.data)
        with self.assertRaisesRegex(ValueError, "reserved"):
            Product(self.root).validate()
        self.data["build"].pop("environment")
        self.profile["startup"] = {"init": "systemd", "after": "systemd-udev-trigger.service", "device_wait_seconds": 15}
        self.save("sources/board/profiles/os.json", self.profile)
        self.data["deployment"].update(runtime_directory="generic-runtime", supplementary_groups=["i2c", "audio"])
        self.save("product.json", self.data)
        product = Product(self.root).validate()
        service = render_service(product)[1]
        self.assertIn("RuntimeDirectory=generic-runtime", service)
        self.assertIn("SupplementaryGroups=audio gpio i2c spi", service)

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

    def test_device_adapter_uses_board_identity_and_keeps_instance_data_out_of_reports(self):
        self.save(".gar/device.json", {"serial": "TEST-LOCAL-ONLY", "sdk": "/external-sdk", "wslDistribution": "test"})
        device = Device(self.root)
        with patch.object(device, "remote", side_effect=[SimpleNamespace(stdout="armv7l\n"), SimpleNamespace(stdout="Wrong model\0")]) as remote:
            with self.assertRaisesRegex(ValueError, "model"):
                device.assert_device()
            self.assertEqual(2, remote.call_count, "Reject the wrong board before any modifying command")
        self.assertNotIn("TEST-LOCAL-ONLY", json.dumps(device.product.describe()))

    def test_preflight_uses_selected_controller_identity(self):
        from preflight import check
        self.profile["gpio"][0].update(label="expected-chip", line_count=288)
        def info(fd, command, data):
            struct.pack_into("32s32sI", data, 0, b"gpiochip0", b"wrong-chip", 288)
        with patch.dict(sys.modules, {"fcntl": SimpleNamespace(ioctl=Mock(side_effect=info))}), \
                patch("preflight.Path.exists", return_value=True), \
                patch("preflight.os.stat", return_value=SimpleNamespace(st_mode=0o020000)), \
                patch("preflight.os.open", return_value=9), patch("preflight.os.close"), \
                self.assertRaisesRegex(ValueError, "GPIO controller identity"):
            check(self.profile, self.root / "hardware/real")


if __name__ == "__main__":
    unittest.main()
