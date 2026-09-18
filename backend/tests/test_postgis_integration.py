"""Real PostGIS tests. Destructive reset is restricted to an explicit *_test database.
No SQLite or in-memory database is substituted when PostGIS is unavailable.
"""
import os,secrets,json
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import text,select,func
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

pytestmark=[pytest.mark.integration,pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='TEST_DATABASE_URL not configured; actual PostGIS is required')]

@pytest.fixture(scope='module')
def database():
    from alembic import command
    from alembic.config import Config
    from app.config import settings
    from app.db.session import engine
    url=os.environ['TEST_DATABASE_URL']
    if not (make_url(url).database or '').endswith('_test') or os.environ.get('TOPH_TEST_RESET')!='YES':
        pytest.fail('Use a disposable database whose name ends in _test and set TOPH_TEST_RESET=YES.')
    patch=pytest.MonkeyPatch()
    for key,val in {'APP_ENV':'test','DATABASE_URL':url,'MIGRATION_DATABASE_URL':url,'POSTGIS_SCHEMA':'public','CSRF_SECRET':secrets.token_urlsafe(48),'RATE_LIMIT_SECRET':secrets.token_urlsafe(48),'COOKIE_SECURE':'false','APP_ORIGINS':'["http://testserver"]','DB_POOL_SIZE':'4','OPENAI_EXTRACT_MODEL':'fixture-extractor'}.items():patch.setenv(key,val)
    settings.cache_clear();engine.cache_clear()
    with engine(True).begin() as conn:conn.execute(text('DROP SCHEMA IF EXISTS farm_app CASCADE'))
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));command.upgrade(config,'head')
    yield
    engine().dispose();engine(True).dispose();engine.cache_clear();patch.undo();settings.cache_clear()

@pytest.fixture
def farm(database):
    from app.db.session import transaction
    from app.cli import seed
    from app.models.tables import metadata
    with transaction(operator=True) as conn:
        conn.execute(text('TRUNCATE '+', '.join('farm_app.'+t.name for t in metadata.sorted_tables)+' CASCADE'))
    password=secrets.token_urlsafe(24);seed(password)
    yield password

class Login:
    def __init__(self,password,username='demo.admin'):
        from app.main import app
        self.client=TestClient(app,raise_server_exceptions=False,headers={'Origin':'http://testserver'})
        response=self.client.post('/api/v1/auth/login',json={'username':username,'password':password});assert response.status_code==200,response.text
        self.auth=response.json();self.client.headers['X-CSRF-Token']=self.auth['csrf_token'];self.farm=self.auth['memberships'][0]['farm']['id'];self.base='/api/v1/farms/'+self.farm
    def get(self,path,**kwargs):return self.client.get(self.base+path,**kwargs)
    def post(self,path,**kwargs):return self.client.post(self.base+path,**kwargs)
    def patch(self,path,**kwargs):return self.client.patch(self.base+path,**kwargs)
    def delete(self,path,**kwargs):return self.client.delete(self.base+path,**kwargs)
    def bootstrap(self):
        response=self.get('/bootstrap');assert response.status_code==200,response.text;return response.json()

def test_migration_and_seed_populate_real_database(farm):
    from app.db.session import transaction
    from app.models.tables import metadata,farms,logs
    assert len(metadata.tables)==13
    with transaction() as conn:
        assert conn.execute(select(func.count()).select_from(farms)).scalar_one()==2
        assert conn.execute(select(func.count()).select_from(logs)).scalar_one()==48
        assert conn.execute(text('SELECT PostGIS_Version()')).scalar_one()

def test_login_cookie_logout_and_csrf(farm):
    user=Login(farm);assert user.get('/dashboard').status_code==200
    csrf=user.client.headers.pop('X-CSRF-Token');assert user.patch('',json={'name':'No write'}).status_code==403
    user.client.headers['X-CSRF-Token']=csrf;cookie=user.client.cookies.get('farm_session')
    assert user.client.post('/api/v1/auth/logout').status_code==204
    user.client.cookies.set('farm_session',cookie);assert user.client.get('/api/v1/me').status_code==401

