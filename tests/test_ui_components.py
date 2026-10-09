import hashlib
import io
import json
import zipfile
import pytest
from backend.system.ui_updates import UIComponents


def package(version='1.2.0',html=b'<html><script src="/assets/app.js"></script></html>',extra=None):
    files={'index.html':html,'assets/app.js':b'console.log("loaded")'}
    files.update(extra or {})
    manifest={'format':'kingdom.ui.v1','compatible_backends':[version],
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        for name,data in files.items(): archive.writestr(name,data)
        archive.writestr('ui-manifest.json',json.dumps(manifest))
    data=output.getvalue();return data,hashlib.sha256(data).hexdigest()


def test_atomic_activation_and_rollback_preserve_old_assets(tmp_path):
    service=UIComponents('1.2.0',tmp_path)
    first,digest=package();service.install(first,digest)
    assert service.status()['active']==digest
    assert f'/ui/{digest}/assets/'.encode() in (service.directory(digest)/'index.html').read_bytes()
    second,next_digest=package(html=b'<html>Second interface</html>');service.install(second,next_digest)
    assert service.status()['previous']==digest
    assert (service.directory(digest)/'assets/app.js').exists()
    assert service.rollback()['active']==digest
    assert not service.status()['backend_restart_required']


@pytest.mark.parametrize('bad',['checksum','compatibility','traversal','backend_code','invalid_index'])
def test_rejected_ui_update_keeps_working_selection(tmp_path,bad):
    service=UIComponents('1.2.0',tmp_path)
    original,digest=package();service.install(original,digest)
    if bad=='compatibility': update,checksum=package(version='2.0.0')
    elif bad=='traversal': update,checksum=package(extra={'../outside.js':b'bad'})
    elif bad=='backend_code': update,checksum=package(extra={'backend/main.py':b'bad'})
    elif bad=='invalid_index': update,checksum=package(html=b'not a page')
    else: update,checksum=original,'0'*64
    with pytest.raises(ValueError): service.install(update,checksum)
    assert service.status()['active']==digest


def test_update_identity_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError): UIComponents('1.2.0',tmp_path).directory('../outside')
