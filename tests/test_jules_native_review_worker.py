"""Controller tests with constructor-only transport/executor injection.

No container, producer signature, deployed service or autonomous success is
claimed by these deliberately isolated lifecycle tests.
"""
import base64
import hashlib
import importlib.util
import json
import os
from types import SimpleNamespace
from contextlib import nullcontext
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('native_review_worker', Path(__file__).parents[1]/'scripts/jules-native-review-worker.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class Fixture:
    def __init__(self, root, *, failed=0, lost=None, cleanup=True):
        self.root, self.failed, self.lost, self.cleanup = root, failed, lost, cleanup
        self.calls, self.executions, self.recoveries = [], 0, []
        self.now = 1000.0
        self.binding = dict(job_id='jules-0123456789ab', project='kingdom', backlog_id='work-a',
            mission_id='mission-a', mission_version=1, step_id='review', source='sources/github/wests-cmd/kingdom',
            base_revision='a'*40, patch_sha256=hashlib.sha256(b'retained fixture patch').hexdigest(), contract_sha256='b'*64)
        self.job = dict(id=self.binding['job_id'], project='kingdom', source=self.binding['source'],
                        phase='awaiting_independent_review', candidate={'patch_sha256':self.binding['patch_sha256']})
        self.material = dict(binding=self.binding, patch='retained fixture patch', deadline_at=1600,
            delivery_protocol=module.DELIVERY_PROTOCOL,
            review_contract=dict(project='kingdom', source=self.binding['source'], base_revision='a'*40,
                contract_id='negative-fence-fixture', contract_sha256='b'*64, minimum_tests=7))
        state = root/'state'; state.mkdir()
        token = root/'owner-token'; token.write_text('fixture-owner-token-not-real-secret')
        seed = root/'seed'; seed.write_bytes(b'x'*32)
        mirror = root/'mirror'; mirror.mkdir()
        self.config = dict(api_port=8014, owner_token=str(token), signing_key=str(seed),
            repository_directory=str(mirror), image='sha256:'+'c'*64, state_directory=str(state),
            reviewer_id='fixture-reviewer', project='kingdom', source=self.binding['source'],
            contract_id='negative-fence-fixture', contract_sha256='b'*64,
            allowed_paths=['backend/integrations/jules.py'], deadline_at=1600, max_reviews=1)
        self.path = root/'config.json'; self.path.write_text(json.dumps(self.config))

    def transport(self, method, path, body=None):
        self.calls.append((method, path))
        if path.endswith('?project=kingdom'):
            return [self.job]
        if path.endswith('/review-material'):
            return self.material
        if path.endswith('/verify') or path.endswith('/failure'):
            if self.lost != 'unconsumed':
                proof = body['attestation']['payload']
                self.job['repair_verdict' if self.failed else 'evidence'] = proof
                self.job['phase'] = 'repair_queued' if self.failed else 'completed'
                self.job['accepted'] = not self.failed
            if self.lost:
                raise OSError('Simulated unknown POST response')
            return self.job
        return self.job

    def execute(self, path):
        self.executions += 1
        config = json.loads(path.read_text())
        assert 'owner_token' not in config and 'api_port' not in config
        assert config['binding'] == self.binding
        assert config['contract_id'] == self.config['contract_id']
        assert config['deadline_at'] == 1600
        run = path.parent/('external-'+'d'*32); run.mkdir()
        if self.cleanup:
            (run/'cleanup-complete').write_text('removed')
        proof = dict(format='kingdom.patch-test.v2', receipt_id='external-'+'d'*32,
            reviewer_id='fixture-reviewer', issued_at=self.now, expires_at=1500,
            binding=self.binding, execution=dict(test_count=7, failed_count=self.failed,
                exit_code=1 if self.failed else 0, network_isolated=True,
                read_only_source=True, verdict_origin='external_controller'))
        output = run/'attestation.json'
        output.write_text(json.dumps({'payload':proof, 'signature':base64.b64encode(b'x'*64).decode()}))
        return output

    def worker(self):
        return module.Worker(self.path, transport=self.transport, execute=self.execute,
            contract_digest=lambda:'b'*64, recover=self.recover, lock_factory=lambda:nullcontext(True),
            protect=lambda path, private=False:Path(path), clock=lambda:self.now)

    def recover(self, folder):
        self.recoveries.append(folder)


@pytest.mark.parametrize('failed', [0, 2])
def test_delivers_exact_fixed_contract_verdict_and_never_runs_twice(tmp_path, failed):
    f = Fixture(tmp_path, failed=failed)
    result = f.worker().tick()
    assert result['reviews'][0]['phase'] == 'delivered'
    assert result['reviews'][0]['route'] == ('failure' if failed else 'verify')
    f.worker().tick()
    assert f.executions == 1
    assert len([c for c in f.calls if c[0] == 'POST']) == 1


def test_installed_producer_hash_uses_the_selected_positive_contract(tmp_path, monkeypatch):
    f = Fixture(tmp_path)
    f.config['contract_id'] = 'backlog-advancement-v1'
    f.config['allowed_paths'] = ['backend/runtime/work_backlog.py']
    f.path.write_text(json.dumps(f.config))
    selected = []
    def digest(contract_id):
        selected.append(contract_id)
        return 'b'*64
    monkeypatch.setattr(module, 'producer', lambda: SimpleNamespace(contract_digest=digest))
    module.Worker(f.path, transport=f.transport, execute=f.execute,
        recover=f.recover, lock_factory=lambda: nullcontext(True),
        protect=lambda path, private=False: Path(path), clock=lambda: f.now)
    assert selected == ['backlog-advancement-v1']


@pytest.mark.parametrize('lost', ['consumed', 'unconsumed'])
def test_consumed_delivery_is_read_only_and_unconsumed_idempotent_delivery_is_bounded(tmp_path, lost):
    f = Fixture(tmp_path, lost=lost)
    assert f.worker().tick()['reviews'][0]['phase'] == 'delivery_unknown'
    result = f.worker().tick()
    assert result['reviews'][0]['phase'] == ('delivered' if lost=='consumed' else 'delivery_unknown')
    assert f.executions == 1 and len([c for c in f.calls if c[0]=='POST']) == (1 if lost=='consumed' else 2)
    if lost=='unconsumed':
        f.worker().tick()
        final=f.worker().tick()
        assert final['reviews'][0]['phase']=='delivery_held'
        assert len([c for c in f.calls if c[0]=='POST'])==3
        assert f.executions==1


def test_failure_receipt_can_reconcile_from_repair_history(tmp_path):
    f = Fixture(tmp_path, failed=1, lost='consumed')
    f.worker().tick()
    f.job['repair_history'] = [{'verdict':f.job.pop('repair_verdict')}]
    result = f.worker().tick()
    assert result['reviews'][0]['phase'] == 'delivered'
    assert f.executions == 1


def test_missing_cleanup_cannot_deliver_or_repeat_execution(tmp_path):
    f = Fixture(tmp_path, cleanup=False)
    assert f.worker().tick()['reviews'][0]['phase'] == 'executing'
    assert f.worker().tick()['reviews'][0]['phase'] == 'cleanup_held'
    assert f.executions == 1 and not any(c[0]=='POST' for c in f.calls)


@pytest.mark.parametrize('change', ['patch', 'binding', 'contract', 'source', 'deadline'])
def test_changed_untrusted_material_never_runs_or_claims_budget(tmp_path, change):
    f = Fixture(tmp_path)
    if change=='patch':f.material['patch']='different'
    if change=='binding':f.material['binding']={**f.binding,'job_id':'jules-ffffffffffff'}
    if change=='contract':f.material['review_contract']['contract_sha256']='e'*64
    if change=='source':f.job['source']='sources/github/unapproved/repository'
    if change=='deadline':f.material['deadline_at']=999
    assert f.worker().tick()['reviews']==[]
    assert f.executions==0


def test_expired_operator_window_does_no_network_and_cannot_renew(tmp_path):
    f = Fixture(tmp_path)
    worker = f.worker()
    f.now=1601
    assert worker.tick()['status']=='scope_expired'
    assert f.calls==[] and f.executions==0


def test_new_binding_does_not_evade_finite_budget(tmp_path):
    f = Fixture(tmp_path)
    f.worker().tick()
    f.job['phase']='awaiting_independent_review'
    f.binding['patch_sha256']=hashlib.sha256(b'new patch').hexdigest()
    f.material['patch']='new patch'
    assert f.worker().tick()['status']=='scope_budget_exhausted'
    assert f.executions==1


def test_config_cannot_select_test_seams_or_remote_endpoint(tmp_path):
    f = Fixture(tmp_path)
    for extra in [{'executor':'fake'}, {'transport':'fake'}, {'api_url':'https://outside.invalid'}]:
        f.path.write_text(json.dumps({**f.config,**extra}))
        with pytest.raises(ValueError):f.worker()


def test_prepost_crash_resumes_identical_owner_verdict_without_retesting(tmp_path):
    f=Fixture(tmp_path)
    worker=f.worker()

    class ProcessLost(BaseException):pass

    def interrupted(method,path,body=None):
        if method=='POST':raise ProcessLost()
        return f.transport(method,path,body)

    worker.transport=interrupted
    with pytest.raises(ProcessLost):worker.tick()
    retained=worker.records()[0]
    assert retained['phase']=='delivery_reserved' and retained['delivery_attempts']==1
    result=f.worker().tick()
    assert result['reviews'][0]['phase']=='delivered'
    assert result['reviews'][0]['delivery_attempts']==2
    assert f.executions==1 and len([c for c in f.calls if c[0]=='POST'])==1
    assert f.job['evidence']==retained['attestation']['payload']


def test_absent_idempotency_protocol_never_executes_or_retries_owner_delivery(tmp_path):
    f=Fixture(tmp_path)
    f.material.pop('delivery_protocol')
    assert f.worker().tick()['reviews']==[]
    assert f.executions==0 and not any(c[0]=='POST' for c in f.calls)


def test_first_job_execution_failure_blocks_second_job_until_cleanup(tmp_path):
    f=Fixture(tmp_path)
    f.config['max_reviews']=2;f.path.write_text(json.dumps(f.config))
    worker=f.worker()
    transport=f.transport
    second={**f.job,'id':'jules-ffffffffffff'}

    def two_jobs(method,path,body=None):
        if path.endswith('?project=kingdom'):
            return [f.job,second]
        assert 'jules-ffffffffffff' not in path, 'No second job before cleanup barrier'
        return transport(method,path,body)

    def failed(path):
        f.executions+=1
        raise OSError('Fixture producer failed with unknown cleanup')

    worker.transport=two_jobs;worker.execute=failed
    result=worker.tick()
    assert result['status']=='cleanup_required'
    assert len(result['reviews'])==1 and result['reviews'][0]['phase']=='executing'
    assert f.executions==1


def test_claim_without_a_launched_attempt_can_recover_once(tmp_path):
    f = Fixture(tmp_path)
    worker = f.worker()
    assert worker.claim(f.binding)['phase']=='executing'
    result=f.worker().tick()
    assert result['reviews'][0]['phase']=='delivered'
    assert f.executions==1


def test_completed_attestation_after_worker_crash_resumes_delivery_without_retest(tmp_path):
    f=Fixture(tmp_path)
    worker=f.worker()
    execute=worker.execute

    class ProcessLost(BaseException):pass

    def crashed(path):
        execute(path)
        raise ProcessLost()

    worker.execute=crashed
    with pytest.raises(ProcessLost):worker.tick()
    result=f.worker().tick()
    assert result['reviews'][0]['phase']=='delivered'
    assert f.executions==1 and len(f.recoveries)==1
    assert len([c for c in f.calls if c[0]=='POST'])==1


def test_verified_cleanup_allows_only_one_isolated_retry_and_counts_attempt_budget(tmp_path):
    f=Fixture(tmp_path)
    f.config['max_reviews']=3;f.path.write_text(json.dumps(f.config))

    class ProcessLost(BaseException):pass

    def crashed(path):
        f.executions+=1
        (path.parent/('external-'+'e'*32)).mkdir()
        raise ProcessLost()

    first=f.worker();first.execute=crashed
    with pytest.raises(ProcessLost):first.tick()
    second=f.worker();second.execute=crashed
    with pytest.raises(ProcessLost):second.tick()
    result=f.worker().tick()
    assert result['reviews'][0]['phase']=='execution_held'
    assert result['reviews'][0]['attempts']==2
    assert f.executions==2 and len(f.recoveries)==2
    assert not any(c[0]=='POST' for c in f.calls)


@pytest.mark.parametrize('budget', [1, 2])
def test_cleaned_interruption_retries_successfully_only_with_remaining_owner_budget(tmp_path, budget):
    f=Fixture(tmp_path)
    f.config['max_reviews']=budget;f.path.write_text(json.dumps(f.config))

    class ProcessLost(BaseException):pass

    def crashed(path):
        f.executions+=1
        raise ProcessLost()

    first=f.worker();first.execute=crashed
    with pytest.raises(ProcessLost):first.tick()
    result=f.worker().tick()
    state=result['reviews'][0]
    assert state['phase']==('delivered' if budget==2 else 'execution_held')
    assert state['attempts']==budget and f.executions==budget
    assert len(f.recoveries)==1


def test_failed_trusted_cleanup_prevents_retry_or_other_new_work(tmp_path):
    f=Fixture(tmp_path)
    f.config['max_reviews']=2;f.path.write_text(json.dumps(f.config))
    worker=f.worker();state=worker.claim(f.binding)
    assert worker.reserve_attempt(state)
    (worker.root/state['attempt_directory']).mkdir()

    def unavailable(folder):raise OSError('Fixture cleanup unavailable')

    worker.recover=unavailable
    assert worker.tick()['status']=='cleanup_required'
    assert f.executions==0 and f.calls==[]


def test_expired_scope_still_cleans_orphan_but_never_retries_or_delivers(tmp_path):
    f=Fixture(tmp_path)
    worker=f.worker();state=worker.claim(f.binding)
    assert worker.reserve_attempt(state)
    (worker.root/state['attempt_directory']).mkdir()
    f.now=1601
    result=worker.tick()
    assert result['status']=='scope_expired' and len(f.recoveries)==1
    assert f.executions==0 and f.calls==[]


@pytest.mark.skipif(os.name!='posix',reason='Actual POSIX flock requires POSIX')
def test_actual_flock_defers_second_worker_without_network_or_execution(tmp_path):
    f=Fixture(tmp_path)
    first=f.worker();second=f.worker()
    first.lock_factory=first._tick_lock;second.lock_factory=second._tick_lock
    with first._tick_lock() as acquired:
        assert acquired
        assert second.tick()['status']=='another_worker_active'
        assert f.calls==[] and f.executions==0
    assert second.tick()['reviews'][0]['phase']=='delivered'
