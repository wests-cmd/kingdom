"""Real workspace and host-process tools. Capability and approval gates stay external."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile

TOOL_CAPABILITIES = {'workspace.read@1.0.0': 'filesystem.read', 'workspace.write@1.0.0': 'filesystem.write',
                     'workspace.list@1.0.0': 'filesystem.read', 'process.run@1.0.0': 'process.execute',
                     'workspace.package@1.0.0': 'filesystem.write',
                     'computer.screenshot@1.0.0': 'computer.observe'}
TOOL_CAPABILITIES['computer.input@1.0.0'] = 'computer.control'


def workspace_path(name='.'):
    root = Path(os.environ.get('KINGDOM_WORKSPACE', 'data/workspace')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    relative = Path(name)
    if relative.is_absolute() or ':' in str(name) or '..' in relative.parts:
        raise ValueError('Use a relative path within the Kingdom workspace')
    target = (root / relative).resolve()
    if not target.is_relative_to(root): raise ValueError('Workspace path escapes its root')
    return target


def read_file(params):
    target = workspace_path(params['path'])
    if target.stat().st_size > 2_000_000: raise ValueError('File is too large for a text tool')
    data = target.read_bytes()
    return {'path': params['path'], 'text': data.decode('utf-8'), 'sha256': hashlib.sha256(data).hexdigest()}


def write_file(params):
    content = params['content']
    if not isinstance(content, str) or len(content.encode()) > 2_000_000: raise ValueError('File exceeds 2 MB')
    target = workspace_path(params['path']); target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        handle.write(content.encode()); temporary = Path(handle.name)
    temporary.replace(target)
    return {'path': params['path'], 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def list_files(params):
    target = workspace_path(params.get('path', '.'))
    return {'path': params.get('path', '.'), 'entries': [{'name': entry.name, 'directory': entry.is_dir()}
            for entry in sorted(target.iterdir())[:1000] if not entry.is_symlink()]}


def run_process(params):
    argv = params.get('argv')
    if not isinstance(argv, list) or not 1 <= len(argv) <= 40 or not all(isinstance(x, str) and 0 < len(x) <= 4000 and '\x00' not in x for x in argv):
        raise ValueError('Supply an argument list, never a shell command string')
    timeout = params.get('timeout_seconds', 60)
    if type(timeout) is not int or not 1 <= timeout <= 120: raise ValueError('Process timeout must be 1–120 seconds')
    cwd = workspace_path(params.get('cwd', '.'))
    env = {key: os.environ[key] for key in ('PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'LANG') if key in os.environ}
    env['PYTHONIOENCODING'] = 'utf-8'
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, shell=False,
            start_new_session=os.name != 'nt', **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        try:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if time.monotonic() >= deadline or os.fstat(output.fileno()).st_size > 2_000_000:
                    raise subprocess.TimeoutExpired(argv, timeout)
                time.sleep(0.05)
            code = process.returncode
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
            raise TimeoutError('Approved process exceeded its time or output budget')
        output.seek(0); text = output.read(65537)
    return {'exit_code': code, 'output': text[:65536].decode('utf-8', errors='replace'),
            'output_truncated': len(text) > 65536, 'cwd': params.get('cwd', '.'),
            'scope': 'Host process with an approved command. Workspace working directory is not an OS sandbox.'}


def screenshot(params):
    from PIL import ImageGrab
    image = ImageGrab.grab()
    target = workspace_path('captures/' + hashlib.sha256(params['_receipt_id'].encode()).hexdigest() + '.png')
    target.parent.mkdir(parents=True, exist_ok=True); image.save(target, format='PNG')
    return {'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'width': image.width, 'height': image.height, 'scope': 'Local desktop capture; not uploaded to a model'}


def package_workspace(params):
    source = workspace_path(params['path'])
    if not source.is_dir(): raise ValueError('Package a workspace project directory')
    target = workspace_path('packages/' + hashlib.sha256(params['_receipt_id'].encode()).hexdigest() + '.zip')
    target.parent.mkdir(parents=True, exist_ok=True)
    files, total = [], 0
    for entry in source.rglob('*'):
        if entry.is_symlink(): raise ValueError('Package cannot contain symbolic links')
        if not entry.is_file() or target.parent == entry.parent: continue
        resolved = workspace_path(str(entry.relative_to(workspace_path())))
        total += resolved.stat().st_size
        files.append(resolved)
        if len(files) > 1000 or total > 20 * 1024 * 1024: raise ValueError('Package exceeds 1000 files or 20 MB')
    if not files: raise ValueError('Project directory is empty')
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle: temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for entry in sorted(files): archive.write(entry, str(entry.relative_to(source)))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'path': str(target.relative_to(workspace_path())), 'files': len(files), 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


COMPUTER_HANDLERS = {'workspace.read@1.0.0': read_file, 'workspace.write@1.0.0': write_file,
                     'workspace.package@1.0.0': package_workspace,
                     'workspace.list@1.0.0': list_files, 'process.run@1.0.0': run_process,
                     'computer.screenshot@1.0.0': screenshot}
from backend.runtime.desktop_control import desktop_input
COMPUTER_HANDLERS['computer.input@1.0.0'] = desktop_input


def receipt(task, output):
    directory = Path('data/computer-receipts'); directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256(task['id'].encode()).hexdigest() + '.json')
    body = json.dumps({'task_id': task['id'], 'tool': task['metadata']['tool'], 'output': output}, sort_keys=True).encode()
    path.write_bytes(body)
    return {'artifact': str(path), 'sha256': hashlib.sha256(body).hexdigest()}


def verify_receipt(task, result):
    path = Path('data/computer-receipts') / (hashlib.sha256(task['id'].encode()).hexdigest() + '.json')
    body = path.read_bytes(); record = json.loads(body)
    if result.get('artifact') != str(path) or hashlib.sha256(body).hexdigest() != result.get('sha256') or record != {'task_id': task['id'], 'tool': task['metadata']['tool'], 'output': result['output']}:
        raise ValueError('Local execution receipt mismatch')
    tool = task['metadata']['tool']
    if tool in {'workspace.write@1.0.0', 'workspace.package@1.0.0'}:
        target = workspace_path(record['output']['path'])
        if hashlib.sha256(target.read_bytes()).hexdigest() != record['output']['sha256']: raise ValueError('Written file changed after execution')
    if tool == 'computer.screenshot@1.0.0':
        if hashlib.sha256(Path(record['output']['path']).read_bytes()).hexdigest() != record['output']['sha256']: raise ValueError('Capture evidence changed')
    return {'state': 'VERIFIED', 'method': 'local_execution_receipt_and_file_evidence',
            'scope': 'Tool execution verified; application correctness requires its own tests'}
