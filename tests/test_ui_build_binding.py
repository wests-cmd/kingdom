import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('ui_updates',Path(__file__).parents[1]/'backend/system/ui_updates.py')
ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)


def package(build):
    content=b'<html>Reviewed interface</html>'
    manifest={'format':'kingdom.ui.v1','compatible_backends':['1.2.4'],'compatible_backend_builds':[build], 'files':{'index.html':hashlib.sha256(content).hexdigest()}}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('index.html',content)
        archive.writestr('ui-manifest.json',json.dumps(manifest))
    raw=stream.getvalue();return raw,hashlib.sha256(raw).hexdigest()


class BuildBindingTests(unittest.TestCase):
    def test_native_build_change_with_same_version_uses_bundled_ui(self):
        with tempfile.TemporaryDirectory() as root:
            old=ui.UIComponents('1.2.4',root,backend_identity='a'*40)
            raw,digest=package('a'*40);old.install(raw,digest)
            self.assertEqual(ui.UIComponents('1.2.4',root,backend_identity='a'*40).status()['active'],digest)
            new=ui.UIComponents('1.2.4',root,backend_identity='b'*40)
            self.assertIsNone(new.status()['active'])
            self.assertEqual(new.status()['inactive_component'],digest)
            self.assertTrue(old.directory(digest).exists())
            with self.assertRaises(ValueError):new.install(raw,digest)
            with self.assertRaises(ValueError):new.rollback()

    def test_legacy_pointer_cannot_hide_new_native_interface(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'active.json').write_text(json.dumps({'active':'c'*64,'previous':None}))
            service=ui.UIComponents('1.2.4',root,backend_identity='b'*40)
            self.assertIsNone(service.status()['active'])
            raw,digest=package('b'*40)
            self.assertEqual(service.install(raw,digest)['active'],digest)
            self.assertEqual(json.loads(Path(root,'active.json').read_text())['backend_identity'],'b'*40)


if __name__=='__main__':unittest.main()
