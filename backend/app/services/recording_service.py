from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.db.session import transaction
from app.errors import AppError,not_found
from app.services.auth_service import recheck
from app.services.catalog_service import require_resource
from app.services.primitives import now,canonical,digest
from app.providers import storage

def receipt(conn,ctx,row,full=False):
    from app.models.tables import logs
    out={k:row[k] for k in ('id','recorded_at','uploaded_at')}
    out['linked_log_id']=conn.execute(select(logs.c.id).where(logs.c.farm_id==ctx.farm_id,logs.c.recording_id==row['id'])).scalar_one_or_none()
    if full:out.update({k:row[k] for k in ('content_type','size_bytes','duration_ms','transcript','waveform_peaks','interview_version')})
    return out

def authorized_recording(conn,ctx,identifier,owner=False):
    from app.models.tables import recordings
    role=recheck(conn,ctx);row=require_resource(conn,recordings,ctx.farm_id,identifier)
    if (owner or role!='admin') and row['employee_id']!=ctx.user_id:not_found()
    return row

def initialize(ctx,data):
    from app.models.tables import recordings
    if data.size_bytes>settings().max_recording_bytes or data.duration_ms>settings().max_recording_duration_ms:
        raise AppError(422,'RECORDING_LIMIT','This recording exceeds the configured recording limit.')
    values=data.model_dump(mode='json');hashed=digest(canonical(values));values=data.model_dump();values['transcript']=[t.model_dump() for t in data.transcript]
    def replay(conn):
        old=conn.execute(select(recordings).where(recordings.c.farm_id==ctx.farm_id,recordings.c.employee_id==ctx.user_id,recordings.c.client_submission_id==data.client_submission_id)).mappings().first()
        if old:
            if old['payload_hash']!=hashed:raise AppError(409,'RECORDING_CONFLICT','This submission ID has already been used with different recording metadata.')
            return receipt(conn,ctx,old),200
        return None
    try:
        with transaction() as conn:
            recheck(conn,ctx);prior=replay(conn)
            if prior:return prior
            rid=uuid4();extension={'audio/webm':'webm','audio/mp4':'mp4','audio/ogg':'ogg'}[data.content_type]
            row=conn.execute(recordings.insert().values(id=rid,farm_id=ctx.farm_id,employee_id=ctx.user_id,payload_hash=hashed,
                object_key=f'farms/{ctx.farm_id}/recordings/{rid}.{extension}',**values).returning(recordings)).mappings().one()
            return receipt(conn,ctx,row),201
    except IntegrityError:
        with transaction() as conn:
            recheck(conn,ctx);prior=replay(conn)
            if prior:return prior
        raise

def get_receipt(ctx,identifier):
    with transaction() as conn:return receipt(conn,ctx,authorized_recording(conn,ctx,identifier),True)

def authorize_upload(ctx,identifier):
    with transaction() as conn:
        row=authorized_recording(conn,ctx,identifier,owner=True)
        if row['uploaded_at']:raise AppError(409,'ALREADY_UPLOADED','This recording has already been confirmed.')
    return storage.upload_form(row)

def complete(ctx,identifier):
    from app.models.tables import recordings
    with transaction() as conn:
        row=authorized_recording(conn,ctx,identifier,owner=True)
        if row['uploaded_at']:return receipt(conn,ctx,row)
    version=storage.confirm_object(row) # No database transaction waits for S3.
    with transaction() as conn:
        conn.execute(select(recordings.c.id).where(recordings.c.farm_id==ctx.farm_id,recordings.c.id==identifier).with_for_update())
        row=authorized_recording(conn,ctx,identifier,owner=True)
        if row['uploaded_at']:return receipt(conn,ctx,row)
        updated=conn.execute(recordings.update().where(recordings.c.farm_id==ctx.farm_id,recordings.c.id==identifier).values(uploaded_at=now(),object_version_id=version).returning(recordings)).mappings().one()
        return receipt(conn,ctx,updated)

def playback(ctx,identifier):
    from app.models.tables import logs,recordings
    with transaction() as conn:
        role=recheck(conn,ctx);log=require_resource(conn,logs,ctx.farm_id,identifier)
        if role!='admin' and log['employee_id']!=ctx.user_id:not_found()
        row=require_resource(conn,recordings,ctx.farm_id,log['recording_id'])
        if not row['uploaded_at']:raise AppError(422,'AUDIO_NOT_UPLOADED','Audio upload has not been confirmed.')
    return storage.playback_url(row)
