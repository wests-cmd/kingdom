import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import unittest

spec=importlib.util.spec_from_file_location('source_archive',Path(__file__).parents[1]/'scripts/archive-verified-source.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@unittest.skipUnless(shutil.which('git'),'Git required for source attestation')
class VerifiedSourceTests(unittest.TestCase):
    def test_export_is_exact_under_crlf_checkout_attributes_and_keeps_binary_bytes(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
            git('init','-q');git('config','user.name','Archive test');git('config','user.email','archive@example.invalid')
            (root/'.gitattributes').write_bytes(b'*.py text eol=crlf\n*.bin -text\n')
            (root/'example.py').write_bytes(b'first\nsecond\n');(root/'asset.bin').write_bytes(b'\x00\xff\r\n\x01')
            git('add','.');git('-c','commit.gpgsign=false','commit','-qm','fixture')
            revision=git('rev-parse','HEAD').decode().strip()
            data,receipt=module.archive_source(root,revision)
            with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
                self.assertEqual(archive.extractfile('example.py').read(),git('show',revision+':example.py'))
                self.assertEqual(archive.extractfile('asset.bin').read(),b'\x00\xff\r\n\x01')
            self.assertTrue(receipt['raw_git_blobs_verified'])
            self.assertEqual(data,module.archive_source(root,revision)[0])
            with self.assertRaises(ValueError):module.archive_source(root,revision,max_bytes=1)

    def test_floating_revision_is_not_source_attestation(self):
        with self.assertRaises(ValueError):module.archive_source('.', 'main')


if __name__=='__main__':unittest.main()