def test_worker_and_farm_isolation(farm):
    admin=Login(farm);other=Login(farm,'cedar.admin');worker=Login(farm,'demo.worker1')
    assert admin.client.get(other.base+'/dashboard').status_code==404
    foreign=other.get('/logs').json()['items'][0]['id'];assert admin.get('/logs/'+foreign).status_code==404
    assert worker.get('/dashboard').status_code==403
    logs=worker.get('/logs?employee_id='+admin.auth['user']['id']).json()['items'];assert logs and all(v['employee']['id']==worker.auth['user']['id'] for v in logs)
    somebody=next(v for v in admin.get('/logs').json()['items'] if v['employee']['id']!=worker.auth['user']['id'])
    assert worker.get('/logs/'+somebody['id']).status_code==404
    assert worker.get('/logs/'+somebody['id']+'/audio-url').status_code==404

def test_activity_fertilizer_crud_parity(farm):
    admin=Login(farm);worker=Login(farm,'demo.worker1')
    for kind in ['activities','fertilizers']:
        assert worker.post('/'+kind,json={'name':'Forbidden'}).status_code==403
        create=admin.post('/'+kind,json={'name':'Unique catalog item'});assert create.status_code==201,create.text
        ident=create.json()['id'];assert admin.patch('/'+kind+'/'+ident,json={'name':'Renamed'}).status_code==200
        assert admin.post('/'+kind,json={'name':'renamed'}).status_code==409
        assert admin.delete('/'+kind+'/'+ident).status_code==204
        used=next(v for v in admin.get('/logs').json()['items'] if v['activity' if kind=='activities' else 'fertilizer'])
        ident=used['activity' if kind=='activities' else 'fertilizer']['id'];assert admin.delete('/'+kind+'/'+ident).status_code==409

def test_cross_farm_schedule_ids_and_composite_foreign_key(farm):
    admin=Login(farm);other=Login(farm,'cedar.admin');boot=admin.bootstrap();foreign=other.bootstrap()['fertilizers'][0]['id']
    value={'employee_id':boot['workers'][0]['id'],'start_at':'2026-09-17T10:00:00Z','end_at':'2026-09-17T11:00:00Z','fertilizer_id':foreign}
    assert admin.post('/shifts',json=value).status_code==404
    from app.db.session import transaction
    from app.models.tables import shifts
    with pytest.raises(IntegrityError):
        with transaction() as conn:conn.execute(shifts.insert().values(id=uuid4(),farm_id=UUID(admin.farm),employee_id=UUID(value['employee_id']),fertilizer_id=UUID(foreign),start_at=datetime(2026,9,17,10,tzinfo=timezone.utc),end_at=datetime(2026,9,17,11,tzinfo=timezone.utc)))

def test_temporary_password_and_session_rotation(farm):
    admin=Login(farm);created=admin.post('/members',json={'name':'New Worker','username':'new.worker','role':'worker'});assert created.status_code==201
    new=Login(created.json()['temporary_password'],'new.worker');assert new.get('/bootstrap').status_code==403
    response=new.client.post('/api/v1/auth/change-password',json={'current_password':created.json()['temporary_password'],'new_password':secrets.token_urlsafe(20)});assert response.status_code==200,response.text
    new.client.headers['X-CSRF-Token']=response.json()['csrf_token'];assert new.get('/bootstrap').status_code==200

def test_shared_or_admin_password_reset_denied(farm):
    admin=Login(farm);boot=admin.bootstrap();members=admin.get('/members').json()['items']
    second=next(m for m in members if m['username']=='demo.admin2');assert admin.post('/members/'+second['id']+'/reset-password').status_code==403
    worker=next(m for m in members if m['username']=='demo.worker1');other=Login(farm,'cedar.admin')
    from app.db.session import transaction
    from app.models.tables import memberships
    with transaction() as conn:conn.execute(memberships.insert().values(id=uuid4(),farm_id=UUID(other.farm),user_id=UUID(worker['user_id']),role='worker'))
    assert admin.post('/members/'+worker['id']+'/reset-password').status_code==403

