"""The launched process reads current CSV; no cached JSON or generated env."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

LOADER = Path(__file__).resolve().parents[1] / 'targets/linux-device/runtime/hardware-csv/hardware-run.sh'


@unittest.skipUnless(os.name == 'posix' and shutil.which('awk'), 'POSIX runtime')
class HardwareRuntimeTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'environment.csv').write_text('variable,table,name,field\nGAR_TEST_LINE,gpio,button,line\nGAR_TEST_LABEL,gpio,button,description\n')
        (root / 'gpio.csv').write_text('name,line,description\nbutton,8,"a, b '' $(touch NEVER)"\n')
        (root / 'spi.csv').write_text('name,dev\n')

    def run_app(self, root, **overrides):
        environment = {key:value for key,value in os.environ.items() if not key.startswith('GAR_TEST_')}
        return subprocess.run(['sh',str(LOADER),str(root),sys.executable,'-c',
            'import os; print(os.environ["GAR_TEST_LINE"]); print(os.environ["GAR_TEST_LABEL"])'],
            env={**environment,**overrides},capture_output=True,text=True,cwd=root)

    def test_same_csv_is_read_each_launch_and_explicit_process_override_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            first=self.run_app(root)
            self.assertEqual(0,first.returncode,first.stderr)
            self.assertTrue(first.stdout.startswith('8\n'))
            self.assertIn('$(touch NEVER)',first.stdout)
            self.assertFalse((root/'NEVER').exists())
            path=root/'gpio.csv'; path.write_text(path.read_text().replace('button,8,','button,9,'))
            self.assertTrue(self.run_app(root).stdout.startswith('9\n'))
            self.assertTrue(self.run_app(root,GAR_TEST_LINE='42').stdout.startswith('42\n'))

    def test_missing_duplicate_and_malformed_data_never_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            for text in ('name,line\nbutton,8\n', 'name,line,description\nbutton,8,x\nbutton,9,y\n',
                         'name,line,description\nbutton,8,"unfinished\n'):
                (root/'gpio.csv').write_text(text)
                result=self.run_app(root)
                self.assertNotEqual(0,result.returncode)
                self.assertEqual('',result.stdout)

    def test_spreadsheet_utf8_bom_crlf_and_empty_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            for name in ('environment.csv','gpio.csv','spi.csv'):
                path=root/name
                path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes().replace(b'\n',b'\r\n'))
            result=self.run_app(root)
            self.assertEqual(0,result.returncode,result.stderr)
            (root/'environment.csv').write_text('variable,table,name,field\n')
            result=self.run_app(root)
            self.assertNotEqual(0,result.returncode)
            self.assertEqual('',result.stdout)
