import pytest
from backend.learning.collector import LearningCollector
from backend.learning.models import SkillOutcome


@pytest.mark.parametrize('limit,expected',[(1,[5]),(3,[2,4,5]),(20,[0,2,4,5]),(0,[0,2,4,5]),(-1,[2,4,5]),(-5,[])])
def test_recent_outcomes_preserve_expiry_order_and_legacy_limits(monkeypatch,limit,expected):
    monkeypatch.setattr('backend.learning.collector.time.time',lambda:100)
    collector=LearningCollector()
    for index,expiry in enumerate([None,1,200,50,None,200]):
        collector.record_outcome(SkillOutcome(skill_id='test',skill_version='1',task_id=str(index),success=True,latency_sec=1,valid_until=expiry))
    assert [int(outcome.task_id) for outcome in collector.get_outcomes('test','1',limit=limit)]==expected
    assert [int(outcome.task_id) for outcome in collector.get_outcomes('test','1',limit=5,ignore_expired=False)]==[1,2,3,4,5]
    assert collector.get_outcomes('absent','1',limit=limit)==[]