def test_concurrent_last_admin_changes(farm):
    a=Login(farm);b=Login(farm,'demo.admin2');members=a.get('/members').json()['items'];a_id=next(m['id'] for m in members if m['username']=='demo.admin');b_id=next(m['id'] for m in members if m['username']=='demo.admin2')
    with ThreadPoolExecutor(2) as pool:
        jobs=[pool.submit(a.patch,'/members/'+b_id,json={'role':'worker'}),pool.submit(b.patch,'/members/'+a_id,json={'role':'worker'})]
        statuses=[j.result().status_code for j in jobs]
    assert statuses.count(200)==1 and all(code in (200,403,409) for code in statuses)
    from app.db.session import transaction
    with transaction() as conn:assert conn.execute(text("SELECT count(*) FROM farm_app.farm_memberships WHERE farm_id=:farm AND role='admin' AND is_enabled"),{'farm':UUID(a.farm)}).scalar_one()==1

def test_query_pagination_filters_and_tags_no_duplicates(farm):
    admin=Login(farm);all_rows=[];cursor=None
    while True:
        params={'limit':3,'range':'all'}
        if cursor:params['cursor']=cursor
        response=admin.get('/logs',params=params);assert response.status_code==200,response.text
        value=response.json();all_rows.extend(value['items']);cursor=value['next_cursor']
        if not cursor:break
    assert len(all_rows)==24 and len({v['id'] for v in all_rows})==24
    item=next(v for v in all_rows if v['fertilizer'])
    matching=admin.get('/logs',params={'activity_id':item['activity']['id'],'fertilizer_id':item['fertilizer']['id'],'field_id':item['field']['id']}).json()['items']
    assert matching and all(v['activity']==item['activity'] and v['fertilizer']==item['fertilizer'] and v['field']==item['field'] for v in matching)
    first=admin.get('/logs?limit=2').json();bad=admin.get('/logs',params={'cursor':first['next_cursor'],'activity_id':item['activity']['id']});assert bad.status_code==422
    tag=admin.post('/tags',json={'name':'Test label'}).json();path='/logs/'+item['id']+'/tags/'+tag['id']
    assert admin.client.put(admin.base+path).status_code==200
    assert admin.client.put(admin.base+path).status_code==200
    tagged=admin.get('/logs',params={'tag_id':tag['id']}).json();assert tagged['total_matching']==1

def test_equal_timestamp_cursor_stability(farm):
    admin=Login(farm)
    from app.db.session import transaction
    from app.models.tables import logs
    stamp=datetime.now(timezone.utc)
    with transaction() as conn:conn.execute(logs.update().where(logs.c.farm_id==UUID(admin.farm)).values(recorded_at=stamp))
    for direction in ['asc','desc']:
        ids=[];cursor=None
        while True:
            params={'limit':5,'direction':direction}
            if cursor:params['cursor']=cursor
            response=admin.get('/logs',params=params);assert response.status_code==200,response.text
            body=response.json();ids.extend(v['id'] for v in body['items']);cursor=body['next_cursor']
            if not cursor:break
        assert len(ids)==24 and len(set(ids))==24

def test_dashboard_metrics_and_cursor_compatible(farm):
    admin=Login(farm);response=admin.get('/dashboard?limit=2&range=all');assert response.status_code==200,response.text
    value=response.json();assert value['metrics']['confidence_sample_size']==24
    assert admin.get('/logs',params={'range':'all','limit':2,'cursor':value['logs']['next_cursor']}).status_code==200
    empty=admin.get('/dashboard?q=no-such-work-needle').json();assert empty['logs']['total_matching']==0 and empty['metrics']['average_extraction_confidence'] is None
    assert empty['metrics']['recordings_today']==value['metrics']['recordings_today']

def test_all_geojson_pages_and_invalid_topology(farm):
    admin=Login(farm);features=[];cursor=None;bbox=None
    while True:
        params={'limit':2}
        if cursor:params['cursor']=cursor
        response=admin.get('/fields/geojson',params=params);assert response.status_code==200,response.text
        body=response.json();features.extend(body['features']);bbox=body['farm_bbox'];cursor=body['next_cursor']
        if not cursor:break
    assert len(features)==5 and len(bbox)==4
    shape={'type':'Polygon','coordinates':[[[0,0],[1,1],[0,1],[1,0],[0,0]]]}
    assert admin.post('/fields',json={'name':'Crossed polygon','geometry':shape}).status_code==422

