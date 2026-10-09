"""Verified UI-only components: atomic activation without restarting the backend."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from threading import RLock
import zipfile


class UIComponents:
    lock = RLock()
    def __init__(self, backend_version, root='data/ui-components'):
        self.version, self.root = backend_version, Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def status(self):
        pointer = self.root/'active.json'
        state = json.loads(pointer.read_text()) if pointer.exists() else {'active': None, 'previous': None}
        return {**state, 'backend_version': self.version, 'backend_restart_required': False,
                'notice': 'UI-only updates activate on page refresh. Backend and native application changes require a restart and the matching installer.'}

    def directory(self, ident):
        if not re.fullmatch('[a-f0-9]{64}', ident): raise ValueError('Invalid UI component identity')
        return self.root/ident

    def asset(self, ident, resource):
        # Request strings select existing allowlisted files; they never form a path.
        folder=next((path for path in self.root.iterdir() if path.name==ident
                     and re.fullmatch('[a-f0-9]{64}',path.name) and path.is_dir() and not path.is_symlink()),None)
        if folder is None:raise ValueError('Unknown UI component')
        for path in folder.rglob('*'):
            name=path.relative_to(folder).as_posix()
            if name==resource and name.startswith(('assets/','branding/')) and path.is_file() and not path.is_symlink():
                if path.resolve().is_relative_to(folder.resolve()):return path
        raise ValueError('Unknown component asset')

    def _point(self, active, previous):
        with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as handle:
            handle.write(json.dumps({'active':active,'previous':previous}).encode()); temporary=Path(handle.name)
        temporary.replace(self.root/'active.json')

    def install(self, data, expected):
        if len(data)>8*1024*1024 or not re.fullmatch('[a-f0-9]{64}',expected) or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('UI package checksum or size is invalid')
        with self.lock, zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries=archive.infolist()
            if len(entries)>2000 or sum(item.file_size for item in entries)>24*1024*1024:
                raise ValueError('UI package exceeds extraction limits')
            seen=set()
            for item in entries:
                path=PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or item.is_dir() or (item.external_attr>>16)&0o170000==0o120000 or item.filename.casefold() in seen:
                    raise ValueError('Unsafe UI package entry')
                seen.add(item.filename.casefold())
            manifest=json.loads(archive.read('ui-manifest.json'))
            if manifest.get('format')!='kingdom.ui.v1' or self.version not in manifest.get('compatible_backends',[]):
                raise ValueError('Backend upgrade and restart required for this UI package')
            files=manifest.get('files',{})
            if not files or set(files)!={item.filename for item in entries}-{'ui-manifest.json'} or 'index.html' not in files:
                raise ValueError('UI package inventory mismatch')
            for name,digest in files.items():
                if not (name=='index.html' or name.startswith(('assets/','branding/'))) or hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                    raise ValueError('UI package file failed validation')
            target=self.directory(expected)
            target.mkdir(exist_ok=True)
            for name in files:
                destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
                content=archive.read(name)
                if name=='index.html':
                    for prefix in (b'"/',b'"./'):
                        for directory in ('assets','branding'):
                            content=content.replace(prefix+directory.encode()+b'/',f'"/ui/{expected}/{directory}/'.encode())
                destination.write_bytes(content)
            if b'<html' not in (target/'index.html').read_bytes().lower(): raise ValueError('UI entry point is invalid')
            state=self.status()
            self._point(expected,state['active'] if state['active']!=expected else state['previous'])
            return self.status()

    def rollback(self):
        with self.lock:
            state=self.status()
            if not state['active']: raise ValueError('No component update is active')
            self._point(state['previous'],state['active']);return self.status()
