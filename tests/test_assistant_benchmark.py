import asyncio
from backend.models.assistant_benchmark import CASES,SUITE,AssistantBenchmarks,prefer_measured
from backend.models.profiles import ModelProfiles
from backend.storage.db import Database


def test_benchmark_is_synthetic_and_revision_bound(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    db=Database(tmp_path/'bench.db')
    profile=ModelProfiles(db).save('small',{'provider':'ollama','endpoint':'http://127.0.0.1:11434','model':'small','variant':'standard'})
    seen=[]
    class Model:
        async def chat(self,ident,request):
            assert ident=='small' and request['_kingdom_profile_revision']==profile['updated_at']
            assert not request.get('tools')
            expected=CASES[len(seen)][1]
            seen.append(request['messages'])
            return {'choices':[{'message':{'content':expected},'finish_reason':'stop'}]}
    store=AssistantBenchmarks(db)
    result=asyncio.run(store.run('small',Model()))
    assert result['passed']==result['total']==3
    assert len(seen)==3 and all(len(x)==1 for x in seen)
    assert store.list()==[result]


def test_preference_requires_fresh_matching_successful_evidence():
    profiles=[{'id':'slow','updated_at':1},{'id':'fast','updated_at':2}]
    def record(profile,revision,latency,passed=3,observed=100):
        return {'profile':profile,'revision':revision,'suite':SUITE,'passed':passed,'total':3,'latency_ms':latency,'observed_at':observed}
    slow=record('slow',1,200)
    fast=record('fast',2,20)
    assert prefer_measured(profiles,[slow,fast],now=101)==[profiles[1]]
    assert prefer_measured(profiles,[slow,{**fast,'revision':3}],now=101)==[profiles[0]]
    assert prefer_measured(profiles,[slow,{**fast,'passed':2}],now=101)==[profiles[0]]
    assert prefer_measured(profiles,[slow,fast],now=9999999)==profiles