def recording_payload():return {'client_submission_id':str(uuid4()),'content_type':'audio/webm','size_bytes':1000,'duration_ms':5000,'recorded_at':datetime.now(timezone.utc).isoformat(),'interview_version':'interview-v1','transcript':[{'speaker':'worker','text':'I watered the field without fertilizer.','offset_ms':0}],'waveform_peaks':[.2,.4]}

def test_recording_idempotency_upload_and_extraction_retry(farm,monkeypatch):
    from app.providers import storage
    from app.services import ai_service
    from app.schemas.contracts import Extraction
    from app.errors import AppError
    worker=Login(farm,'demo.worker1');payload=recording_payload()
    first=worker.post('/recordings',json=payload);assert first.status_code==201,first.text;rid=first.json()['id']
    second=worker.post('/recordings',json=payload);assert second.status_code==200 and second.json()['id']==rid
    conflict=worker.post('/recordings',json={**payload,'size_bytes':900});assert conflict.status_code==409
    assert worker.post('/logs',json={'recording_id':rid,'shift_id':None}).status_code==422
    calls=[];monkeypatch.setattr(storage,'confirm_object',lambda row:calls.append(row['id']) or 'pinned-test-version')
    assert worker.post('/recordings/'+rid+'/complete').status_code==200
    assert worker.post('/recordings/'+rid+'/complete').status_code==200 and len(calls)==1
    async def fail(_):raise AppError(504,'EXTRACTION_TIMEOUT','Saved, retry.',True)
    monkeypatch.setattr(ai_service,'extract',fail)
    assert worker.post('/logs',json={'recording_id':rid,'shift_id':None}).status_code==504
    assert worker.get('/recordings/'+rid).json()['uploaded_at'] is not None
    async def okay(_):return Extraction(summary='Watered a field.',field_id=None,activity_id=None,fertilizer_id=None,answers={'details':None,'issues':None},extraction_confidence=None)
    monkeypatch.setattr(ai_service,'extract',okay)
    body={'recording_id':rid,'shift_id':None};done=worker.post('/logs',json=body);assert done.status_code==201,done.text
    retry=worker.post('/logs',json=body);assert retry.status_code==200 and retry.json()['id']==done.json()['id']
    assert worker.post('/logs',json={**body,'shift_id':str(uuid4())}).status_code==409

def test_invented_or_foreign_extracted_id_never_persisted(farm,monkeypatch):
    from app.providers import storage
    from app.services import ai_service
    from app.schemas.contracts import Extraction
    worker=Login(farm,'demo.worker1');other=Login(farm,'cedar.admin');foreign=other.bootstrap()['fertilizers'][0]['id'];rid=worker.post('/recordings',json=recording_payload()).json()['id']
    monkeypatch.setattr(storage,'confirm_object',lambda row:'v1');worker.post('/recordings/'+rid+'/complete')
    async def bad(_):return Extraction(summary='Made up.',field_id=None,activity_id=None,fertilizer_id=foreign,answers={'details':None,'issues':None},extraction_confidence=.9)
    monkeypatch.setattr(ai_service,'extract',bad)
    response=worker.post('/logs',json={'recording_id':rid,'shift_id':None});assert response.status_code==502
    assert worker.get('/recordings/'+rid).json()['linked_log_id'] is None

def test_concurrent_duplicate_reports_commit_once(farm,monkeypatch):
    import asyncio
    from app.providers import storage
    from app.services import ai_service
    from app.schemas.contracts import Extraction
    worker=Login(farm,'demo.worker1');retry=Login(farm,'demo.worker1');rid=worker.post('/recordings',json=recording_payload()).json()['id']
    monkeypatch.setattr(storage,'confirm_object',lambda row:'v1');assert worker.post('/recordings/'+rid+'/complete').status_code==200
    async def okay(_):
        await asyncio.sleep(.1)
        return Extraction(summary='Real database race fixture.',field_id=None,activity_id=None,fertilizer_id=None,answers={'details':None,'issues':None},extraction_confidence=None)
    monkeypatch.setattr(ai_service,'extract',okay);body={'recording_id':rid,'shift_id':None}
    with ThreadPoolExecutor(2) as pool:
        jobs=[pool.submit(client.post,'/logs',json=body) for client in (worker,retry)];results=[j.result() for j in jobs]
    assert sorted(v.status_code for v in results)==[200,201]
    assert len({v.json()['id'] for v in results})==1
