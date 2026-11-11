import csv
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from hardware_contract import derive, generate


class CsvContractTests(unittest.TestCase):
    def fixture(self, root):
        hardware = root / 'hardware'
        hardware.mkdir()
        (hardware / 'components.csv').write_text('component_id,name\nboard,Board\nknob,Knob\nlcd,Display\n')
        (hardware / 'connections.csv').write_text(
            'source,source_pin,target,target_pin,signal,description\n'
            'board,physical pin 11 (GPIO17),knob,CLK,GPIO17,Clock\n'
            'board,19,lcd,SDI,MOSI,Data\nboard,23,lcd,SCK,SCLK,Clock\nboard,24,lcd,CS,CS0,Select\n')
        self.interfaces = [
            dict(id='encoder', kind='gpio', component_id='knob', runtime_name='encoder_a', component_pins='CLK',
                 required_drivers='gpio-cdev', voltage_v='3.3', resource='', min_speed_hz=''),
            dict(id='display', kind='spi', component_id='lcd', runtime_name='lcd',
                 component_pins='SDI:MOSI;SCK:SCLK;CS:CS0', required_drivers='spidev', voltage_v='3.3',
                 resource='', min_speed_hz='10000000'),
        ]
        self.save_interfaces(hardware)
        self.capabilities = {'target_id': 'fixture', 'resources': [
            {'id': 'gpio0', 'kind': 'gpio', 'device': '/dev/gpiochip0', 'line_pins': {'17': '11'},
             'pinmux': {'id': 'gpio'}},
            {'id': 'spi0', 'kind': 'spi', 'device': '/dev/spidev0.0',
             'signal_pins': {'MOSI': '19', 'MISO': '21', 'SCLK': '23', 'CS0': '24'}, 'pinmux': {'id': 'spi0'}},
        ]}
        (root / 'capabilities.json').write_text(json.dumps(self.capabilities))
        return SimpleNamespace(root=root, hardware=hardware, board={'id': 'fixture'},
            gpio=[{'name': 'encoder_a', 'chip': '/dev/gpiochip0', 'line': '17', 'direction': 'input'}],
            spi=[{'name': 'lcd', 'dev': '/dev/spidev0.0', 'mode': '0', 'max_speed_hz': '24000000'}],
            data={'hardware': {'spi_miso': False, 'contract': {
                'components': 'hardware/components.csv', 'connections': 'hardware/connections.csv',
                'interfaces': 'hardware/interfaces.csv', 'board_component': 'board', 'product': 'fixture-app'}}})

    def save_interfaces(self, hardware):
        with (hardware / 'interfaces.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.interfaces[0]))
            writer.writeheader()
            writer.writerows(self.interfaces)

    def test_gpio_and_write_only_spi_derive_from_actual_csv_without_repeating_pin_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            requirements, binding = derive(product, self.capabilities)
            self.assertEqual(17, binding['mappings'][0]['line'])
            self.assertEqual('11', binding['mappings'][0]['physical_pin'])
            self.assertEqual(['19:MOSI', '23:SCLK', '24:CS0'], binding['mappings'][1]['physical_pins'])
            self.assertFalse(requirements['requirements'][1]['requires_miso'])
            output = generate(product, product.root / 'capabilities.json')
            self.assertEqual(requirements, json.loads((output / 'requirements.json').read_text()))
            self.assertEqual(binding, json.loads((output / 'binding.json').read_text()))

    def test_wiring_drift_and_ambiguous_or_unknown_parts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            product.gpio[0]['line'] = '18'
            with self.assertRaisesRegex(ValueError, 'disagree'):
                derive(product, self.capabilities)
            product.gpio[0]['line'] = '17'
            self.interfaces[0]['component_id'] = 'unknown'
            self.save_interfaces(product.hardware)
            with self.assertRaisesRegex(ValueError, 'unsupported interface'):
                derive(product, self.capabilities)

    def test_duplicate_interface_and_wrong_board_cannot_generate(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            self.interfaces[1]['id'] = self.interfaces[0]['id']
            self.save_interfaces(product.hardware)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                derive(product, self.capabilities)
            self.capabilities['target_id'] = 'other'
            with self.assertRaisesRegex(ValueError, 'board/target'):
                derive(product, self.capabilities)

    def test_output_cannot_replace_source_or_machine_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            product = self.fixture(Path(directory))
            for output in ('hardware', '.gar/config.json', '.gar/hardware-contract/../config.json'):
                with self.assertRaises(ValueError):
                    generate(product, product.root / 'capabilities.json', output)


if __name__ == '__main__':
    unittest.main()
