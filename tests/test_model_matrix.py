"""Offline contract tests only; never represented as live inference evidence."""
import pytest
from backend.models.model_matrix import CASES, CASE_IDS, SUITE, grade, model_identity, tier_of, verify_reports


@pytest.mark.parametrize("count,tier",[(1,"small"),(3_000_000_000,"small"),(3_000_000_001,"medium"),(13_000_000_000,"medium"),(13_000_000_001,"large")])
def test_measured_parameter_boundaries(count,tier):
    assert tier_of(count)==tier


@pytest.mark.parametrize("bad",[None,True,0,-1,3.0,"7B"])
def test_unknown_parameter_count_is_not_guessed(bad):
    with pytest.raises(ValueError):tier_of(bad)


@pytest.mark.parametrize("tier,count", [("small",1_500_000_000),("medium",7_000_000_000),("large",32_000_000_000)])
def test_local_metadata_requires_correct_tier_and_digest(tier,count):
    tags={"models":[{"name":"fixture:local","size":100,"digest":"a"*64}]}
    show={"model_info":{"general.parameter_count":count}}
    assert model_identity(tags,show,"fixture:local",tier)["parameters"]==count
    with pytest.raises(ValueError):model_identity(tags,show,"missing:local",tier)
    with pytest.raises(ValueError):model_identity(tags,{**show,"remote_host":"example.invalid"},"fixture:local",tier)
    with pytest.raises(ValueError):model_identity(tags,show,"fixture:local",next(t for t in ("small","medium","large") if t!=tier))


@pytest.mark.parametrize("case_id,messages,expected",CASES)
def test_grading_never_executes_generated_text(case_id,messages,expected):
    import json
    answer=json.dumps(expected) if isinstance(expected,dict) else expected
    response={"kingdom_profile":"lab","choices":[{"finish_reason":"stop","message":{"content":answer}}]}
    assert grade(case_id,expected,response,"lab")
    assert not grade(case_id,expected,{**response,"kingdom_profile":"wrong"},"lab")
    response["choices"][0]["message"]["tool_calls"]=[{"function":{"name":"process.run"}}]
    assert not grade(case_id,expected,response,"lab")


def test_release_records_reject_missing_mock_failed_and_stale_tiers():
    from copy import deepcopy
    rows=[{"suite":SUITE,"source_commit":"a"*40,"version":"1.3.0","mode":"live_local_ollama","tier":tier,
           "status":"passed","identity":{"parameters":count,"digest":digest*64,"model_bytes":100},
           "cases":[{"id":name,"passed":True,"elapsed_ms":1,"completion_tokens":1} for name in CASE_IDS]}
           for tier,count,digest in [("small",1_000_000_000,"a"),("medium",7_000_000_000,"b"),("large",32_000_000_000,"c")]]
    assert verify_reports(rows,"a"*40,"1.3.0")["status"]=="records_passed"
    with pytest.raises(ValueError):verify_reports(rows[:2],"a"*40,"1.3.0")
    for field,value in [("mode","simulated"),("source_commit","b"*40),("status","not_tested"),("version","1.2.11")]:
        changed=deepcopy(rows);changed[0][field]=value
        with pytest.raises(ValueError):verify_reports(changed,"a"*40,"1.3.0")
    changed=deepcopy(rows);changed[2]["cases"][0]["passed"]=False
    with pytest.raises(ValueError):verify_reports(changed,"a"*40,"1.3.0")
    changed=deepcopy(rows);changed[2]["identity"]["digest"]=changed[0]["identity"]["digest"]
    with pytest.raises(ValueError):verify_reports(changed,"a"*40,"1.3.0")


def test_duplicate_json_keys_are_not_accepted():
    payload={"kingdom_profile":"lab","choices":[{"finish_reason":"stop","message":{"content":'{"status":"wrong","status":"ready","count":3}'}}]}
    assert not grade("json",{"status":"ready","count":3},payload,"lab")
