import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('snapshot_client',Path(__file__).resolve().parents[1]/'simulation-host/native-snapshot/client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


class SnapshotClientTests(unittest.TestCase):
    def test_start_never_builds_or_deploys_and_stop_addresses_the_selected_host(self):
        self.assertEqual([('sim','start','host'),('sim','start')],client.commands('start'))
        self.assertEqual([('sim','stop'),('sim','stop','host')],client.commands('stop'))
        self.assertEqual([('sim','deploy')],client.commands('deploy'))
        self.assertEqual([('product','run','verify-simulation')],client.commands('verify'))


if __name__=='__main__':unittest.main()
