import asyncio,base64,json
from types import SimpleNamespace
import boto3,httpx,pytest
from botocore.stub import Stubber
from app.config import Settings
from app.errors import AppError
from app.providers import storage,ai

@pytest.fixture
def s3(monkeypatch):
    cfg=Settings(_env_file=None,s3_bucket='toph-test-fixtures',aws_region='us-west-2');monkeypatch.setattr(storage,'settings',lambda:cfg)
    client=boto3.client('s3',region_name='us-west-2',aws_access_key_id='TESTONLY',aws_secret_access_key='TESTONLY')
    monkeypatch.setattr(storage,'client',lambda:client);return client

def recording():return dict(object_key='farms/example/recordings/test.webm',content_type='audio/webm',size_bytes=1000,duration_ms=5000,object_version_id='pinned-version')

def test_s3_post_policy_constrains_key_type_and_size(s3):
    value=storage.upload_form(recording());policy=json.loads(base64.b64decode(value['fields']['policy']))
    assert ['content-length-range',1000,1000] in policy['conditions']
    assert {'Content-Type':'audio/webm'} in policy['conditions']
    assert {'key':recording()['object_key']} in policy['conditions']
    assert 'acl' not in value['fields'] and value['method']=='POST'

def test_s3_confirmation_uses_version(s3):
    with Stubber(s3) as stub:
        stub.add_response('head_object',{'ContentLength':1000,'ContentType':'audio/webm','VersionId':'v1'},{'Bucket':'toph-test-fixtures','Key':recording()['object_key']})
        assert storage.confirm_object(recording())=='v1';stub.assert_no_pending_responses()

@pytest.mark.parametrize('head,code',[({'ContentLength':999,'ContentType':'audio/webm','VersionId':'v1'},'AUDIO_MISMATCH'),({'ContentLength':1000,'ContentType':'audio/mp4','VersionId':'v1'},'AUDIO_MISMATCH'),({'ContentLength':1000,'ContentType':'audio/webm','VersionId':'null'},'BUCKET_VERSIONING_REQUIRED')])
def test_s3_invalid_objects_rejected(s3,head,code):
    with Stubber(s3) as stub:
        stub.add_response('head_object',head,{'Bucket':'toph-test-fixtures','Key':recording()['object_key']})
        with pytest.raises(AppError) as error:storage.confirm_object(recording())
        assert error.value.code==code

def test_playback_is_version_pinned_and_temporary(s3):
    value=storage.playback_url(recording())
    from urllib.parse import urlsplit,parse_qs
    query=parse_qs(urlsplit(value['url']).query)
    assert query['versionId']==['pinned-version']
    assert 'Expires' in query or 'X-Amz-Expires' in query

def test_fixture_audio_is_not_faked(s3):
    with pytest.raises(AppError) as error:storage.playback_url({**recording(),'object_key':'dev-fixture/test'})
    assert error.value.code=='FIXTURE_AUDIO_UNAVAILABLE'

GOOD={'summary':'Watered a field.','field_id':None,'activity_id':None,'fertilizer_id':None,'answers':{'details':None,'issues':None},'extraction_confidence':.8}
@pytest.fixture
def ai_config(monkeypatch):
    cfg=Settings(_env_file=None,openai_api_key='test-provider-key',openai_extract_model='test-extractor',openai_realtime_model='test-realtime',openai_transcription_model='test-asr')
    monkeypatch.setattr(ai,'settings',lambda:cfg);return cfg

def inject_async(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(ai.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

def test_extraction_request_is_strict_and_secrets_stay_in_headers(monkeypatch,ai_config):
    seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert body['store'] is False and body['text']['format']['strict'] is True
        assert 'test-provider-key' not in request.content.decode()
        assert body['text']['format']['schema']['additionalProperties'] is False
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(GOOD)}]}]})
    inject_async(monkeypatch,handler);value=asyncio.run(ai.extract({'transcript':[]}));assert value.summary==GOOD['summary'] and len(seen)==1

@pytest.mark.parametrize('reply',[{'status':'incomplete','output':[]},{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'not json'}]}]},{'status':'completed','output':[{'type':'message','content':[{'type':'refusal','refusal':'Cannot comply'}]}]}])
def test_failed_extraction_is_visible(monkeypatch,ai_config,reply):
    inject_async(monkeypatch,lambda _:httpx.Response(200,json=reply))
    with pytest.raises(AppError) as error:asyncio.run(ai.extract({}))
    assert error.value.status==502 and error.value.retryable

def test_extraction_timeout_has_no_automatic_retry(monkeypatch,ai_config):
    attempts=[]
    def handler(request):attempts.append(1);raise httpx.ReadTimeout('simulated timeout',request=request)
    inject_async(monkeypatch,handler)
    with pytest.raises(AppError) as error:asyncio.run(ai.extract({}))
    assert error.value.status==504 and len(attempts)==1

def test_realtime_mints_only_ephemeral_response(monkeypatch,ai_config):
    original=httpx.Client
    def handler(request):
        body=json.loads(request.content);assert body['session']['audio']['input']['transcription']['model']=='test-asr'
        assert 'fertilizer' in body['session']['instructions'].lower()
        return httpx.Response(200,json={'value':'ephemeral-test-only','expires_at':1900000000})
    monkeypatch.setattr(ai.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    value=ai.mint({'farm':{'name':'Fictional','timezone':'UTC'},'fields':[],'activities':[],'fertilizers':[]})
    assert value['client_secret']=='ephemeral-test-only' and 'test-provider-key' not in json.dumps(value)

def test_missing_provider_configuration_fails_explicitly(monkeypatch):
    monkeypatch.setattr(ai,'settings',lambda:Settings(_env_file=None))
    with pytest.raises(AppError) as error:asyncio.run(ai.extract({}))
    assert error.value.status==503
