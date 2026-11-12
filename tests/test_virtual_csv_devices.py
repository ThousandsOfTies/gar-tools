import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'targets/linux-device/runtime/hardware-csv'
spec=importlib.util.spec_from_file_location('virtual_gpio',ROOT/'virtual_gpio.py')
gpio=importlib.util.module_from_spec(spec);spec.loader.exec_module(gpio)


class VirtualCsvDevicesTests(unittest.TestCase):
    def test_canonical_large_offsets_are_kept_and_size_the_virtual_bank(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'gpio.csv').write_text('name,chip,line,direction\nlcd_dc,/dev/gpiochip1,228,output\nlcd_rst,/dev/gpiochip1,262,output\n')
            before=(root/'gpio.csv').read_bytes()
            self.assertEqual([{'device':'/dev/gpiochip1','num_lines':263}],gpio.plan(root))
            self.assertEqual(before,(root/'gpio.csv').read_bytes())
            with (root/'gpio.csv').open('a') as stream:stream.write('duplicate,/dev/gpiochip1,262,input\n')
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                gpio.plan(root)

    @unittest.skipUnless(hasattr(Path,'symlink_to'),'symlink support')
    def test_virtual_alias_never_overwrites_an_existing_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();actual=root/'gpiochip0';expected=root/'gpiochip1'
            actual.touch();expected.write_text('existing device')
            with patch.object(Path,'is_char_device',return_value=True):
                with self.assertRaisesRegex(ValueError,'occupied'):
                    gpio.alias(expected,actual)
            self.assertEqual('existing device',expected.read_text())
