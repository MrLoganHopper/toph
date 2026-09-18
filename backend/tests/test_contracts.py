from datetime import datetime,timedelta,timezone
from uuid import uuid4
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas.contracts import CatalogInput,TagInput,MemberInput,FarmUpdate,LogFilters,ShiftInput,ShiftUpdate,Extraction,LogItem,RecordingInput,LogCreate
from app.services.primitives import range_bounds,username,password,validate_geometry,cursor_encode,cursor_decode,PASSWORDS,canonical,digest
from app.errors import AppError

@pytest.mark.parametrize('day,hours',[('2026-03-08T15:00:00+00:00',23),('2026-11-01T15:00:00+00:00',25),('2026-09-17T15:00:00+00:00',24)])
def test_farm_day_dst(day,hours):
    start,end=range_bounds('today','America/Los_Angeles',datetime.fromisoformat(day))
    assert (end-start).total_seconds()==hours*3600

@pytest.mark.parametrize('preset,hours',[('last_day',24),('last_week',168),('last_month',720)])
def test_rolling_dates(preset,hours):
    stamp=datetime(2026,9,17,tzinfo=timezone.utc);start,end=range_bounds(preset,'America/Los_Angeles',stamp)
    assert end==stamp and (end-start).total_seconds()==hours*3600

def test_week_starts_monday_and_december_rollover():
    a,b=range_bounds('this_week','America/Los_Angeles',datetime(2026,9,17,15,tzinfo=timezone.utc));assert a.weekday()==0 and (b-a).days==7
    a,b=range_bounds('this_month','UTC',datetime(2026,12,15,tzinfo=timezone.utc));assert a.day==1 and b==datetime(2027,1,1,tzinfo=timezone.utc)

@pytest.mark.parametrize('bad',['a','UPPER SPACE','/etc/passwd','a'*41,''])
def test_bad_username(bad):
    with pytest.raises(ValueError):username(bad)

def test_username_and_password_hash():
    assert username(' Alex.Wang ')=='alex.wang'
    secret='  Twelve letters and spaces  ';assert password(secret)==secret
    hashed=PASSWORDS.hash(secret);assert hashed.startswith('$argon2id$') and PASSWORDS.verify(hashed,secret)

def test_signed_cursor_rejects_changes_and_cross_farm():
    value=cursor_encode(['2026-01-01T00:00:00Z',str(uuid4())],{'farm':'a','fertilizer':'b'},'secret')
    assert len(cursor_decode(value,{'farm':'a','fertilizer':'b'},'secret'))==2
    for candidate,fp in [(value+'x',{'farm':'a','fertilizer':'b'}),(value,{'farm':'other'}),('broken',{})]:
        with pytest.raises(AppError) as e:cursor_decode(candidate,fp,'secret')
        assert e.value.status==422

def test_canonical_hash_is_order_independent():
    assert digest(canonical({'activity':'x','fertilizer':'y'}))==digest(canonical({'fertilizer':'y','activity':'x'}))

GOOD={'type':'Polygon','coordinates':[[[-93,41],[-92,41],[-92,42],[-93,41]]]}
def test_geojson_normalizes_polygon():
    normalized=validate_geometry(GOOD);assert normalized['type']=='MultiPolygon' and len(normalized['coordinates'])==1

@pytest.mark.parametrize('shape',[
    {'type':'Point','coordinates':[-93,41]}, {'type':'Polygon','coordinates':[]},
    {'type':'Polygon','coordinates':[[[-93,41],[-92,41],[-92,42],[-92,41]]]},
    {'type':'Polygon','coordinates':[[[-93,191],[-92,191],[-92,192],[-93,191]]]},
    {'type':'Polygon','coordinates':[[[float('nan'),41],[-92,41],[-92,42],[float('nan'),41]]]},
    {'type':'Polygon','coordinates':[[[-93,41,0],[-92,41,0],[-92,42,0],[-93,41,0]]]},
])
def test_invalid_geojson(shape):
    with pytest.raises(ValueError):validate_geometry(shape)

def test_geojson_position_limit():
    with pytest.raises(ValueError):validate_geometry({'type':'Polygon','coordinates':[[[-93,41]]*1001]})

@pytest.mark.parametrize('model',[CatalogInput,TagInput,MemberInput,FarmUpdate])
def test_blank_names_rejected(model):
    payload={'name':'  '}
    if model is MemberInput:payload['username']='worker'
    with pytest.raises(ValidationError):model(**payload)

