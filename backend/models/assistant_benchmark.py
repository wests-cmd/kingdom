"""Owner-invoked synthetic text benchmark, not a general intelligence score."""
import asyncio
import json
import time
import math

CASES=(("Return exactly the number 17, with no other text.","17"),
       ("Return exactly the word maple in lowercase, no punctuation.","maple"),
       ("What is 8 plus 5? Return only the number.","13"))
SUITE="exact-text-v1"
MAX_AGE=7*86400


class AssistantBenchmarks:
    def __init__(self,database):
        self.db=database
        with self.db.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS assistant_model_benchmarks(
                profile TEXT PRIMARY KEY, evidence_json TEXT NOT NULL)""")
            conn.commit()

    def list(self):
        with self.db.get_connection() as conn:
            return [json.loads(r[0]) for r in conn.execute("SELECT evidence_json FROM assistant_model_benchmarks ORDER BY profile")]

    async def run(self,profile,models):
        from backend.models.profiles import ModelProfiles
        config=ModelProfiles(self.db).get(profile)
        if config.get('disabled'):
            raise ValueError("Profile disabled")
        revision=config['updated_at']
        timings=[]
        passed=0
        for prompt,expected in CASES:
            started=time.monotonic()
            result=await asyncio.wait_for(models.chat(profile,{'messages':[{'role':'user','content':prompt}],
                'max_tokens':32,'stream':False,'_kingdom_profile_revision':revision}),timeout=45)
            timings.append(round((time.monotonic()-started)*1000,2))
            choice=result['choices'][0]
            answer=choice['message'].get('content')
            if isinstance(answer,str) and answer.strip()==expected and choice.get('finish_reason')!='length':
                passed+=1
        evidence={'profile':profile,'revision':revision,'suite':SUITE,'passed':passed,'total':len(CASES),
            'latency_ms':round(sum(timings)/len(timings),2),'observed_at':time.time(),
            'scope':'Three exact synthetic text answers; no tool, reasoning, vision or general quality certification'}
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO assistant_model_benchmarks VALUES(?,?) ON CONFLICT(profile) DO UPDATE SET evidence_json=excluded.evidence_json",(profile,json.dumps(evidence)))
            conn.commit()
        return evidence


def prefer_measured(candidates, evidence, now=None):
    now=time.time() if now is None else now
    by_id={item.get('profile'):item for item in evidence}
    ranked=[]
    for profile in candidates:
        item=by_id.get(profile['id'],{})
        age=now-item.get('observed_at',0) if type(item.get('observed_at')) in (int,float) else -1
        latency=item.get('latency_ms')
        if (item.get('suite')==SUITE and item.get('revision')==profile.get('updated_at')
                and item.get('passed')==item.get('total')==len(CASES)
                and 0<=age<=MAX_AGE and type(latency) in (int,float) and math.isfinite(latency) and latency>=0):
            ranked.append((latency,profile['id'],profile))
    return [min(ranked,key=lambda row:row[:2])[2]] if ranked else candidates
