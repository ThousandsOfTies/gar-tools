import configparser
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from embedded import runtime_paths
from product import Product


class EmbeddedCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = {
            'schema_version': 1, 'board': 'fixture', 'kind': 'platformio', 'os': 'Arduino',
            'architecture': 'test-mcu', 'startup': {'init': 'arduino'},
            'platformio': {'core_version': '6.1.19', 'platform': 'fixture@1.0', 'board': 'test',
                           'framework': 'arduino', 'lib_deps': ['vendor/driver@1.2.3']},
            'adapter': {'include': 'include', 'source': 'src/io.cpp'},
            'flash': {'size_bytes': 4194304},
            'resources': {'display': {'id': 'screen', 'width': 64, 'height': 128, 'orientation': 'portrait'},
                          'buttons': {'next': 3, 'ok': 7}}
        }
        self.data = {
            'schema_version': 1, 'id': 'fixture-product',
            'components': {'application': 'sources/app', 'tools': 'sources/tools', 'board': 'sources/board'},
            'board_profile': 'arduino', 'hardware': {'binding': 'hardware/binding.json'},
            'application': {'label': 'Unrelated app "A"', 'heap_bytes': 24576},
            'build': {'backend': 'platformio', 'project': 'firmware', 'environment': 'device',
                      'sources': ['app.cpp'], 'includes': ['include']},
            'launch': {'entrypoint': 'firmware/main.cpp'}
        }
        for path in ('sources/app/include', 'sources/tools', 'sources/board/include'):
            (self.root / path).mkdir(parents=True)
        for path in ('sources/app/app.cpp', 'sources/board/src/io.cpp', 'firmware/main.cpp', 'firmware/platformio.ini'):
            self.save(path, '// fixture\n')
        self.save('product.json', self.data)
        self.save('sources/board/board.json', {'schema_version': 1, 'id': 'fixture', 'profiles': {'arduino': 'profile.json'}})
        self.save('sources/board/profile.json', self.profile)
        self.save('hardware/binding.json', {'schema_version': 1, 'display': 'screen', 'buttons': ['next', 'ok'], 'orientation': 'portrait'})

    def save(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')

    def test_board_and_application_generate_separate_settings_without_copying_sources(self):
        product = Product(self.root).validate()
        output = product.prepare()
        config = configparser.ConfigParser(interpolation=None)
        config.read(output / 'board.ini')
        self.assertEqual('4MB', config['board']['board_build.flash_size'])
        board = (output / 'gar_board_config.h').read_text(encoding='utf-8')
        app = (output / 'application_config.h').read_text(encoding='utf-8')
        self.assertIn('width = 64', board)
        self.assertIn('next = 3', board)
        self.assertNotIn('Unrelated', board)
        self.assertIn('#define GAR_APPLICATION_HEAP_BYTES 24576', app)
        self.assertIn('#ifdef __cplusplus', app)
        self.assertNotIn('width', app)
        stamp = (output / 'board.ini').stat().st_mtime_ns
        product.prepare()
        self.assertEqual(stamp, (output / 'board.ini').stat().st_mtime_ns)
        self.assertEqual(['next', 'ok'], product.describe()['validated']['buttons'])

    def test_changing_the_selected_board_changes_generated_constants_only(self):
        binding = (self.root / 'hardware/binding.json').read_bytes()
        Product(self.root).prepare()
        self.profile['resources']['buttons']['next'] = 17
        self.profile['resources']['display']['width'] = 80
        self.save('sources/board/profile.json', self.profile)
        output = Product(self.root).prepare()
        self.assertIn('next = 17', (output / 'gar_board_config.h').read_text())
        self.assertIn('width = 80', (output / 'gar_board_config.h').read_text())
        self.assertEqual(binding, (self.root / 'hardware/binding.json').read_bytes())

    def test_invalid_bindings_and_source_escapes_fail_before_generation(self):
        self.save('hardware/binding.json', {'schema_version': 1, 'display': 'screen', 'buttons': ['missing'], 'orientation': 'portrait'})
        with self.assertRaisesRegex(ValueError, 'Button'):
            Product(self.root).prepare()
        self.assertFalse((self.root / '.gar').exists())
        self.data['build']['sources'] = ['../tools']
        self.save('product.json', self.data)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            Product(self.root).validate()

    def test_native_build_cannot_be_confused_with_firmware(self):
        with self.assertRaisesRegex(ValueError, 'simulator hook'):
            Product(self.root).build(native=True)

    def test_build_cache_is_platform_scoped(self):
        runtime, python, cache, env = runtime_paths(self.root, '6.1.19')
        self.assertIn('pio-6.1.19', runtime.name)
        self.assertTrue(python.is_relative_to(runtime))
        if os.name == 'nt':
            self.assertTrue(cache.is_relative_to(Path.home() / '.cache/gar'))
            self.assertNotEqual(cache,runtime_paths(self.root / 'other', '6.1.19')[2])
        else:
            self.assertTrue(cache.is_relative_to(self.root / '.cache/gar-target-build'))
        self.assertEqual(str(cache / 'core'), env['PLATFORMIO_CORE_DIR'])


if __name__ == '__main__':
    unittest.main()
