from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.runtime import request_api
from backend.security.http_auth import require_owner


def test_background_budget_is_owner_only_strict_and_explicit(monkeypatch):
    calls=[]
    def start(ident,**options):calls.append((ident,options));return {'active_request_ids':[ident]}
    monkeypatch.setattr(request_api,'background',SimpleNamespace(start=start))
    app=FastAPI();app.include_router(request_api.router)
    with TestClient(app) as client:
        assert client.post('/requests/job/background',json={},headers={'X-Kingdom-Request':'1'}).status_code==401
        assert calls==[]
        app.dependency_overrides[require_owner]=lambda:None
        assert client.post('/requests/job/background',json={'max_seconds':1200,'max_chunks':8}).status_code==202
        assert calls[-1]==('job',{'max_seconds':1200,'max_chunks':8})
        assert client.post('/requests/job/background').status_code==202
        assert calls[-1]==('job',{'max_seconds':310,'max_chunks':6})
        for body in ({'max_seconds':True},{'max_seconds':1801},{'max_chunks':13},{'renew':True}):
            assert client.post('/requests/job/background',json=body).status_code==422
        assert len(calls)==2
