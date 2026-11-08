"""Check build configuration and cache behavior without requiring Emscripten."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('build_lvgl', Path(__file__).resolve().parents[1] / 'build_lvgl.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildLvglTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.lvgl = self.root / 'standalone-lvgl'
        (self.lvgl / 'src').mkdir(parents=True)
        (self.lvgl / 'lvgl.h').write_text('/* LVGL */', encoding='utf-8')
        (self.lvgl / 'src/core.c').write_text('void lv_init(void) {}', encoding='utf-8')
        self.app = self.root / 'app'
        self.app.mkdir()
        (self.app / 'web-entry.cpp').write_text('extern "C" void gar_app_init() {}', encoding='utf-8')
        self.config = self.root / 'lv_conf.h'
        self.config.write_text('#define LV_COLOR_DEPTH 16', encoding='utf-8')
        self.base = ['--lvgl', str(self.lvgl), '--app', str(self.app), '--config', str(self.config),
                     '--output', str(self.root / 'output'), '--cache', str(self.root / 'cache'), '--jobs', '1']
        self.commands = []

        def compiler(command, **kwargs):
            self.commands.append(command)
            Path(command[command.index('-o') + 1]).write_bytes(b'compiled')

        self.addCleanup(patch.stopall)
        patch.object(BUILD.subprocess, 'check_output', return_value='emcc test compiler').start()
        patch.object(BUILD.subprocess, 'run', side_effect=compiler).start()

    def compile(self, extra=()):
        BUILD.main([*self.base, *extra])
        return [command for command in self.commands if '-c' in command]

    def test_standalone_non_square_build_needs_no_lilygo_or_arduino_json(self):
        calls = self.compile(['--width', '320', '--height', '170', '--app-api', 'minimal'])
        self.assertTrue(calls)
        for command in calls:
            self.assertIn('-DGAR_LV_WIDTH=320', command)
            self.assertIn('-DGAR_LV_HEIGHT=170', command)
            self.assertIn('-I' + str(self.lvgl), command)
        link = self.commands[-1]
        exports = json.loads(next(flag.split('=', 1)[1] for flag in link if flag.startswith('-sEXPORTED_FUNCTIONS=')))
        self.assertIn('_gar_lv_width', exports)
        self.assertIn('_gar_lv_height', exports)
        self.assertIn('_gar_app_init', exports)
        self.assertNotIn('_gar_app_hardware', exports)
        metadata = json.loads((self.root / 'output/build.json').read_text(encoding='utf-8'))
        self.assertEqual((320, 170), (metadata['width'], metadata['height']))

    def test_defaults_keep_legacy_app_exports_and_display_size(self):
        calls = self.compile()
        self.assertIn('-DGAR_LV_WIDTH=240', calls[0])
        self.assertIn('-DGAR_LV_HEIGHT=240', calls[0])
        self.assertIn('_gar_app_hardware', ' '.join(self.commands[-1]))

    def test_legacy_lilygo_and_optional_json_library_paths_remain_supported(self):
        library = self.root / 'lilygo'
        shutil.copytree(self.lvgl, library / 'src/lvgl')
        json_library = self.root / 'ArduinoJson'
        (json_library / 'src').mkdir(parents=True)
        self.base[:2] = ['--library', str(library)]
        calls = self.compile(['--json-library', str(json_library)])
        self.assertIn('-I' + str(library / 'src'), calls[0])
        self.assertIn('-I' + str(json_library / 'src'), calls[0])

    def test_cache_reuses_objects_and_invalidates_for_dimensions_and_config(self):
        count = len(self.compile())
        self.commands.clear()
        self.assertEqual([], self.compile())
        self.commands.clear()
        self.assertEqual(count, len(self.compile(['--width', '320'])))
        self.commands.clear()
        self.config.write_text('#define LV_COLOR_DEPTH 32', encoding='utf-8')
        self.assertEqual(count, len(self.compile(['--width', '320'])))

    def test_optional_include_and_entry_source_are_compiled_once(self):
        includes = self.root / 'dependencies'
        includes.mkdir()
        entry = self.app / 'entry.c'
        entry.write_text('void start(void) {}', encoding='utf-8')
        calls = self.compile(['--include', str(includes), '--entry', str(entry), '--app-api', 'none', '--export', 'start'])
        self.assertEqual(1, sum(str(entry) in command for command in calls))
        self.assertIn('-I' + str(includes), calls[0])
        self.assertIn('_start', ' '.join(self.commands[-1]))
        self.assertNotIn('_gar_app_init', ' '.join(self.commands[-1]))

    def test_invalid_dimensions_are_rejected_before_build(self):
        for value in ['0', '-1', '32768']:
            with self.subTest(value=value), patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit):
                BUILD.parser().parse_args([*self.base, '--width', value])
        self.assertEqual([], self.commands)


if __name__ == '__main__':
    unittest.main()
