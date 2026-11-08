from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "targets" / "frdm-imx91s"
UUU = TARGET / "provisioning" / "uuu"


class FrdmImx91sTargetTests(unittest.TestCase):
    def make_components(self, root: Path) -> Path:
        files = {
            "pub/u-boot/ram.bin": b"ram-boot",
            "pub/u-boot/nand.bin": b"nand-boot",
            "pub/kernel/Image": b"kernel",
            "pub/kernel/board.dtb": b"dtb",
            "pub/rootfs/rootfs.squashfs": b"rootfs",
            "pub/rootfs/usr.local.tar.bz2": b"overlay",
            "pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst": b"initrd",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return root

    def write_config(self, root: Path, *, confirmed: bool) -> Path:
        config = root / "imx91s-uuu.env"
        config.write_text(
            "\n".join(
                (
                    "export GAR_IMX91S_DTB=board.dtb",
                    "export GAR_IMX91S_RAM_BOOT_IMAGE=ram.bin",
                    "export GAR_IMX91S_NAND_BOOT_IMAGE=nand.bin",
                    f"export GAR_IMX91S_NAND_LAYOUT_CONFIRMED={int(confirmed)}",
                    "",
                )
            ),
            encoding="utf-8",
        )
        return config

    def run_script(self, script: str, *args: object, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        command = [str(UUU / script), *(str(arg) for arg in args)]
        return subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, **(env or {})},
            check=False,
            capture_output=True,
            text=True,
        )

    def test_target_pack_contains_no_product_identity(self) -> None:
        forbidden = ("garservopet", "gar-servo-pet", "gar_servo_pet")
        for path in TARGET.rglob("*"):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(any(token in content for token in forbidden))

    def test_factory_generator_requires_explicit_layout_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.make_components(root / "components")
            config = self.write_config(root, confirmed=False)
            output = root / "Factory.lst"

            result = self.run_script(
                "generate.sh",
                "--config",
                config,
                "--bundle-dir",
                bundle,
                "--output",
                output,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("layout is not confirmed", result.stderr)
            self.assertFalse(output.exists())

    def test_factory_generator_encodes_transfer_and_ownership_safeguards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.make_components(root / "components")
            config = self.write_config(root, confirmed=False)
            output = root / "Factory.lst"

            result = self.run_script(
                "generate.sh",
                "--config",
                config,
                "--bundle-dir",
                bundle,
                "--output",
                output,
                "--allow-unconfirmed",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            generated = output.read_text(encoding="utf-8")
            self.assertIn("SDPS[-t 10000]: boot -scanterm -f pub/u-boot/ram.bin", generated)
            self.assertIn("fspinand init spi-nand0", generated)
            self.assertIn("tar -xojf", generated)
            self.assertIn("chown 0:0 /mnt/gar-rootfs", generated)
            self.assertIn("GAR_IMX91S_NAND_FLASH_COMPLETE", generated)
            self.assertNotIn("acmd reboot", generated)
            self.assertNotRegex(generated, r"@@[A-Z0-9_]+@@")
            self.assertEqual(0x100000, (bundle / "pub/uuu-ram/Image.padded").stat().st_size)

    def test_layout_probe_is_read_only_and_uses_configured_ram_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.make_components(root / "components")
            config = self.write_config(root, confirmed=False)
            output = root / "Inspect.lst"

            result = self.run_script(
                "generate-layout-probe.sh",
                "--config",
                config,
                "--bundle-dir",
                bundle,
                "--output",
                output,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            generated = output.read_text(encoding="utf-8")
            self.assertIn("pub/u-boot/ram.bin", generated)
            self.assertIn("GAR_IMX91S_LAYOUT_PROBE_END", generated)
            self.assertNotIn("flash_erase", generated)
            self.assertNotIn("nandwrite", generated)
            self.assertNotIn("ubiformat", generated)
            self.assertNotIn("acmd reboot", generated)

    def test_dtb_update_touches_only_the_confirmed_dtb_partition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.make_components(root / "components")
            config = self.write_config(root, confirmed=True)
            output = root / "Update-dtb.lst"

            result = self.run_script(
                "generate-dtb-update.sh",
                "--config",
                config,
                "--bundle-dir",
                bundle,
                "--output",
                output,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            generated = output.read_text(encoding="utf-8")
            self.assertIn("/sys/class/mtd/mtd3/name", generated)
            self.assertIn("flash_erase /dev/mtd3", generated)
            self.assertIn("nandwrite -p /dev/mtd3", generated)
            self.assertIn("GAR_IMX91S_DTB_UPDATE_COMPLETE", generated)
            self.assertNotIn("fspinand", generated)
            self.assertNotIn("/dev/mtd2", generated)
            self.assertNotIn("/dev/mtd4", generated)
            self.assertNotIn("ubiformat", generated)
            self.assertNotIn("acmd reboot", generated)
            self.assertNotRegex(generated, r"@@[A-Z0-9_]+@@")

    def test_dtb_update_requires_confirmed_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.make_components(root / "components")
            config = self.write_config(root, confirmed=False)
            output = root / "Update-dtb.lst"

            result = self.run_script(
                "generate-dtb-update.sh",
                "--config",
                config,
                "--bundle-dir",
                bundle,
                "--output",
                output,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("requires GAR_IMX91S_NAND_LAYOUT_CONFIRMED=1", result.stderr)
            self.assertFalse(output.exists())

    def test_stage_builds_a_self_describing_generic_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            components = self.make_components(root / "components")
            config = self.write_config(root, confirmed=True)
            output = root / "bundle"

            result = self.run_script(
                "stage.sh",
                "--config",
                config,
                "--input-dir",
                components,
                "--output-dir",
                output,
                env={
                    "GAR_PRODUCT_NAME": "ExampleProduct",
                    "GAR_IMX91S_FACTORY_SCRIPT_NAME": "Factory-example.lst",
                },
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "Factory-example.lst").is_file())
            self.assertTrue((output / "checksums.sha256").is_file())
            info = (output / "bundle-info.txt").read_text(encoding="utf-8")
            self.assertIn("ExampleProduct FRDM-IMX91S", info)
            self.assertIn("SPI-NAND layout confirmed: 1", info)

    def test_stage_refuses_to_replace_its_input_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            components = self.make_components(root / "components")
            config = self.write_config(root, confirmed=True)

            result = self.run_script(
                "stage.sh",
                "--config",
                config,
                "--input-dir",
                components,
                "--output-dir",
                components,
                "--force",
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("must not be the input directory", result.stderr)
            self.assertTrue((components / "pub/kernel/Image").is_file())


if __name__ == "__main__":
    unittest.main()
