"""Optional Kingdom JSON-lines contract for owner-configured harness wrappers.

Output is untrusted data. Proposals are never executed here.
"""
import json

TOOLS={"text.analyze@1.0.0","code.python.analyze@1.0.0"}


def decode(output):
    if not isinstance(output,str) or len(output)>65536:
        raise ValueError("Structured harness output exceeds its budget")
    events=[]
    answer=None
    proposals=[]
    for line in output.splitlines():
        if not line.strip():continue
        if len(events)>=64:raise ValueError("Too many harness events")
        event=json.loads(line)
        if not isinstance(event,dict):raise ValueError("Invalid harness event")
        kind=event.get("type")
        if kind=="progress" and set(event)=={"type","message"} and isinstance(event["message"],str) and 1<=len(event["message"])<=300:
            events.append({"type":"progress","message":event["message"]})
        elif kind=="answer" and set(event)=={"type","text"} and answer is None and isinstance(event["text"],str) and 1<=len(event["text"])<=16000:
            answer=event["text"]
            events.append({"type":"answer"})
        elif kind=="proposal" and set(event)=={"type","tool","text"} and isinstance(event["tool"],str) and event["tool"] in TOOLS and isinstance(event["text"],str) and 1<=len(event["text"])<=16000 and len(proposals)<5:
            proposals.append({"tool":event["tool"],"text":event["text"]})
            events.append({"type":"proposal","tool":event["tool"]})
        else:
            raise ValueError("Unsupported harness event; no proposed action was executed")
    if answer is None:raise ValueError("Missing structured harness answer")
    return {"answer":answer,"events":events,"proposals":proposals,"scope":"Untrusted harness output; proposals require fresh review"}


def proposal_plan(proposals):
    from backend.runtime.missions import MissionPlan
    # Revalidate stored proposal records, not client-supplied executable data.
    raw="\n".join(json.dumps({"type":"proposal",**item}) for item in proposals)+"\n"+json.dumps({"type":"answer","text":"proposal review"})
    checked=decode(raw)["proposals"]
    if not checked:raise ValueError("No supported proposal")
    return MissionPlan(title="Reviewed harness proposals",objective="Evaluate retained bounded analysis proposals",
        deliverables=["Independently verified analysis results"],steps=[
            {"id":f"check-{i}","title":f"Review proposed analysis {i}",
             "kind":"text_check" if item["tool"]=="text.analyze@1.0.0" else "python_check",
             "instructions":item["text"],"acceptance":"Controller verifies the exact retained analysis"}
            for i,item in enumerate(checked,1)])
