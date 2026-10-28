"""Export exact Git blobs without checkout/archive line-ending conversion."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def archive_source(repository, revision, max_bytes=200*1024*1024):
    if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Pin an exact commit')
    def git(*args,input=None):
        env={key:value for key,value in os.environ.items() if not key.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0')
        return subprocess.run(['git','-c','protocol.allow=never','-c','core.hooksPath='+os.devnull,*args],
                              cwd=repository,input=input,capture_output=True,check=True,env=env,timeout=30).stdout
    if git('cat-file','-t',revision).strip()!=b'commit':raise ValueError('Source must be a commit')
    commit=git('cat-file','commit',revision)
    if len(commit)>1024*1024 or hashlib.sha1(b'commit '+str(len(commit)).encode()+b'\0'+commit).hexdigest()!=revision:
        raise ValueError('Raw commit identity mismatch')
    root_tree=commit.splitlines()[0].removeprefix(b'tree ')
    if not re.fullmatch(b'[a-f0-9]{40}',root_tree):raise ValueError('Invalid root tree identity')
    entries=[('',b'040000',root_tree,b'tree')]
    for row in git('ls-tree','-r','-t','-z',revision).split(b'\0'):
        if not row:continue
        header,name=row.split(b'\t',1);mode,kind,oid=header.split()
        path=name.decode('utf-8');parts=PurePosixPath(path)
        if ((kind,mode) not in {(b'blob',b'100644'),(b'blob',b'100755'),(b'tree',b'040000')}
                or parts.is_absolute() or '..' in parts.parts or '\\' in path):
            raise ValueError('Only contained regular source files are supported')
        entries.append((path,mode,oid,kind))
    if not 1<=len(entries)<=50000:raise ValueError('Source file count exceeds budget')
    queries=b''.join(oid+b'\n' for _,_,oid,_ in entries)
    sizes=git('cat-file','--batch-check',input=queries).splitlines()
    if len(sizes)!=len(entries) or sum(int(line.split()[2]) for line in sizes)>max_bytes:raise ValueError('Source byte budget exceeded')
    data=git('cat-file','--batch',input=queries);position=0;files=[]
    for path,mode,oid,expected_kind in entries:
        end=data.index(b'\n',position);actual,kind,size=data[position:end].split();position=end+1;size=int(size)
        value=data[position:position+size];position+=size+1
        if actual!=oid or kind!=expected_kind or hashlib.sha1(kind+b' '+str(size).encode()+b'\0'+value).hexdigest().encode()!=oid:
            raise ValueError('Raw blob identity mismatch')
        if kind==b'blob':files.append((path,mode,value))
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w') as output:
        dirs=sorted({str(parent) for path,_,_ in files for parent in PurePosixPath(path).parents if str(parent)!='.'},key=lambda p:(len(PurePosixPath(p).parts),p))
        for path in dirs:
            member=tarfile.TarInfo(path);member.type=tarfile.DIRTYPE;member.mode=0o755;output.addfile(member)
        for path,mode,value in files:
            member=tarfile.TarInfo(path);member.mode=0o755 if mode==b'100755' else 0o644;member.size=len(value)
            output.addfile(member,io.BytesIO(value))
    result=gzip.compress(archive.getvalue(),mtime=0)
    return result,{'revision':revision,'files':len(files),'archive_sha256':hashlib.sha256(result).hexdigest(),'raw_git_blobs_verified':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--revision',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();data,receipt=archive_source(a.repository,a.revision)
    with Path(a.output).open('xb') as out:out.write(data)
    print(json.dumps(receipt))
