"""Archive trust boundary checks; no VM, service or physical device is operated."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest


@unittest.skipUnless(os.name=='posix','The runtime executes on Linux')
class SnapshotHostTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('snapshot_host',Path(__file__).resolve().parents[1]/'simulation-host/native-snapshot/host.py')
        self.host=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.host)

    def archive(self,path,files,extra=None):
        checks={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
        with tarfile.open(path,'w:gz') as archive:
            for name,data in {**files,'simulator-manifest.json':json.dumps(checks).encode()}.items():
                member=tarfile.TarInfo(name);member.size=len(data);archive.addfile(member,io.BytesIO(data))
            if extra:archive.addfile(extra)

    def test_only_a_complete_checksum_inventory_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'out';output.mkdir();archive=root/'app.tar.gz'
            self.archive(archive,{'product.json':b'{}','build/app':b'binary fixture'})
            self.host.extract(archive,output);self.assertTrue(self.host.verify(output))
            (output/'build/app').write_bytes(b'tampered')
            self.assertFalse(self.host.verify(output))

    def test_links_and_traversal_are_rejected_before_any_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for index,name in enumerate(['../outside','/tmp/outside','link']):
                output=root/str(index);output.mkdir();archive=root/'app.tar.gz'
                member=tarfile.TarInfo(name)
                if name=='link':member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
                self.archive(archive,{'product.json':b'{}'},member)
                with self.assertRaisesRegex(ValueError,'Unsafe'):self.host.extract(archive,output)
                self.assertEqual([],list(output.iterdir()))

    def test_undeclared_file_and_checksum_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'out';output.mkdir();archive=root/'app.tar.gz'
            extra=tarfile.TarInfo('undeclared');extra.size=0
            self.archive(archive,{'product.json':b'{}'},extra)
            with self.assertRaisesRegex(ValueError,'inventory'):self.host.extract(archive,output)


if __name__=='__main__':unittest.main()
