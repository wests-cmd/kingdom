"""Reconnect explicit owner-configured, pinned loopback SSH links. No discovery or grants."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid


def validate_link(link):
    if not isinstance(link, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', link.get('name', '')):
        raise ValueError('Each link needs a bounded public name')
    argv = link.get('argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(v, str) or '\x00' in v for v in argv):
        raise ValueError('Supply explicit SSH argument strings')
    if Path(argv[0]).name.lower() not in {'ssh', 'ssh.exe'}:
        raise ValueError('Only an SSH executable is supported')
    options, forwards, destination = {}, 0, None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == '-N':
            index += 1
            continue
        if arg in {'-F', '-i', '-o', '-L', '-R', '-p'}:
            if index + 1 >= len(argv):
                raise ValueError('SSH option lacks its argument')
            value = argv[index + 1]
            if arg == '-o':
                key, separator, setting = value.partition('=')
                allowed = {'stricthostkeychecking', 'batchmode', 'exitonforwardfailure',
                           'serveraliveinterval', 'serveralivecountmax', 'connecttimeout'}
                if not separator or key.lower() not in allowed or key.lower() in options:
                    raise ValueError('Unsupported or duplicate SSH option')
                options[key.lower()] = setting.lower()
            elif arg in {'-L', '-R'}:
                # An explicit loopback listener is mandatory on both ends.
                match = re.fullmatch(r'(127\.0\.0\.1|localhost):([0-9]{1,5}):(127\.0\.0\.1|localhost):([0-9]{1,5})', value)
                if not match or any(not 1 <= int(match.group(n)) <= 65535 for n in (2, 4)):
                    raise ValueError('Forward endpoints must be explicit loopback ports')
                forwards += 1
            elif arg == '-p' and (not value.isdigit() or not 1 <= int(value) <= 65535):
                raise ValueError('Invalid SSH port')
            index += 2
            continue
        if arg.startswith('-') or destination is not None or index != len(argv) - 1:
            raise ValueError('SSH remote commands and unsupported arguments are forbidden')
        destination = arg
        index += 1
    if not destination or not forwards or '-N' not in argv:
        raise ValueError('Require one destination, a forward and no remote command')
    for key in ('stricthostkeychecking', 'batchmode', 'exitonforwardfailure'):
        if options.get(key) != 'yes':
            raise ValueError('Pinned host keys, batch mode and forward failure checking are required')
    for key in ('serveraliveinterval', 'serveralivecountmax', 'connecttimeout'):
        value = options.get(key, '')
        if not value.isdigit() or not 1 <= int(value) <= 60:
            raise ValueError('Explicit bounded keepalive and connection timeouts are required')
    return {'name': link['name'], 'argv': argv}


class ProcessLock:
    def __init__(self, path):
        self.path = Path(path)
        self.token = uuid.uuid4().hex

    def acquire(self):
        import psutil
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                try:
                    record = json.loads(self.path.read_text(encoding='utf-8'))
                    existing = psutil.Process(record['pid'])
                    alive = existing.is_running() and existing.create_time() == record['created_at']
                except psutil.NoSuchProcess:
                    alive = False
                except (ValueError, KeyError, OSError, psutil.AccessDenied):
                    raise RuntimeError('Supervisor lock cannot be verified') from None
                if alive:
                    raise RuntimeError('A private-link supervisor is already running')
                self.path.unlink()
                continue
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump({'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'token': self.token}, stream)
            return
        raise RuntimeError('Cannot acquire private-link supervisor lock')

    def release(self):
        try:
            if json.loads(self.path.read_text(encoding='utf-8')).get('token') == self.token:
                self.path.unlink()
        except FileNotFoundError:
            pass


class Supervisor:
    def __init__(self, links, spawn=subprocess.Popen, clock=time.monotonic):
        self.spawn, self.clock = spawn, clock
        self.links = [dict(validate_link(link), child=None, failures=0, next_attempt=0, status='waiting') for link in links]
        if not self.links or len({link['name'] for link in self.links}) != len(self.links):
            raise ValueError('Supply distinct nonempty private links')

    def step(self):
        now = self.clock()
        for link in self.links:
            child = link['child']
            if child is not None and child.poll() is None:
                link['status'] = 'process_running'
                if now - link['started_at'] >= 60:
                    link['failures'] = 0
                continue
            if child is not None:
                link['child'] = None
                self.failed(link, now)
            if now < link['next_attempt']:
                continue
            try:
                link['child'] = self.spawn(link['argv'], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
                link['started_at'] = now
                link['status'] = 'process_running'
            except OSError:
                self.failed(link, now)

    @staticmethod
    def failed(link, now):
        link['failures'] += 1
        link['next_attempt'] = now + min(60, 2 ** min(link['failures'], 6))
        link['status'] = 'reconnecting'

    def receipt(self):
        # Never serialize argv, paths, destinations, stderr or credentials.
        return {'pid': os.getpid(), 'observed_at': time.time(),
                'links': [{'name': item['name'], 'status': item['status'],
                           'child_pid': item['child'].pid if item['child'] else None,
                           'failures': item['failures'],
                           'retry_in_seconds': max(0, round(item['next_attempt'] - self.clock()))}
                          for item in self.links],
                'connection_verified': False}

    def stop(self):
        for link in self.links:
            child = link['child']
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            link['child'] = None
            link['status'] = 'stopped'


def write_receipt(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    worker = Supervisor(config['links'])
    lock = ProcessLock(config['lock_file'])
    lock.acquire()
    stopping = False
    def stop_signal(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)
    try:
        while not stopping:
            worker.step()
            write_receipt(config['state_file'], worker.receipt())
            time.sleep(1)
    finally:
        try:
            worker.stop()
            write_receipt(config['state_file'], worker.receipt())
        finally:
            lock.release()


if __name__ == '__main__':
    main()
