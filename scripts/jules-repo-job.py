"""Finite owner-installed Jules outbox. Remote completion is never acceptance.

Configuration and credentials must remain outside all agent workspaces. No
automatic POST replay, plan approval, PR export, merge or deployment is exposed.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import urllib.error

API = 'https://jules.googleapis.com/v1alpha/'
TERMINAL = {'awaiting_independent_review', 'failed', 'submission_unknown', 'expired_remote_may_continue'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def validate(config):
    if config.get('repository') != 'wests-cmd/kingdom' or config.get('source') != 'sources/github/wests-cmd/kingdom':
        raise ValueError('Only the owner-approved Kingdom repository is configured')
    if not re.fullmatch('[a-f0-9]{40}', config.get('revision', '')):
        raise ValueError('Pin the reviewed source revision')
    if not re.fullmatch('[A-Za-z0-9_./-]{1,150}', config.get('branch', '')) or '..' in config['branch']:
        raise ValueError('Invalid source branch')
    if not isinstance(config.get('prompt'), str) or not 1 <= len(config['prompt']) <= 12000:
        raise ValueError('Use a bounded repository-only assignment')
    if type(config.get('deadline_at')) not in (float, int) or not 0 < config['deadline_at'] <= time.time() + 3600:
        raise ValueError('Use at most one hour of local observation')


class Job:
    def __init__(self, config_file):
        path = Path(config_file).resolve()
        if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
            raise ValueError('Configuration must be protected by the job owner')
        self.root = path.parent
        self.lock = (self.root / 'job.lock').open('a+b')
        import fcntl
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.config = json.loads(path.read_text())
        validate(self.config)
        self.file = self.root / 'state.json'
        self.state = json.loads(self.file.read_text()) if self.file.exists() else {'phase':'queued'}
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))

    def save(self, **values):
        self.state.update(values, updated_at=time.time())
        tmp = self.file.with_suffix('.tmp')
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as out:
            json.dump(self.state, out, indent=2)
        tmp.replace(self.file)
        self.publish()

    def secret(self):
        from cryptography.fernet import Fernet
        c = self.config
        return Fernet(Path(c['vault_key']).read_bytes()).decrypt(Path(c['credential_file']).read_bytes()).decode()

    def request(self, path, body=None):
        if not re.fullmatch(r'sessions(?:/[A-Za-z0-9_-]+)?', path):
            raise ValueError('Only fixed Jules session operations are allowed')
        request = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(),
            headers={'X-Goog-Api-Key':self.secret(), 'Content-Type':'application/json'})
        with self.opener.open(request, timeout=30) as response:
            data = response.read(262145)
        if len(data) > 262144:
            raise ValueError('Bounded Jules response exceeded')
        return json.loads(data)

    def submit(self):
        if self.state['phase'] != 'queued':
            return
        # A crash or unknown HTTP outcome after this point must never replay POST.
        self.save(phase='submitting')
        c = self.config
        body = {'title':'Kingdom scoped engineering assignment',
            'prompt':c['prompt'] + '\nExpected source revision: ' + c['revision'] +
                '\nVerify the exact checkout first. No merge, deployment, credentials or owner-device access. Return source/test evidence for independent review.',
            'sourceContext':{'source':c['source'], 'githubRepoContext':{'startingBranch':c['branch']}},
            'requirePlanApproval':False, 'automationMode':'AUTOMATION_MODE_UNSPECIFIED'}
        try:
            reply = self.request('sessions', body)
            name = reply['name']
            if not isinstance(name, str) or not re.fullmatch('sessions/[A-Za-z0-9_-]+', name):
                raise ValueError('Unexpected Jules session identity')
            self.save(phase='watching', session=name, session_url='https://jules.google.com/session/' + name.split('/')[1])
        except Exception as error:
            self.save(phase='submission_unknown', reason='Submission outcome needs reconciliation; no automatic replay',
                      http_status=error.code if isinstance(error, urllib.error.HTTPError) else None)

    def poll(self):
        if self.state['phase'] != 'watching':
            return
        reply = self.request(self.state['session'])
        if reply.get('name') != self.state['session']:
            raise ValueError('Jules session identity changed')
        remote = reply.get('state', 'STATE_UNSPECIFIED')
        known = {'STATE_UNSPECIFIED','QUEUED','PLANNING','AWAITING_PLAN_APPROVAL','AWAITING_USER_FEEDBACK','IN_PROGRESS','PAUSED','FAILED','COMPLETED'}
        if remote not in known:
            raise ValueError('Unknown Jules lifecycle state')
        phase = 'awaiting_independent_review' if remote == 'COMPLETED' else 'failed' if remote == 'FAILED' else 'watching'
        self.save(phase=phase, remote_state=remote, accepted=False, automatic_merge=False, automatic_deployment=False)

    def publish(self):
        c = self.config
        if not c.get('owner_token_file'):
            return
        public = {k:v for k,v in self.state.items() if k in {'phase','session_url','remote_state','accepted','reason','http_status'}}
        try:
            token = Path(c['owner_token_file']).read_text().strip()
            def call(path, body=None):
                r = urllib.request.Request('http://127.0.0.1:8012' + path,
                    data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer ' + token,'X-Kingdom-Request':'1','Content-Type':'application/json'})
                with self.opener.open(r,timeout=10) as response:return json.loads(response.read(65536))
            ident = c['document_id']
            if not re.fullmatch('[a-z0-9-]{1,80}',ident):return
            try:revision = call('/vault/kingdom/documents/' + ident)['revision']
            except urllib.error.HTTPError as error:
                if error.code != 404:raise
                revision = 0
            call('/vault/kingdom/documents',{'id':ident,'body':json.dumps(public,indent=2),
                'expected_revision':revision,'allowed_roles':['planner','coder','security'],
                'provenance':{'source':'owner-installed Jules outbox','revision':c['revision']},'receipts':[]})
        except Exception:
            pass  # The protected local checkpoint remains authoritative.

    def run(self):
        if self.state['phase'] in TERMINAL:
            return
        if self.state['phase'] == 'submitting':
            self.save(phase='submission_unknown', reason='Interrupted POST; reconcile remote sessions before any new job')
            return
        if time.time() >= self.config['deadline_at']:
            self.save(phase='expired_remote_may_continue',reason='Local observation ended; remote work was not cancelled')
            return
        self.submit()
        failures = 0
        while self.state['phase'] == 'watching' and time.time() < self.config['deadline_at']:
            try:
                self.poll()
                failures = 0
            except Exception:
                failures += 1
                self.save(observation='Provider observation unavailable; saved session retained')
            if self.state['phase'] != 'watching':break
            time.sleep(min(300,60 * 2 ** min(failures,2),max(0,self.config['deadline_at']-time.time())))
        if self.state['phase'] == 'watching':
            self.save(phase='expired_remote_may_continue',reason='Local observation ended; remote work was not cancelled')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    Job(parser.parse_args().config).run()
