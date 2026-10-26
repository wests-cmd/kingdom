"""Operator-owned exact-source external review producer; never a candidate tool.

The signing key stays in this supervisor, outside the disposable API container.
Installing its public key/contract is a separate governed operator action.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
import uuid

CONTEXT = b'kingdom.independent-patch-test.v2\0'
BINDING = {'job_id','project','backlog_id','mission_id','mission_version','step_id',
           'source','base_revision','patch_sha256','contract_sha256'}


def load(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected(path, private=False):
    path = Path(path).absolute()
    if os.name != 'posix' or path.resolve() != path:
        raise ValueError('Protected POSIX paths without symlinks required')
    for entry in [path, *path.parents]:
        value = entry.stat()
        if value.st_uid != 0 or value.st_mode & 0o022:
            raise ValueError('Root-owned non-writable supervisor inputs required')
    if private and path.stat().st_mode & 0o077:
        raise ValueError('Supervisor secret/config must be private')
    return path


def contract_digest():
    names = ['jules-external-review.py', 'jules-source-preparation.py', 'jules-external-oracle.py','archive-verified-source.py']
    files = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names}
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def durable_json(path, value):
    temp=path.with_name(path.name+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as handle:
        json.dump(value,handle,sort_keys=True,indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def cleanup_candidate(name, run_id):
    """Resolve even an unknown docker-run outcome without touching other work."""
    result = subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=10)
    if result.returncode:
        listing = subprocess.run(['docker','container','ls','--all','--filter','name=^/'+name+'$',
            '--format','{{.ID}}'],capture_output=True,text=True,timeout=10)
        return listing.returncode == 0 and not listing.stdout.strip()
    records = json.loads(result.stdout)
    if len(records) != 1 or records[0].get('Config',{}).get('Labels',{}).get('kingdom.external-review-run') != run_id:
        raise ValueError('Candidate cleanup identity mismatch')
    ident = records[0].get('Id','')
    if not re.fullmatch('[a-f0-9]{64}',ident):
        raise ValueError('Invalid cleanup container identity')
    removed = subprocess.run(['docker','rm','--force',ident],capture_output=True,timeout=15)
    return removed.returncode == 0


def sign_payload(key_path, canonical, run):
    """Use the existing host OpenSSL; secret bytes never enter argv/stdout."""
    protected('/usr/bin/openssl')
    seed = key_path.read_bytes()
    if len(seed) != 32:
        raise ValueError('A 32-byte protected Ed25519 seed is required')
    wrapped = run/'signing-key.der'
    message = run/'signed-payload.json'
    try:
        fd = os.open(wrapped,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as handle:
            handle.write(bytes.fromhex('302e020100300506032b657004220420')+seed)
        message.write_bytes(canonical)
        result = subprocess.run(['/usr/bin/openssl','pkeyutl','-sign','-rawin','-keyform','DER',
            '-inkey',str(wrapped),'-in',str(message)],capture_output=True,timeout=10)
        if result.returncode or len(result.stdout) != 64:
            raise ValueError('Protected signing failed')
        return base64.b64encode(result.stdout).decode()
    finally:
        wrapped.unlink(missing_ok=True)


def recover_candidates(root):
    for directory in root.glob('external-*'):
        intent=directory/'container-intent.json'
        if not intent.exists() or (directory/'cleanup-complete').exists():
            continue
        protected(intent)
        if intent.stat().st_size>4096:
            raise ValueError('Invalid retained cleanup intent')
        value=json.loads(intent.read_text(encoding='utf-8'))
        if (value.get('run_id')!=directory.name or
                not re.fullmatch('kingdom-review-[a-f0-9]{16}',value.get('name',''))):
            raise ValueError('Invalid retained candidate identity')
        if not cleanup_candidate(value['name'],value['run_id']):
            raise ValueError('An earlier candidate still needs cleanup; no new candidate launched')
        (directory/'cleanup-complete').write_text('reconciled',encoding='utf-8')


def bounded_logs(container_id,limit=32768,timeout=10):
    process=subprocess.Popen(['docker','logs','--tail','100',container_id],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    data=bytearray()
    deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while len(data)<limit:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):
                    raise TimeoutError('Bounded diagnostic read expired')
                block=os.read(process.stdout.fileno(),min(4096,limit-len(data)))
                if not block:break
                data.extend(block)
        return bytes(data)
    finally:
        if process.poll() is None:process.kill()
        process.wait(timeout=5)
        process.stdout.close()


def finish_candidate(run,container_id,name,run_id):
    try:
        if container_id:
            log_path=run/'candidate-startup.log'
            fd=os.open(log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as handle:handle.write(bounded_logs(container_id))
    except (OSError,subprocess.SubprocessError,TimeoutError):
        pass  # Diagnostic availability must never control candidate teardown.
    finally:
        if not cleanup_candidate(name,run_id):
            raise ValueError('Candidate cleanup needs reconciliation; retained container intent, no replacement launched')
        (run/'cleanup-complete').write_text('removed',encoding='utf-8')


def execute(config_path):
    if not sys.flags.isolated:
        raise ValueError('Launch the protected supervisor with Python -I')
    config_path=protected(config_path,private=True)
    import fcntl
    with (config_path.parent/'review.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        recover_candidates(config_path.parent)
        return _execute(config_path)


def _execute(config_path):
    for name in ['jules-external-review.py','jules-source-preparation.py','jules-external-oracle.py','archive-verified-source.py']:
        protected(Path(__file__).with_name(name))
    config_path = protected(config_path, private=True)
    if config_path.stat().st_size > 65536:
        raise ValueError('Bounded supervisor configuration required')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    binding = config['binding']
    if set(binding) != BINDING or binding['contract_sha256'] != contract_digest():
        raise ValueError('Exact governed supervisor contract required')
    if binding['project'] != 'kingdom' or binding['source'] != 'sources/github/wests-cmd/kingdom':
        raise ValueError('Only the owner-approved Kingdom scope is supported')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', config['reviewer_id']):
        raise ValueError('Bounded reviewer identity required')
    key_path = protected(config['signing_key'], private=True)
    repository = protected(config['repository_directory'])
    # A protected top-level directory does not protect writable object/config
    # descendants. Require an independently installed immutable bare mirror.
    if not (repository/'HEAD').is_file() or not (repository/'objects').is_dir():
        raise ValueError('A protected bare Git mirror is required')
    for entry in repository.rglob('*'):
        protected(entry)
    if (repository/'objects/info/alternates').exists() or list((repository/'objects').rglob('*.promisor')):
        raise ValueError('Git alternates and partial-clone sources are forbidden')
    patch_path = protected(config['patch_file'])
    if patch_path.stat().st_size > 2_000_000:
        raise ValueError('Bounded provider patch required')
    deadline = config['deadline_at']
    if type(deadline) not in (int, float) or not time.time() < deadline <= time.time() + 3600:
        raise ValueError('Finite unexpired supervisor window required')
    root = config_path.parent
    run_id = 'external-' + uuid.uuid4().hex
    run = root / run_id
    prep = load('jules-source-preparation')
    oracle_module = load('jules-external-oracle')
    proof = prep.prepare(repository, binding['base_revision'], patch_path.read_bytes(),
                         binding['patch_sha256'], run, config['allowed_paths'])
    # Candidate source never receives real credentials. Authentication uses a
    # new private tmpfs fixture token, created by the candidate API at startup.
    name = 'kingdom-review-' + uuid.uuid4().hex[:16]
    image = config['image']
    if not re.fullmatch('sha256:[a-f0-9]{64}', image):
        raise ValueError('Pinned installed review image required')
    command = ['docker','run','--detach','--init','--pull=never','--name',name,
               '--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=1',
               '--log-opt','mode=non-blocking','--log-opt','max-buffer-size=256k',
               '--label','kingdom.external-oracle='+binding['base_revision'],
               '--label','kingdom.external-review-run='+run_id,
               '--network','none','--read-only','--cap-drop','ALL',
               '--security-opt','no-new-privileges','--memory','384m','--cpus','0.5',
               '--pids-limit','128','--user','1000:1000',
               '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777',
               '--tmpfs','/data:rw,nosuid,nodev,size=128m,uid=1000,gid=1000,mode=0700',
               '-e','PYTHONPATH=/workspace','-e','KINGDOM_MODEL_PROVIDER=disabled',
               '-v',str(run/'source')+':/workspace:ro','-w','/data',
               '--entrypoint','python',image,'-m','uvicorn','backend.main:app',
               '--host','127.0.0.1','--port','8012','--no-access-log']
    container_id = None
    durable_json(run/'container-intent.json',dict(name=name,run_id=run_id,image=image))
    if time.time()>=deadline:
        raise ValueError('Source preparation consumed the review window; no candidate launched')
    try:
        started = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if started.returncode or not re.fullmatch('[a-f0-9]{64}', started.stdout.strip()):
            raise ValueError('Disposable candidate startup failed')
        container_id = started.stdout.strip()
        # Fixed read of the fixture's generated owner token, kept in memory and
        # private supervisor config only. No production state is mounted.
        token = None
        for _ in range(90):
            if time.time() >= deadline:
                break
            result = subprocess.run(['docker','exec',container_id,'/usr/local/bin/python3','-I','-S','-c',
                "from pathlib import Path;p=Path('/data/data/owner-token');f=p.open('rb');v=f.read(501);f.close();assert 20<=len(v)<=500;print(v.decode().strip())"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and 20 <= len(result.stdout.strip()) <= 500:
                token = result.stdout.strip()
                break
            state=subprocess.run(['docker','inspect','--format','{{.State.Running}}',container_id],
                                 capture_output=True,text=True,timeout=5)
            if state.returncode or state.stdout.strip()!='true':
                raise ValueError('Disposable candidate exited during startup; inspect retained private logs')
            time.sleep(1)
        if not token:
            raise ValueError('Disposable candidate authentication unavailable')
        oracle_config = dict(repository='wests-cmd/kingdom',source=binding['source'],
            revision=binding['base_revision'],image=image,container_name=container_id,
            deadline_at=deadline,candidate_patch_sha256=binding['patch_sha256'],
            source_directory=str(run/'source'),source_tree_sha256=proof['candidate_tree_sha256'],
            test_auth_token=token,output_dir=str(run/'verdict'))
        filename = run/'oracle-config.json'
        durable_json(filename,oracle_config)
        oracle=oracle_module.ExternalOracle(filename)
        oracle.inspect_candidate_container()
        ready=False
        warmup_deadline=min(deadline,time.time()+90)
        while time.time()<warmup_deadline:
            try:
                response=oracle.docker_exec_transport('GET','/health/live',{},None)
                if response['status']==200 and response.get('truncated') is False:
                    ready=True
                    break
            except ValueError:
                pass  # A token file may precede the listening API socket.
            time.sleep(.5)
        if not ready:
            raise ValueError('Disposable candidate never became ready within its bounded startup window')
        record, _ = oracle.run_suite()
        if (prep.tree_digest(run/'source') != proof['candidate_tree_sha256'] or
                time.time() >= deadline):
            raise ValueError('Candidate source changed or review expired')
        counts = record['trusted_test_counts']
        now = time.time()
        payload = dict(format='kingdom.patch-test.v2',receipt_id=run_id,
            reviewer_id=config['reviewer_id'],issued_at=now,expires_at=min(deadline,now+900),
            binding=binding,execution=dict(run_id=run_id,image_sha256=image[7:],
                source_archive_sha256=proof['source_archive_sha256'],
                candidate_tree_sha256=proof['candidate_tree_sha256'],
                argv=['external-controller', '--contract', binding['contract_sha256']],
                test_count=counts['total'],failed_count=counts['failed'],
                exit_code=0 if record['verdict']=='PASSED' else 1,
                network_isolated=True,read_only_source=True,verdict_origin='external_controller'))
        canonical = CONTEXT + json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
        envelope = dict(payload=payload,signature=sign_payload(key_path,canonical,run))
        output = run/'attestation.json'
        durable_json(output,envelope)
        return output
    finally:
        finish_candidate(run,container_id,name,run_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    args = parser.parse_args()
    print(execute(args.config))
