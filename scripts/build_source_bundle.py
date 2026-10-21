"""Build a source-service preview from an immutable Git revision and built UI."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def build(repository,output):
    repository=Path(repository).resolve();output=Path(output).resolve()
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=repository).strip():
        raise ValueError('Commit tracked source changes before packaging')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
    snapshot=subprocess.check_output(['git','archive','--format=zip',revision],cwd=repository)
    files={}
    with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():continue
            name=entry.filename
            # A source preview must not carry an older prebuilt native backend.
            # Native installers have a separate tested release pipeline.
            if name.startswith('desktop/bin/'):continue
            if name.startswith('data/') and name.endswith('/nothing'):continue
            if name.startswith(('data/','.venv/','node_modules/')) or name=='.env':
                raise ValueError('Runtime/private data must not be tracked in a source release')
            files[name]=archive.read(entry)
    dist=repository/'frontend/dist'
    if not (dist/'index.html').is_file():raise ValueError('Build frontend first')
    for path in dist.rglob('*'):
        if path.is_file():files[path.relative_to(repository).as_posix()]=path.read_bytes()
    files['START-HERE.md']=('''# Kingdom source-service preview

This preview includes source code and a built browser interface. It is not a
signed native installer. Python 3.12 and an internet connection for dependency
installation are required. No model, provider account or external drive is
automatically connected.

Extract to a new directory and open a terminal there:

    python -m venv .venv

Windows:

    .venv\\Scripts\\python -m pip install -r requirements-release.txt
    .venv\\Scripts\\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8012

Linux/macOS:

    .venv/bin/python -m pip install -r requirements-release.txt
    .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8012

Open http://127.0.0.1:8012 and follow owner authentication. Keep data/ private.
Use the guided worker connections in Talk & work. External vault configuration
and removable-device behavior are documented in docs/VAULT_AND_DEVICE_LAYOUT.md.
Back up existing state before upgrades. Use a separate port/data directory for a
trial installation; do not start two controllers on one live state database.
''').encode()
    manifest={'format':'kingdom.source-service.v1','revision':revision,
              'scope':'source-service preview; native installer certification separate',
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}}
    files['source-bundle.json']=json.dumps(manifest,indent=2).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):archive.writestr(name,data)
    return {'revision':revision,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':len(files),'output':str(output)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],args.output)))
