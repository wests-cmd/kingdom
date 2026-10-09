"""Package the built UI separately, with explicit backend compatibility."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def build(dist, output, version):
    dist,output=Path(dist),Path(output)
    files={path.relative_to(dist).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in dist.rglob('*') if path.is_file()}
    if 'index.html' not in files: raise ValueError('Build the frontend first')
    manifest={'format':'kingdom.ui.v1','compatible_backends':[version],'files':files}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files): archive.write(dist/name,name)
        archive.writestr('ui-manifest.json',json.dumps(manifest,sort_keys=True))
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',required=True);parser.add_argument('--dist',default='frontend/dist');parser.add_argument('--output',required=True)
    args=parser.parse_args();print(build(args.dist,args.output,args.version))
