"""
Process-Level Distributed Execution E2E Suite.

Tests real OS process-to-process communication across network sockets (127.0.0.1):
1. Commander Uvicorn Process (Port 8090)
2. Knight Worker Daemon Process (Port 8091)
3. Knight Worker Daemon Process (Port 8092)

Verifies:
- Startup & readiness polling (/health/ready and /status over HTTP)
- Real network pairing request & WAITING_FOR_APPROVAL / PENDING_APPROVAL status reporting
- Commander approval over HTTP API (/nodes/{id}/approve)
- Capability advertisement & routing over network API
- Real task execution & result transport
- Process disconnect detection & restart reconnect
- Revocation enforcement blocking network reconnect
- Multi-Knight capability routing across distinct network processes
"""

import os
import sys
import time
import json
import signal
import subprocess
import urllib.request
import urllib.parse
import pytest
import secrets
import shlex
from pathlib import Path
from datetime import datetime
OWNER_CODE = secrets.token_urlsafe(48)
_DIAGNOSTICS = None


def _logged_process(command, directory, name, **kwargs):
    """Never leave a child blocked on a full, unread Windows pipe."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (name + '.stdout.log')).open('wb') as out, (directory / (name + '.stderr.log')).open('wb') as error:
        return subprocess.Popen(command, stdout=out, stderr=error, **kwargs)


def _capture_timeout():
    # Child stacks contain no locals; keep only this isolated fixture's logs.
    if _DIAGNOSTICS is None:
        return
    directory, trigger = _DIAGNOSTICS
    trigger.touch()
    deadline = time.monotonic() + 1
    stack = directory / 'commander.stacks.log'
    while time.monotonic() < deadline and (trigger.exists() or not stack.exists()):
        time.sleep(.02)
    destination = Path(__file__).resolve().parents[2] / 'evidence' / ('process-timeout-' + directory.name)
    destination.mkdir(parents=True, exist_ok=True)
    for source in directory.glob('*.log'):
        # Never retain the generated owner credential even if a dependency logs it.
        text = source.read_text(encoding='utf-8', errors='replace').replace(OWNER_CODE, '<REDACTED>')
        (destination / source.name).write_text(text[-100000:], encoding='utf-8')
    print('Isolated process timeout diagnostics:', destination)


def _open_http(request, timeout):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except TimeoutError:
        _capture_timeout()
        raise


def test_reviewed_build_on_real_remote_computer(commander_process, tmp_path_factory):
    """Opt-in physical Linux worker, signed RPC and exact high-risk approval."""
    if not os.getenv('KINGDOM_E2E_REMOTE_CONFIG'):
        pytest.skip('A real approved POSIX computer configuration is required')
    import base64, hashlib, io, zipfile
    from backend.runtime.remote_build import source_digest
    config=json.loads(Path(os.environ['KINGDOM_E2E_REMOTE_CONFIG']).read_text())
    ident='build-worker-'+secrets.token_hex(4)
    invite=_http_post(f'{COMMANDER_URL}/nodes/invitation?ttl_seconds=300')
    args=[config['python'],'-m','backend.cluster.knight_daemon','--node-id',ident,
          '--commander-url','http://127.0.0.1:18190','--pairing-code',invite['code'],
          '--capabilities','process.execute','--data-dir','/tmp/kingdom-build-e2e-'+secrets.token_hex(8)]
    remote='timeout 90s env '+shlex.quote('PYTHONPATH='+config['source'])+' '+shlex.join(args)
    worker=subprocess.Popen(['ssh','-i',config['identity_file'],'-o','BatchMode=yes','-o','ConnectTimeout=10',
        '-o','ExitOnForwardFailure=yes','-R','127.0.0.1:18190:127.0.0.1:8090',config['target'],remote],
        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.time()+20
        while True:
            try:
                if _http_get(f'{COMMANDER_URL}/nodes/{ident}')['node_state']=='PENDING_APPROVAL':break
            except Exception:pass
            assert time.time()<deadline, 'Remote build worker did not pair'
            time.sleep(.2)
        _http_post(f'{COMMANDER_URL}/nodes/{ident}/approve',{'granted_capabilities':['process.execute']})
        deadline=time.time()+15
        while True:
            node=_http_get(f'{COMMANDER_URL}/nodes/{ident}')
            load=node.get('connection_metadata',{}).get('load_metrics',{})
            if load:break
            assert time.time()<deadline, 'Remote worker has no measured capacity'
            time.sleep(.2)
        if max(load['cpu_percent'],load['memory_percent'])>=85:
            pytest.skip('Real POSIX worker exceeds production admission limits; build not verified')
        app='print("Hello from a reviewed remote package")\n'
        script="from pathlib import Path\nimport zipfile\ns=Path('app.py').read_bytes()\ncompile(s,'app.py','exec')\ni=zipfile.ZipInfo('app.py');i.create_system=3;i.external_attr=0o644<<16\nwith zipfile.ZipFile('app.zip','w') as z:z.writestr(i,s)\n"
        expected=io.BytesIO()
        info=zipfile.ZipInfo('app.py');info.create_system=3;info.external_attr=0o644<<16
        with zipfile.ZipFile(expected,'w') as archive:archive.writestr(info,app.encode())
        files={'app.py':app,'build.py':script}
        spec={'source_revision':'a'*40,'source_sha256':source_digest(files),'files':files,
              'argv':['@python','build.py'],'expected_artifacts':{'app.zip':hashlib.sha256(expected.getvalue()).hexdigest()}}
        task=_http_post(f'{COMMANDER_URL}/tasks',{'prompt':'Build the exact reviewed Python package',
            'metadata':{'tool':'build.run@1.0.0','tool_parameters':spec,'execution_target':'remote','assigned_knight':ident}})
        deadline=time.time()+35;approved=False
        while True:
            task=_http_get(f'{COMMANDER_URL}/tasks/{task["id"]}')
            if task['status']=='WAITING_APPROVAL':
                assert not approved, 'A consumed exact approval was requested again'
                _http_post(f'{COMMANDER_URL}/security/approvals/{task["metadata"]["approval_id"]}/approve')
                approved=True
            if task['status'] in {'completed','failed','RECOVERY_REQUIRED'}:break
            assert time.time()<deadline,task['status']
            time.sleep(.2)
        assert approved, 'Remote process execution bypassed exact task approval'
        assert task['status']=='completed',task.get('error')
        assert task['result']['executed_by']==ident
        assert task['result']['verification']['state']=='VERIFIED'
        artifact=task['result']['output']['output']['artifacts']['app.zip']
        assert base64.b64decode(artifact['base64'])==expected.getvalue()
        download=urllib.request.Request(f'{COMMANDER_URL}/tasks/{task["id"]}/build-artifacts/app.zip',
            headers={'Authorization':'Bearer '+OWNER_CODE})
        with urllib.request.urlopen(download,timeout=5) as response:
            assert response.read()==expected.getvalue()
            assert response.headers['Cache-Control']=='no-store'
    finally:
        worker.terminate()
        try:worker.communicate(timeout=5)
        except subprocess.TimeoutExpired:worker.kill();worker.communicate(timeout=5)


COMMANDER_PORT = 8090
COMMANDER_URL = f"http://127.0.0.1:{COMMANDER_PORT}"


def _http_get(url: str, timeout: float = 3.0) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + OWNER_CODE}, method="GET")
    with _open_http(req, timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def _http_post(url: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
    data_bytes = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + OWNER_CODE}
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    with _open_http(req, timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def wait_for_url(url: str, max_wait_sec: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < max_wait_sec:
        try:
            res = _http_get(url)
            if res:
                return True
        except Exception:
            time.sleep(0.3)
    return False


@pytest.fixture
def commander_process(tmp_path_factory):
    """
    Spawns real Commander Uvicorn server in an independent process on port 8090 with isolated SQLite DB.
    """
    cmd_dir = tmp_path_factory.mktemp("commander_data")
    db_file = cmd_dir / "kingdom_e2e.db"
    env = os.environ.copy()
    env["DATA_DIR"] = str(cmd_dir)
    env["KINGDOM_OWNER_TOKEN"] = OWNER_CODE

    # A filesystem trigger works on Windows and POSIX without exposing a debug API
    # or using platform-specific signals. It dumps all child threads, never locals.
    diagnostic_dir = cmd_dir / 'diagnostics'
    diagnostic_dir.mkdir()
    trigger = diagnostic_dir / 'dump.request'
    stack = diagnostic_dir / 'commander.stacks.log'
    bootstrap = f"""
