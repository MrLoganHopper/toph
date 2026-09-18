from uuid import uuid4
from dataclasses import replace
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings,Settings
from app.api import dependencies
from app.services.auth_service import Context
from app.services.primitives import mac
from app.errors import AppError

@pytest.fixture
def client():
    return TestClient(app,raise_server_exceptions=False)

def test_liveness_and_no_store(client):
    r=client.get('/healthz');assert r.status_code==200 and r.json()=={'ok':True}
    assert 'no-store' in r.headers['cache-control'] and r.headers['x-content-type-options']=='nosniff'

def test_unknown_api_never_html(client):
    r=client.get('/api/v1/not-a-route');assert r.status_code==404
    assert r.json()['error']['code']=='NOT_FOUND' and r.headers['content-type'].startswith('application/json')

@pytest.mark.parametrize('path',['/api/v1/me','/api/v1/farms/'+str(uuid4())+'/dashboard','/api/v1/farms/'+str(uuid4())+'/logs'])
def test_anonymous_denied(client,path):assert client.get(path).status_code==401

@pytest.mark.parametrize('origin',[None,'https://attacker.invalid','https://legit.vercel.app.attacker.invalid'])
def test_origin_required_for_mutation(client,origin):
    r=client.post('/api/v1/auth/login',json={'username':'valid.user','password':'not-a-real-password'},headers={'Origin':origin} if origin else {})
    assert r.status_code==403 and r.json()['error']['code']=='ORIGIN_INVALID'

def test_non_json_body_rejected(client):
    r=client.post('/api/v1/auth/login',content='username=anything',headers={'Origin':settings().app_origins[0],'Content-Type':'text/plain'})
    assert r.status_code==415

def test_metadata_size_limited(client):
    r=client.post('/api/v1/auth/login',content='x'*262145,headers={'Origin':settings().app_origins[0],'Content-Type':'application/json'})
    assert r.status_code==413

def test_malformed_payload_normalized(client):
    r=client.post('/api/v1/auth/login',content='{',headers={'Origin':settings().app_origins[0],'Content-Type':'application/json'})
    assert r.status_code==422 and 'input' not in r.json()['error']

def test_csrf_checked_before_any_authenticated_mutation(monkeypatch):
    ctx=Context(uuid4(),uuid4(),'hashed');monkeypatch.setattr(dependencies,'identity',lambda *args:ctx)
    cfg=Settings(_env_file=None,csrf_secret='a'*48,rate_limit_secret='b'*48);monkeypatch.setattr(dependencies,'settings',lambda:cfg)
    def request(csrf):return Request({'type':'http','method':'POST','path':'/api/v1/farms/test','headers':[(b'cookie',b'farm_session=session-token'),(b'x-csrf-token',csrf.encode())]})
    for csrf in ['', 'wrong','é']:
        with pytest.raises(AppError) as error:dependencies.current_user(request(csrf))
        assert error.value.status==403
    assert dependencies.current_user(request(mac(cfg.csrf_secret,'session-token')))==ctx

def test_exact_origin_configuration_rejects_wildcards():
    from pydantic import ValidationError
    for origin in ['https://*.vercel.app','https://example.com/path','https://user:password@example.com']:
        with pytest.raises(ValidationError):Settings(_env_file=None,app_origins=[origin])

def test_worker_cannot_use_admin_dependency():
    with pytest.raises(AppError) as exc:dependencies.require_farm_admin(Context(uuid4(),uuid4(),'hash',uuid4(),'worker'))
    assert exc.value.status==403