@pytest.mark.parametrize('payload',[{'range':'today','from':'2026-01-01T00:00:00Z','to':'2026-01-02T00:00:00Z'},{'from':'2026-01-01T00:00:00Z'},{'from':'2026-01-01T00:00:00','to':'2026-01-02T00:00:00'}, {'direction':'random'},{'limit':101},{'q':'x'*201}])
def test_filters_invalid(payload):
    with pytest.raises(ValidationError):LogFilters.model_validate(payload)

def test_fertilizer_shapes_parallel():
    identifier=str(uuid4());parsed=LogFilters(activity_id=identifier,fertilizer_id=identifier)
    assert parsed.activity_id==parsed.fertilizer_id
    for model in [ShiftInput,ShiftUpdate,Extraction,LogItem]:
        assert ('activity_id' in model.model_fields and 'fertilizer_id' in model.model_fields) or ('activity' in model.model_fields and 'fertilizer' in model.model_fields)

def recording(**changes):
    value=dict(client_submission_id=uuid4(),content_type='audio/webm',size_bytes=1000,duration_ms=5000,recorded_at=datetime.now(timezone.utc),interview_version='interview-v1',transcript=[{'speaker':'worker','text':'Watered Field A','offset_ms':0}],waveform_peaks=[.1,.8])
    value.update(changes);return value

@pytest.mark.parametrize('changes',[{'size_bytes':0},{'size_bytes':26214401},{'duration_ms':600001},{'content_type':'text/html'},{'transcript':[]},{'transcript':[{'speaker':'assistant','text':'hello','offset_ms':0}]},{'transcript':[{'speaker':'worker','text':'hello','offset_ms':6000}]},{'waveform_peaks':[float('nan')]},{'waveform_peaks':[.2]*513},{'employee_id':str(uuid4())},{'object_key':'other/farm'}])
def test_recording_invalid(changes):
    with pytest.raises(ValidationError):RecordingInput(**recording(**changes))

def test_recording_has_no_inferred_worker_or_storage_key():
    value=RecordingInput(**recording());assert value.size_bytes==1000
    assert not {'employee_id','farm_id','object_key'}&RecordingInput.model_fields.keys()

def test_log_requires_explicit_nullable_shift():
    with pytest.raises(ValidationError):LogCreate(recording_id=uuid4())
    assert LogCreate(recording_id=uuid4(),shift_id=None).shift_id is None

def test_extraction_is_strict_nullable_and_required():
    value={'summary':'Worker did not identify a field.','field_id':None,'activity_id':None,'fertilizer_id':None,'answers':{'details':None,'issues':None},'extraction_confidence':None}
    assert Extraction(**value).fertilizer_id is None
    with pytest.raises(ValidationError):Extraction(**{**value,'employee_id':str(uuid4())})
    schema=Extraction.model_json_schema();assert schema['additionalProperties'] is False
    assert set(schema['required'])==set(value)
    assert schema['$defs']['Answers']['additionalProperties'] is False

def test_all_api_contract_routes_in_actual_openapi():
    from app.main import app
    spec=app.openapi();contract=json.loads((Path(__file__).resolve().parents[2]/'docs/api_contract.json').read_text())
    assert len(contract['endpoints'])==44
    for endpoint in contract['endpoints']:assert endpoint['method'].lower() in spec['paths'].get(endpoint['path'],{})
    for catalog,single in [('activities','activity_id'),('fertilizers','fertilizer_id')]:
        operation=spec['paths']['/api/v1/farms/{farm_id}/'+catalog+'/{'+single+'}']['patch']
        assert any(p['name']==single and p['in']=='path' for p in operation['parameters'])
    for model in ('User','Member','AuthResult','LogDetail','RecordingView'):
        assert not {'password_hash','token_hash','payload_hash','object_key','object_version_id'}&spec['components']['schemas'][model]['properties'].keys()



def test_project_and_requirements_dependencies_match():
    from pathlib import Path
    import tomllib
    root=Path(__file__).resolve().parents[1]
    project=tomllib.loads((root/'pyproject.toml').read_text())
    required=[line for line in (root/'requirements.txt').read_text().splitlines() if line and not line.startswith('#')]
    assert project['project']['dependencies']==required
