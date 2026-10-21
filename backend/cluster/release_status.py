"""Observed source fingerprints and owner-approved release reconciliation, never an updater."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import sys
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

SOURCE_SCOPE = 'backend-python-and-built-ui-v1'


class ReleaseReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = Field(min_length=1,max_length=80,pattern=r'^[A-Za-z0-9_.+-]+$')
    revision: str | None = Field(default=None,pattern=r'^[0-9a-f]{40}$')
    source_sha256: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    artifact_sha256: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    source_scope: str = Field(default=SOURCE_SCOPE,pattern='^'+SOURCE_SCOPE+'$')
    update_adapter: Literal['configured','absent','invalid','unknown'] = 'unknown'
    source_evidence: Literal['observed_files','build_input_manifest','unknown'] = 'unknown'


class DesiredRelease(ReleaseReport):
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    auto_reconcile: bool = False


def _hash_files(root,signature):
    digest=hashlib.sha256()
    for name,_,_ in signature:
        path=Path(root)/name
        content=path.read_bytes()
        if name.startswith('backend/') and name.endswith('.py'):
            content=content.replace(b'\r\n',b'\n')
        digest.update(name.encode()+b'\0'+content+b'\0')
    return digest.hexdigest()


def local_release(root=None):
    from backend.state import STATE
    if getattr(sys,'frozen',False):
        metadata={}
        try:
            manifest=Path(sys._MEIPASS)/'kingdom-release.json'
            metadata=ReleaseReport.model_validate(json.loads(manifest.read_text(encoding='utf-8-sig'))).model_dump()
        except (AttributeError,OSError,ValueError):pass
        return ReleaseReport(version=metadata.get('version',STATE.get('version','unknown')),
            revision=metadata.get('revision'),source_sha256=metadata.get('source_sha256'),
            source_evidence='build_input_manifest' if metadata.get('source_sha256') else 'unknown',
            artifact_sha256=None).model_dump()
    root=Path(root or Path(__file__).resolve().parents[2]).resolve()
    files=sorted([*root.glob('backend/**/*.py'),*root.glob('frontend/dist/**/*')])
    files=[path for path in files if path.is_file() and '__pycache__' not in path.parts]
    signature=tuple((path.relative_to(root).as_posix(),path.stat().st_size,path.stat().st_mtime_ns) for path in files)
    digest=_hash_files(str(root),signature) if (root/'backend/main.py').is_file() else None
    metadata={}
    manifest=os.environ.get('KINGDOM_RELEASE_MANIFEST')
    if manifest:
        try:metadata=ReleaseReport.model_validate(json.loads(Path(manifest).read_text(encoding='utf-8-sig'))).model_dump()
        except (OSError,ValueError):metadata={}
    adapter='absent'
    if os.environ.get('KINGDOM_KNIGHT_UPDATE_PROFILE'):
        try:
            from backend.runtime.knight_updates import load_profile
            load_profile(os.environ['KINGDOM_KNIGHT_UPDATE_PROFILE']);adapter='configured'
        except (OSError,ValueError,KeyError):adapter='invalid'
    return ReleaseReport(version=STATE.get('version','unknown'),update_adapter=adapter,revision=metadata.get('revision'),
                         artifact_sha256=metadata.get('artifact_sha256'),source_sha256=digest,
                         source_evidence='observed_files' if digest else 'unknown').model_dump()



def reconciliation(report,desired,fresh=True):
    if not fresh:return 'stale'
    if report is None:return 'unknown'
    try:report=ReleaseReport.model_validate(report).model_dump()
    except ValueError:return 'unknown'
    if desired is None:return 'unconfigured'
    if report['source_sha256'] is None:return 'unknown'
    for key in ('revision','artifact_sha256'):
        if desired.get(key) and not report.get(key):return 'unknown'
        if desired.get(key) and report[key] != desired[key]:return 'update_required'
    if report['source_sha256'] != desired['source_sha256'] or report['version'] != desired['version']:
        return 'update_required'
    return 'current'


class ReleasePreferences:
    def __init__(self,database,publish):self.db,self.publish=database,publish

    def get(self):
        with self.db.get_connection() as connection:
            row=connection.execute("SELECT value_json FROM runtime_state WHERE key='desired_release'").fetchone()
        return json.loads(row[0]) if row else None

    def set(self,request):
        desired=DesiredRelease.model_validate(request).model_dump()
        desired.update(approved_at=time.time(),approved_by='owner')
        with self.db.get_connection() as connection:
            connection.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES('desired_release',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(json.dumps(desired),time.time()))
            connection.commit()
        self.publish('cluster.desired_release_changed',{'source_sha256':desired['source_sha256'],'version':desired['version']})
        return desired

    def status(self,peers,now=None):
        from backend.cluster.apprentice_inventory import aggregate_inventories
        desired=self.get();local=local_release()
        reports=aggregate_inventories([],peers,now=now)['reports']
        rows=[{'id':'local','installed':local,'freshness':'current','status':reconciliation(local,desired),
               'action':'Use the installation-specific approved updater; this endpoint does not install code.'}]
        for row in reports:
            rows.append({'id':row['kingdom_id'],'installed':row.get('release'),'freshness':row['state'],
                         'status':reconciliation(row.get('release'),desired,fresh=row['state']=='current') if row['state']!='missing' else 'unknown',
                         'action':'Inspect the owner-installed update adapter and its exact-digest receipt before activation.'})
        return {'desired':desired,'knights':rows,'auto_install_supported':False,
                'notice':'Source fingerprints cover backend Python (CRLF normalized) and exact built UI bytes, not dependencies or OS. Frozen builds identify declared build inputs, not observed source files or a verified installer artifact. Signed reports attest identity, not independent filesystem proof. Auto-reconcile records desired state only; it never grants update authority.'}
