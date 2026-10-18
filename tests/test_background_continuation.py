import asyncio
from types import SimpleNamespace

from backend.runtime.background_requests import BackgroundRequests


class ScriptedService:
    def __init__(self, states):
        self.states = states
        self.calls = 0
        self.current = {'id': 'job', 'status': 'queued', 'agent_session_id': 'agent'}
        self.agent = {'status': 'ready', 'pending': [], 'error': None}
        self.agents = SimpleNamespace(get=lambda ident: dict(self.agent))

    def get(self, ident):
        return dict(self.current)

    def update(self, ident, change, expected=None):
        if expected is not None and self.current['status'] not in expected:
            return None
        self.current.update(change)
        return dict(self.current)

    async def run(self, ident):
        self.calls += 1
        status, agent = self.states[min(self.calls - 1, len(self.states) - 1)]
        self.current['status'] = status
        self.agent['status'] = agent
        await asyncio.sleep(0)
        return dict(self.current)


def run_fixture(states):
    service = ScriptedService(states)
    runner = BackgroundRequests(lambda: service)
    asyncio.run(runner._run('job'))
    return service


def test_continues_same_ready_agent_after_a_two_turn_checkpoint():
    service = run_fixture([('waiting_review', 'ready'), ('completed', 'completed')])
    assert service.calls == 2
    assert service.current['status'] == 'completed'


def test_actual_review_failure_is_not_retried():
    service = run_fixture([('waiting_review', 'needs_review')])
    assert service.calls == 1
    assert service.current['status'] == 'waiting_review'


def test_pending_tool_or_approval_is_not_blindly_replayed():
    service = run_fixture([('waiting_review', 'waiting_tools')])
    assert service.calls == 1


def test_completed_request_is_never_repeated():
    assert run_fixture([('completed', 'completed')]).calls == 1


def test_cancelled_request_is_never_repeated():
    assert run_fixture([('cancelled', 'cancelled')]).calls == 1


def test_unending_ready_agent_has_a_small_fixed_chunk_budget():
    service = run_fixture([('waiting_review', 'ready')])
    assert 1 < service.calls <= 6
    assert service.current['status'] == 'waiting_review'


def test_ready_agent_with_pending_tools_does_not_continue():
    service = ScriptedService([('waiting_review', 'ready')])
    service.agent['pending'] = [{'task_id': 'waiting-for-approval'}]
    asyncio.run(BackgroundRequests(lambda: service)._run('job'))
    assert service.calls == 1


def test_request_error_is_not_a_productive_checkpoint():
    service = ScriptedService([('waiting_review', 'ready')])
    service.current['error'] = 'Retained failure'
    asyncio.run(BackgroundRequests(lambda: service)._run('job'))
    assert service.calls == 1


def test_agent_error_is_not_a_productive_checkpoint():
    service = ScriptedService([('waiting_review', 'ready')])
    service.agent['error'] = 'Retained failure'
    asyncio.run(BackgroundRequests(lambda: service)._run('job'))
    assert service.calls == 1


def test_different_agent_cannot_take_over_continuation():
    class ChangedAgent(ScriptedService):
        async def run(self, ident):
            await super().run(ident)
            if self.calls == 2:
                self.current['agent_session_id'] = 'different-agent'
            return dict(self.current)
    service = ChangedAgent([('waiting_review', 'ready')])
    asyncio.run(BackgroundRequests(lambda: service)._run('job'))
    assert service.calls == 2


def test_continuations_share_one_decreasing_deadline(monkeypatch):
    timeouts = []
    async def observe(awaitable, timeout):
        timeouts.append(timeout)
        await asyncio.sleep(.01)
        return await awaitable
    monkeypatch.setattr('backend.runtime.background_requests.asyncio.wait_for', observe)
    run_fixture([('waiting_review', 'ready'), ('completed', 'completed')])
    assert len(timeouts) == 2
    assert 0 < timeouts[1] < timeouts[0] <= 310
