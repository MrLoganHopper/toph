"""Real S3 adapter. Test doubles are injected only in tests, never on key failure."""
from functools import lru_cache
from datetime import timedelta
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError,BotoCoreError
from app.config import settings
from app.errors import AppError,missing_config
from app.services.primitives import now

@lru_cache
def client():
    cfg=settings();missing_config(S3_BUCKET=cfg.s3_bucket,AWS_REGION=cfg.aws_region)
    kwargs={'region_name':cfg.aws_region,'config':Config(signature_version='s3v4',connect_timeout=5,read_timeout=10,retries={'max_attempts':1,'mode':'standard'})}
    if cfg.aws_access_key_id or cfg.aws_secret_access_key:
        missing_config(AWS_ACCESS_KEY_ID=cfg.aws_access_key_id,AWS_SECRET_ACCESS_KEY=cfg.aws_secret_access_key)
        kwargs.update(aws_access_key_id=cfg.aws_access_key_id,aws_secret_access_key=cfg.aws_secret_access_key)
    return boto3.client('s3',**kwargs)

def upload_form(recording):
    try:
        result=client().generate_presigned_post(Bucket=settings().s3_bucket,Key=recording['object_key'],
            Fields={'Content-Type':recording['content_type']},Conditions=[{'Content-Type':recording['content_type']},['content-length-range',recording['size_bytes'],recording['size_bytes']]],ExpiresIn=600)
        return {**result,'method':'POST','expires_at':now()+timedelta(seconds=600),'max_size_bytes':recording['size_bytes']}
    except (ClientError,BotoCoreError) as exc:raise AppError(502,'STORAGE_UNAVAILABLE','Could not authorize the upload. Your local draft is preserved.',True) from exc

def confirm_object(recording):
    try:head=client().head_object(Bucket=settings().s3_bucket,Key=recording['object_key'])
    except (ClientError,BotoCoreError) as exc:raise AppError(502,'UPLOAD_NOT_VERIFIED','The upload could not be verified. Check storage permissions or retry uploading.',True) from exc
    if head.get('ContentLength')!=recording['size_bytes'] or head.get('ContentType','').split(';')[0].strip()!=recording['content_type']:
        raise AppError(422,'AUDIO_MISMATCH','The uploaded audio size or type does not match the saved recording metadata.')
    version=head.get('VersionId')
    if not version or version=='null':raise AppError(503,'BUCKET_VERSIONING_REQUIRED','Enable versioning on the private audio bucket and upload again.')
    return version

def playback_url(recording):
    if recording['object_key'].startswith('dev-fixture/'):
        raise AppError(404,'FIXTURE_AUDIO_UNAVAILABLE','This fictional seed report has no audio. Make a real worker recording to test playback.')
    try:
        url=client().generate_presigned_url('get_object',Params={'Bucket':settings().s3_bucket,'Key':recording['object_key'],
            'VersionId':recording['object_version_id'],'ResponseContentType':recording['content_type']},ExpiresIn=300)
        return {'url':url,'expires_at':now()+timedelta(seconds=300),'content_type':recording['content_type'],'duration_ms':recording['duration_ms']}
    except (ClientError,BotoCoreError) as exc:raise AppError(502,'STORAGE_UNAVAILABLE','Could not authorize audio playback. Try again.',True) from exc
