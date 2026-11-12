from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'composition'))
from i2c_binding import derive,generate


class I2cCsvBindingTest(unittest.TestCase):
    def fixture(self,root):
        root=root.resolve();hardware=root/'hardware';hardware.mkdir()
        for name,text in {
            'components.csv':'component_id,name\nboard,Board\ncontroller,PWM\n',
            'connections.csv':'source,source_pin,target,target_pin\nboard,3,controller,SDA\nboard,5,controller,SCL\n',
            'i2c.csv':'name,bus,dev,address\npwm,3,/dev/i2c-3,0x40\n',
            'interfaces.csv':'id,component_id,runtime_name,controller,frequency_hz,logic_voltage_v,pin_group,keep_rails\nservo-bus,controller,pwm,LPI2C4,100000,3.3,qualified-grp,exp-3v3;exp-5v\n'
        }.items():(hardware/name).write_text(text)
        return {'hardware':{'i2c':'hardware/i2c.csv','i2c_contract':{
            'components':'hardware/components.csv','connections':'hardware/connections.csv',
            'interfaces':'hardware/interfaces.csv','board_component':'board','product':'unrelated-app'}}}

    def test_policy_and_runtime_share_one_csv_source_without_writing_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();data=self.fixture(root)
            binding=derive(root,data,'qualified-board')
            self.assertEqual('/dev/i2c-3',binding['interfaces'][0]['device'])
            self.assertEqual({'SDA':'3','SCL':'5'},binding['interfaces'][0]['pins'])
            self.assertEqual(['exp-3v3','exp-5v'],binding['preparation']['keep_rails'])
            self.assertFalse(list(root.rglob('*.json')))
            path=root/'hardware/i2c.csv';path.write_text(path.read_text().replace(',3,/dev/i2c-3,',',1,/dev/i2c-1,'))
            self.assertEqual(1,derive(root,data,'qualified-board')['interfaces'][0]['bus'])

    def test_mismatched_runtime_and_ambiguous_wiring_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();data=self.fixture(root)
            path=root/'hardware/i2c.csv';original=path.read_text();path.write_text(original.replace('/dev/i2c-3','/dev/i2c-99'))
            with self.assertRaisesRegex(ValueError,'disagree'):derive(root,data,'board')
            path.write_text(original)
            path=root/'hardware/connections.csv';path.write_text(path.read_text()+'board,7,controller,SDA\n')
            with self.assertRaisesRegex(ValueError,'ambiguous'):derive(root,data,'board')

    def test_json_is_generated_only_under_private_composition_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();data=self.fixture(root)
            output=generate(root,data,'board')
            self.assertEqual(root/'.gar/composition/i2c-binding.json',output)
            self.assertFalse((root/'hardware/binding.json').exists())
