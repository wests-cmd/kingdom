#!/usr/bin/env python3
"""Run real inference against an existing local Ollama server, one tier at a time.

No downloads, cloud credentials, repository edits, model-generated actions or paid API calls.
Run on a dedicated idle model host, using the exact clean reviewed source checkout.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.models.model_matrix import CASES, SUITE, TIERS, grade, model_identity, verify_reports
from scripts.validate_version import get_authoritative_version


def source_revision():
    commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    if subprocess.check_output(["git","-C",str(ROOT),"status","--porcelain","--untracked-files=no"],text=True).strip():
        raise ValueError("Use a clean tracked source checkout; evidence must bind to the tested revision")
    return commit,get_authoritative_version(str(ROOT))


async def run(args, report):
    import httpx
    import psutil
    endpoint=f"http://127.0.0.1:{args.port}"
    async with httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=False) as client:
        tags=await client.get(endpoint+"/api/tags")
        tags.raise_for_status()
        # Reject absent tags before asking the server to resolve model metadata.
        inventory=tags.json()
        if not any(item.get("name")==args.model or item.get("model")==args.model for item in inventory.get("models",[])):
            raise ValueError("Exact installed model tag required")
        show=await client.post(endpoint+"/api/show",json={"model":args.model})
        show.raise_for_status()
        report["identity"]=model_identity(tags.json(),show.json(),args.model,args.tier)
    # Conservative CPU-friendly preflight, not a VRAM estimator. Refuse a
    # host without room for the installed model file plus modest headroom.
    report["host"]={"os":platform.system(),"architecture":platform.machine(),
                    "logical_cpu":os.cpu_count(),"ram_bytes":psutil.virtual_memory().total,
                    "available_ram_before_bytes":psutil.virtual_memory().available}
    minimum=max(1024**3,report["identity"]["model_bytes"]+512*1024**2)
    report["host"]["minimum_available_ram_bytes"]=minimum
    if report["host"]["available_ram_before_bytes"]<minimum:
        raise ValueError("Insufficient available RAM for this conservative lab preflight")
    report["settings"]={"context_tokens":2048,"output_tokens":128,"timeout_seconds":args.timeout,
                        "parallel":1,"temperature":0}
    # Do not import the default database or credential vault until isolated.
    previous=Path.cwd()
    with tempfile.TemporaryDirectory(prefix="kingdom-model-lab-") as directory:
        try:
            os.chdir(directory)
            import backend.storage.db as storage
            from backend.models.profiles import ModelProfiles
            from backend.models.service import ModelService
            profile=ModelProfiles(storage.db).save("lab",{"provider":"ollama","endpoint":endpoint,
                "model":args.model,"variant":"standard","hosting":"local","auto_select":False,
                "max_parallel":1,"num_ctx":2048,"max_output_tokens":128,
                "context_characters":16000,"timeout_seconds":args.timeout})
            service=ModelService()
            for case_id,messages,expected in CASES:
                start=time.monotonic()
                case={"id":case_id,"passed":False,"completion_tokens":0}
                try:
                    request={"messages":messages,"temperature":0,"max_tokens":128,"tool_choice":"none",
                             "_kingdom_profile_revision":profile["updated_at"]}
                    if case_id=="json":request["response_format"]={"type":"json_object"}
                    result=await asyncio.wait_for(service.chat("lab",request),timeout=args.timeout+5)
                    tokens=(result.get("usage") or {}).get("completion_tokens")
                    case["completion_tokens"]=tokens if type(tokens) is int else 0
                    case["passed"]=grade(case_id,expected,result,"lab") and case["completion_tokens"]>0
                except Exception as error:
                    case["error_type"]=type(error).__name__
                case["elapsed_ms"]=round((time.monotonic()-start)*1000,2)
                case["available_ram_after_bytes"]=psutil.virtual_memory().available
                report["cases"].append(case)
            # A changed model tag invalidates evidence. Do not infer after drift.
            async with httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=False) as client:
                tags=await client.get(endpoint+"/api/tags");tags.raise_for_status()
                show=await client.post(endpoint+"/api/show",json={"model":args.model});show.raise_for_status()
                if model_identity(tags.json(),show.json(),args.model,args.tier)!=report["identity"]:
                    raise ValueError("Model identity changed during the suite")
            report["status"]="passed" if all(c["passed"] for c in report["cases"]) and len(report["cases"])==len(CASES) else "failed"
        finally:
            os.chdir(previous)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    live=sub.add_parser("run")
    live.add_argument("--tier",choices=TIERS,required=True)
    live.add_argument("--model",required=True,help="Exact installed tag, including :tag")
    live.add_argument("--port",type=int,default=11434)
    live.add_argument("--timeout",type=int,default=180)
    live.add_argument("--output",type=Path,required=True)
    live.add_argument("--confirm-idle-local-lab",action="store_true",required=True,
                      help="Confirm this local server is owner-controlled and adequately resourced")
    check=sub.add_parser("verify")
    check.add_argument("reports",type=Path,nargs=3)
    args=parser.parse_args()
    commit,version=source_revision()
    if args.command=="verify":
        print(json.dumps(verify_reports([json.loads(p.read_text(encoding="utf-8")) for p in args.reports],commit,version),indent=2))
        return 0
    if not 1<=args.port<=65535 or not 30<=args.timeout<=600 or not args.model or len(args.model)>200:
        parser.error("Invalid port, timeout or model tag")
    path=args.output.resolve()
    if path.is_relative_to(ROOT) or path.exists():
        parser.error("Choose a new report path outside the source checkout")
    # Do not allow the local model HTTP request to use a configured proxy.
    os.environ["NO_PROXY"]="127.0.0.1,localhost,::1"
    os.environ["no_proxy"]=os.environ["NO_PROXY"]
    report={"suite":SUITE,"version":version,"source_commit":commit,"tier":args.tier,
            "mode":"live_local_ollama","status":"not_tested","cases":[],
            "observed_at":datetime.now(timezone.utc).isoformat()}
    try:
        asyncio.run(run(args,report))
        if source_revision()!=(commit,version):
            raise ValueError("Source revision changed during the lab")
    except Exception as error:
        report["status"]="failed" if report["cases"] else "not_tested"
        report["error_type"]=type(error).__name__
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as output:
        json.dump(report,output,indent=2,allow_nan=False)
        output.write("\n")
    print(f"{args.tier}: {report['status']} ({sum(c['passed'] for c in report['cases'])}/{len(CASES)})")
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
