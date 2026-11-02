from backend.system.gap_backlog_bridge import register_missing_capabilities
import pytest

class Register:
    def list(self):
        return [dict(id='self-repair', status='partial', capability='Self repair',
                     missing_work='Bounded patch loop', test_evidence='test_repair.py', priority='P0'),
                dict(id='ready', status='verified', capability='Ready',
                     missing_work='', test_evidence='test_ready.py', priority='P1')]

class Backlog:
    def __init__(self): self.items = {}
    def register(self, **kw):
        key = kw['idempotency_key']
        self.items.setdefault(key, kw)
        return self.items[key]

def test_only_incomplete_are_registered_and_disabled():
    backlog = Backlog()
    items = register_missing_capabilities(Register(), backlog)
    assert len(items) == 1
    assert items[0]['enabled'] is False
    assert items[0]['task_type'] == 'repair'
    assert items[0]['priority'] == 90

def test_idempotency():
    backlog = Backlog()
    register_missing_capabilities(Register(), backlog)
    register_missing_capabilities(Register(), backlog)
    assert len(backlog.items) == 1

@pytest.mark.parametrize('project,limit', [('bad name', 10), ('kingdom', 0), ('kingdom', 101)])
def test_reject_invalid_arguments(project, limit):
    with pytest.raises(ValueError):
        register_missing_capabilities(Register(), Backlog(), project=project, limit=limit)
