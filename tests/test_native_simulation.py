import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from native_simulation import package


@unittest.skipUnless(os.name == 'posix' and shutil.which('gcc'), 'Native Linux compiler contract')
class NativeSimulationTests(unittest.TestCase):
    def fixture(self, root):
        root = root.resolve()
        (root / 'sources/tools').mkdir(parents=True)
        (root / 'sources/tools/README.md').write_text('tool fixture')
        (root / 'application').mkdir()
        (root / 'application/main.c').write_text('#include <stdio.h>\nint main(void){puts("unchanged application");return 0;}\n')
        return SimpleNamespace(root=root, id='fixture-native',
            describe=lambda: {'product': 'fixture-native'}, data={
                'components': {'tools': 'sources/tools'}, 'build': {},
                'simulation': {'native_artifact': {'sources': ['sources/tools', 'application'],
                    'commands': [['gcc', 'application/main.c', '-o', '{build}/application']],
                    'outputs': ['application'], 'entrypoint': 'build/application'}}})

    def test_actual_linux_build_has_architecture_and_source_hashes_in_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            source = (product.root / 'application/main.c').read_bytes()
            with patch.dict(os.environ, {'GAR_SIM_ARCH': 'x86_64'}):
                output = package(product)
            manifest = json.loads((output / 'artifact.json').read_text())
            self.assertEqual('sim_app', manifest['artifact_kind'])
            with tarfile.open(output / 'files/vm.tar.gz') as archive:
                checks = json.loads(archive.extractfile('simulator-manifest.json').read())
                for name, digest in checks.items():
                    self.assertEqual(digest, hashlib.sha256(archive.extractfile(name).read()).hexdigest())
                self.assertEqual(source, archive.extractfile('application/main.c').read())
                self.assertTrue(archive.extractfile('build/application').read().startswith(b'\x7fELF'))
            self.assertEqual(source, (product.root / 'application/main.c').read_bytes())

    def test_wrong_architecture_never_replaces_existing_snapshot_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            with patch.dict(os.environ, {'GAR_SIM_ARCH': 'x86_64'}):
                output = package(product)
            before = (output / 'files/vm.tar.gz').read_bytes()
            with patch.dict(os.environ, {'GAR_SIM_ARCH': 'aarch64'}):
                with self.assertRaisesRegex(ValueError, 'wrong architecture'):
                    package(product)
            self.assertEqual(before, (output / 'files/vm.tar.gz').read_bytes())


if __name__ == '__main__':
    unittest.main()
