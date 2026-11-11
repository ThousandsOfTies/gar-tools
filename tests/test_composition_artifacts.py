import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from artifact import run
from esp32_bundle import export


class ArtifactTests(unittest.TestCase):
    def test_declared_portable_hook_receives_clean_and_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook = root / 'hook.py'
            hook.write_text("import os,sys,json\nfrom pathlib import Path\n"
                            "Path('called.json').write_text(json.dumps([sys.argv[1:],os.environ['GAR_SIM_ARCH']]))\n")
            product = SimpleNamespace(root=root, data={'build': {'simulation_hook': 'hook.py'}})
            with patch.dict('os.environ', {'GAR_SIM_ARCH': 'aarch64'}):
                run(product, 'sim_app', clean=True)
            self.assertEqual([['clean'], 'aarch64'], json.loads((root / 'called.json').read_text()))

    def test_missing_simulation_adapter_cannot_build_firmware_instead(self):
        product = SimpleNamespace(data={'build': {'backend': 'platformio'}})
        with self.assertRaisesRegex(ValueError, 'refusing to substitute'):
            run(product, 'sim_app')

    def fixture(self, root):
        root = root.resolve()
        build, cache = root / 'build', root / 'cache'
        build.mkdir()
        boot = bytearray(24)
        boot[0] = 0xe9
        boot[12:14] = (9).to_bytes(2, 'little')
        for name in ('bootloader.bin', 'firmware.bin'):
            (build / name).write_bytes(boot)
        partition = struct.pack('<HBBII16sI', 0x50aa, 0, 0, 0x10000, 0x100000, b'factory', 0)
        (build / 'partitions.bin').write_bytes(partition + b'\xeb\xeb' + b'\xff' * 14 + hashlib.md5(partition).digest())
        boot_app = cache / 'core/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'
        boot_app.parent.mkdir(parents=True)
        boot_app.write_bytes(b'\xff' * 8192)
        product = SimpleNamespace(root=root, data={'id': 'fixture-product'},
            profile={'flash': {'chip': 'esp32s3', 'size_bytes': 8 * 1024 * 1024},
                     'platformio': {'core_version': '6.1.19'}})
        return product, build, cache

    def test_firmware_package_is_exported_with_checksums_and_wrong_chip_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            product, build, cache = self.fixture(Path(directory))
            with patch('esp32_bundle.runtime_paths', return_value=(None, None, cache, {})):
                output = export(product, build)
                self.assertEqual('esp32', json.loads((output / 'artifact.json').read_text())['target'])
                digest = hashlib.sha256((build / 'firmware.bin').read_bytes()).hexdigest()
                self.assertIn(digest + '  firmware.bin', (output / 'files/firmware/SHA256SUMS').read_text())
                image = bytearray((build / 'firmware.bin').read_bytes())
                image[12:14] = b'\x00\x00'
                (build / 'firmware.bin').write_bytes(image)
                with self.assertRaisesRegex(ValueError, 'wrong ESP32 image chip'):
                    export(product, build)
                self.assertEqual(digest, hashlib.sha256((output / 'files/firmware/firmware.bin').read_bytes()).hexdigest())

    def test_firmware_export_preserves_foreign_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            product, build, cache = self.fixture(Path(directory))
            output = product.root / 'artifacts/from-codespace'
            output.mkdir(parents=True)
            original = json.dumps({'name': 'other-product', 'target': 'esp32'})
            (output / 'artifact.json').write_text(original)
            with patch('esp32_bundle.runtime_paths', return_value=(None, None, cache, {})):
                with self.assertRaisesRegex(ValueError, 'another Product'):
                    export(product, build)
            self.assertEqual(original, (output / 'artifact.json').read_text())


if __name__ == '__main__':
    unittest.main()