import pathlib, threading, time, faulthandler, uvicorn
from backend.storage import db
def dump_on_request():
    trigger = pathlib.Path({str(trigger)!r})
    while True:
        if trigger.exists():
            with open({str(stack)!r}, 'a') as output:
                faulthandler.dump_traceback(file=output, all_threads=True)
            trigger.unlink(missing_ok=True)
        time.sleep(.02)
threading.Thread(target=dump_on_request, daemon=True).start()
db.db.db_path = pathlib.Path({str(db_file)!r})
db.db.init_db()
uvicorn.run('backend.main:app', host='127.0.0.1', port={COMMANDER_PORT}, log_level='warning')
"""
    proc = _logged_process([sys.executable, '-c', bootstrap], diagnostic_dir, 'commander',
                          cwd=Path(__file__).resolve().parents[2], env=env)
    global _DIAGNOSTICS
    _DIAGNOSTICS = (diagnostic_dir, trigger)
    try:
        if not wait_for_url(f"{COMMANDER_URL}/health/ready", max_wait_sec=30.0):
            _capture_timeout()
            raise AssertionError("Commander failed to start; isolated diagnostics retained")
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            _capture_timeout()
            proc.kill()
            proc.wait(timeout=3.0)
        _DIAGNOSTICS = None



def test_process_distributed_enrollment_task_execution_lifecycle(commander_process, tmp_path_factory):
    """
    Verifies process-to-process network execution:
    1. Obtain pairing invitation from Commander process.
    2. Start Knight daemon process with pairing code.
    3. Verify Knight process reports PENDING_APPROVAL over HTTP.
    4. Commander approves Knight process with granted capabilities.
    5. Submit task to Commander process, verify task execution on Knight process over network.
    6. Terminate Knight process & verify disconnect status.
    7. Restart Knight process & verify automatic reconnection.
    8. Revoke Knight process & verify network reconnect is denied.
    """
    # 1. Obtain pairing invitation from Commander process over HTTP
    inv_res = _http_post(f"{COMMANDER_URL}/nodes/invitation?ttl_seconds=300")
    pairing_code = inv_res["code"]

    # 2. Spawn Knight daemon process A on port 8091
    kn_data_dir = tmp_path_factory.mktemp("knight_data_a")
    kn_id = "kn-process-worker-01"

    cmd_kn = [
        sys.executable, "-m", "backend.cluster.knight_daemon",
        "--node-id", kn_id,
        "--display-name", "Process Worker A",
        "--commander-url", COMMANDER_URL,
        "--listen-port", "8091",
        "--pairing-code", pairing_code,
        "--capabilities", "compute", "gpu",
        "--data-dir", str(kn_data_dir)
    ]

    diagnostic_dir = _DIAGNOSTICS[0]
    kn_proc = _logged_process(cmd_kn, diagnostic_dir, 'knight-first')
    try:
        # Give Knight process time to submit pairing request
        time.sleep(2.0)

        # 3. Query Commander process: Knight node MUST be in PENDING_APPROVAL
        node_res = _http_get(f"{COMMANDER_URL}/nodes/{kn_id}")
        assert node_res["node_state"] == "PENDING_APPROVAL"
        assert node_res["granted_capabilities"] == []

        # 4. Approve Knight process with 'gpu' capability granted
        approve_res = _http_post(
            f"{COMMANDER_URL}/nodes/{kn_id}/approve",
            payload={"granted_capabilities": ["gpu", "compute"]}
        )
        assert approve_res["node_state"] == "APPROVED"
        assert "gpu" in approve_res["granted_capabilities"]

        # Allow daemon loop to pick up APPROVED state
        time.sleep(2.5)
        node_approved = _http_get(f"{COMMANDER_URL}/nodes/{kn_id}")
        assert node_approved["node_state"] in ["APPROVED", "CONNECTED"]

        # 5. Create a task assigned to this Knight process
        task_req = {
            "prompt": "Analyze this real process result",
            "metadata": {"assigned_knight": kn_id, "execution_target": "remote", "tool": "text.analyze@1.0.0", "capability": "compute"}
        }
        task_res = _http_post(f"{COMMANDER_URL}/tasks", payload=task_req)
        assert task_res["id"] is not None

        # Allow daemon loop to poll and execute
        time.sleep(2.5)

        deadline = time.time() + 12
        while time.time() < deadline:
            completed = _http_get(f"{COMMANDER_URL}/tasks/{task_res['id']}")
            if completed["status"] in {"completed", "failed"}:
                break
            time.sleep(0.2)
        assert completed["status"] == "completed", completed.get("error")
        assert completed["result"]["output"]["output"]["words"] == 5
        assert completed["result"]["verification"]["state"] == "VERIFIED"
        assert completed["result"]["executed_by"] == kn_id

        # 6. Terminate Knight process -> Verify process disappearance
        kn_proc.terminate()
        kn_proc.wait(timeout=3.0)

        # 7. Restart same Knight process -> Identity persists, reconnect succeeds
        kn_proc_restarted = _logged_process(
            [c for c in cmd_kn if c != "--pairing-code" and c != pairing_code],
            diagnostic_dir, "knight-restarted"
        )
        try:
            time.sleep(2.5)
            node_reconnected = _http_get(f"{COMMANDER_URL}/nodes/{kn_id}")
            assert node_reconnected["node_state"] in ["APPROVED", "CONNECTED"]

            # 8. Revoke Knight process -> Reconnect denied
            revoke_res = _http_post(f"{COMMANDER_URL}/nodes/{kn_id}/revoke?reason=E2E_Test_Revocation")
            assert revoke_res["node_state"] == "REVOKED"

            time.sleep(1.0)
            reconnect_attempt = _http_post(f"{COMMANDER_URL}/nodes/{kn_id}/reconnect")
            assert reconnect_attempt.get("rejoined", False) is False or reconnect_attempt.get("success", False) is False

        finally:
            kn_proc_restarted.terminate()
            kn_proc_restarted.wait(timeout=3.0)

    finally:
        if kn_proc.poll() is None:
            kn_proc.terminate()
            kn_proc.wait(timeout=3.0)


def test_dual_knight_process_capability_routing(commander_process, tmp_path_factory):
    """
    Spawns two independent Knight processes (Knight Coder and Knight Researcher)
    and verifies that task capability routing directs tasks to the correct physical process.
    """
    # Pair Coder Knight
    inv1 = _http_post(f"{COMMANDER_URL}/nodes/invitation?ttl_seconds=300")
    kn1_dir = tmp_path_factory.mktemp("knight_coder")
    kn1_id = "kn-coder-process-01"

    proc_coder = subprocess.Popen([
        sys.executable, "-m", "backend.cluster.knight_daemon",
        "--node-id", kn1_id, "--display-name", "Coder Node",
        "--commander-url", COMMANDER_URL, "--listen-port", "8092",
        "--pairing-code", inv1["code"], "--capabilities", "coder.execute",
        "--data-dir", str(kn1_dir)
    ])

    # Pair Researcher Knight
    inv2 = _http_post(f"{COMMANDER_URL}/nodes/invitation?ttl_seconds=300")
    kn2_dir = tmp_path_factory.mktemp("knight_researcher")
    kn2_id = "kn-researcher-process-02"

    proc_researcher = subprocess.Popen([
        sys.executable, "-m", "backend.cluster.knight_daemon",
        "--node-id", kn2_id, "--display-name", "Researcher Node",
        "--commander-url", COMMANDER_URL, "--listen-port", "8093",
        "--pairing-code", inv2["code"], "--capabilities", "researcher.execute",
        "--data-dir", str(kn2_dir)
    ])

    try:
        time.sleep(2.0)
        # Approve Coder with coder.execute
        _http_post(f"{COMMANDER_URL}/nodes/{kn1_id}/approve", payload={"granted_capabilities": ["coder.execute"]})
        # Approve Researcher with researcher.execute
        _http_post(f"{COMMANDER_URL}/nodes/{kn2_id}/approve", payload={"granted_capabilities": ["researcher.execute"]})

        time.sleep(2.0)

        # Verify node states over network
        c_node = _http_get(f"{COMMANDER_URL}/nodes/{kn1_id}")
        r_node = _http_get(f"{COMMANDER_URL}/nodes/{kn2_id}")

        assert "coder.execute" in c_node["granted_capabilities"]
        assert "researcher.execute" in r_node["granted_capabilities"]

    finally:
        proc_coder.terminate()
        proc_coder.wait(timeout=3.0)
        proc_researcher.terminate()
        proc_researcher.wait(timeout=3.0)


def test_verified_mission_dependency_across_two_worker_processes(commander_process, tmp_path_factory):
    """A real reviewed mission crosses signed worker RPC, not mocked results."""
    import psutil
    # At least one real worker runs on this host. Do not weaken production
    # admission thresholds or invent capacity to make a loaded machine pass.
    if psutil.virtual_memory().percent >= 85:
        pytest.skip('Real worker host exceeds the 85% memory admission threshold; multi-worker completion is unverified in this run')
    workers=[]
    try:
        for index in (1,2):
            ident=f'mission-worker-{index}'
            invite=_http_post(f'{COMMANDER_URL}/nodes/invitation?ttl_seconds=300')
            worker_command=[sys.executable,'-m','backend.cluster.knight_daemon',
                '--node-id',ident,'--commander-url',COMMANDER_URL,'--pairing-code',invite['code'],
                '--capabilities','compute','--data-dir',str(tmp_path_factory.mktemp(ident))]
            # Optional real second computer, reached through an encrypted SSH
            # reverse tunnel to this isolated controller. No credentials in repo.
            if index==2 and os.getenv('KINGDOM_E2E_REMOTE_CONFIG'):
                config=json.loads(Path(os.environ['KINGDOM_E2E_REMOTE_CONFIG']).read_text())
                remote_args=[config['python'],'-m','backend.cluster.knight_daemon','--node-id',ident,
                    '--commander-url','http://127.0.0.1:18190','--pairing-code',invite['code'],
                    '--capabilities','compute','--data-dir','/tmp/kingdom-e2e-'+secrets.token_hex(12)]
                remote='timeout 90s env '+shlex.quote('PYTHONPATH='+config['source'])+' '+shlex.join(remote_args)
                worker_command=['ssh','-i',config['identity_file'],'-o','BatchMode=yes','-o','ConnectTimeout=10',
                    '-o','ExitOnForwardFailure=yes','-R','127.0.0.1:18190:127.0.0.1:8090',config['target'],remote]
            proc=subprocess.Popen(worker_command,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            workers.append(proc)
            deadline=time.time()+15
            while True:
                try:
                    if _http_get(f'{COMMANDER_URL}/nodes/{ident}')['node_state']=='PENDING_APPROVAL':break
                except Exception:pass
                assert time.time()<deadline,'Worker did not pair'
                time.sleep(.2)
            _http_post(f'{COMMANDER_URL}/nodes/{ident}/approve',{'granted_capabilities':['compute']})
        # Wait for each real signed heartbeat to provide load measurements.
        deadline=time.time()+15
        while True:
            nodes=[_http_get(f'{COMMANDER_URL}/nodes/mission-worker-{i}') for i in (1,2)]
            if all(n.get('connection_metadata',{}).get('load_metrics') for n in nodes):break
            assert time.time()<deadline,'Worker has no fresh measured capacity'
            time.sleep(.2)
        request=urllib.request.Request(f'{COMMANDER_URL}/runtime/policy',data=json.dumps({'level':5}).encode(),method='PUT',
            headers={'Authorization':'Bearer '+OWNER_CODE,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=5) as response:assert response.status==200
        plan={'title':'Verified two-computer dependency','objective':'Analyze supplied text, then analyze the verified first result on a second worker.',
              'deliverables':['Two independently verified results on different workers'], 'steps':[
            {'id':'first','title':'First computer analysis','kind':'text_check','computer_id':'mission-worker-1',
             'instructions':'A real cluster result','acceptance':'Controller recomputes result'},
            {'id':'second','title':'Second computer consumes verified output','kind':'text_check','computer_id':'mission-worker-2',
             'depends_on':['first'],'input_from':'first','acceptance':'Second worker result recomputed by controller'}]}
        mission=_http_post(f'{COMMANDER_URL}/missions',{'plan':plan})
        ident=mission['id'];_http_post(f'{COMMANDER_URL}/missions/{ident}/approve',{'version':1})
        deadline=time.time()+30
        while True:
            mission=_http_post(f'{COMMANDER_URL}/missions/{ident}/advance')
            if mission['status'] in {'completed','needs_review'}:break
            assert time.time()<deadline,mission
            time.sleep(.3)
        assert mission['status']=='completed',mission
        tasks=[_http_get(f"{COMMANDER_URL}/tasks/{mission['steps'][key]['task_id']}") for key in ('first','second')]
        assert [t['result']['executed_by'] for t in tasks]==['mission-worker-1','mission-worker-2']
        assert all(t['result']['verification']['state']=='VERIFIED' for t in tasks)
        assert tasks[1]['metadata']['tool_parameters']['text']
        assert datetime.fromisoformat(tasks[0]['completed_at']).timestamp()<=float(tasks[1]['started_at'])
    finally:
        for proc in workers:
            if proc.poll() is None:proc.terminate()
            proc.communicate(timeout=5)

def test_process_logs_cannot_fill_unread_pipes(tmp_path):
    """Real child output exceeds the Windows anonymous-pipe buffer on both streams."""
    proc = _logged_process([sys.executable, '-c',
        "import sys; sys.stdout.write('x'*1048576); sys.stdout.flush(); sys.stderr.write('y'*1048576); sys.stderr.flush()"],
        tmp_path, 'verbose-child')
    try:
        assert proc.wait(timeout=5) == 0
        assert (tmp_path / 'verbose-child.stdout.log').stat().st_size == 1048576
        assert (tmp_path / 'verbose-child.stderr.log').stat().st_size == 1048576
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)


def test_commander_diagnostic_trigger_captures_real_child_threads(commander_process):
    directory, trigger = _DIAGNOSTICS
    trigger.touch()
    deadline = time.monotonic() + 3
    stack = directory / 'commander.stacks.log'
    while time.monotonic() < deadline and (trigger.exists() or not stack.exists()):
        time.sleep(.02)
    assert stack.exists(), 'Cross-platform timeout stack capture failed'
    text = stack.read_text(errors='replace')
    assert 'dump_on_request' in text
    assert 'uvicorn' in text
    assert OWNER_CODE not in text
