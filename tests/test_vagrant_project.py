import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE=Path(__file__).resolve().parents[1]/'simulation-host/vagrant'
VAGRANT=shutil.which('vagrant') or (shutil.which('vagrant.exe') if os.name == 'nt' else None)


@unittest.skipUnless(VAGRANT,'Vagrant declaration validation')
class VagrantProjectTests(unittest.TestCase):
    def validate(self, directory):
        return subprocess.run([VAGRANT,'validate'],cwd=directory,capture_output=True,text=True,
            env={**os.environ,'VAGRANT_NO_COLOR':'1','CHECKPOINT_DISABLE':'1'})

    def test_real_vagrant_accepts_shared_multi_machine_declaration_without_starting_vms(self):
        # A Windows Vagrant launched from WSL can read this mounted checkout,
        # whereas a Linux-only /tmp path may be inaccessible to its Ruby runtime.
        artifacts=TEMPLATE.parents[1]/'artifacts'
        artifacts.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='vagrant-validation-',dir=artifacts) as directory:
            project=Path(directory)
            for name in ('Vagrantfile','machines.csv','provision.sh'):
                shutil.copyfile(TEMPLATE/name,project/name)
            result=self.validate(project)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertFalse(list((project/'.vagrant/machines').rglob('id')))
            # Duplicate external ports must fail before VM creation.
            path=project/'machines.csv';path.write_text(path.read_text().replace('18881','18880'))
            result=self.validate(project)
            self.assertNotEqual(0,result.returncode)
            self.assertIn('Duplicate host port',result.stdout+result.stderr)
