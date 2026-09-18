import asyncio
import json
from uuid import UUID, uuid4
import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.db.session import transaction
from app.errors import AppError, missing_config, not_found
from app.models.tables import farms, fields, activities, fertilizers, shifts, recordings, logs
from app.schemas.contracts import Extraction
from app.services.auth_service import recheck
from app.services.catalog_service import named, require_resource
from app.services.log_service import detail
from app.services.primitives import canonical, digest, mac
from app.prompts import interview_v1, extraction_v1


def farm_vocabulary(conn,ctx):
    farm = dict(conn.execute(select(farms).where(farms.c.id==ctx.farm_id)).mappings().one())
    return {'farm': {k:farm[k] for k in ('name','timezone')},
            'fields':named(conn,fields,ctx.farm_id),'activities':named(conn,activities,ctx.farm_id),
            'fertilizers':named(conn,fertilizers,ctx.farm_id)}


def mint_realtime(ctx,shift_id):
    from app.providers.ai import mint
    from datetime import datetime
    from zoneinfo import ZoneInfo
    with transaction() as conn:
        recheck(conn,ctx)
        context=farm_vocabulary(conn,ctx)
        if shift_id:
            shift=require_resource(conn,shifts,ctx.farm_id,shift_id)
            if shift['employee_id']!=ctx.user_id:
                not_found()
            context['scheduled_assignment']=dict(shift)
    context['farm_local_date']=datetime.now(ZoneInfo(context['farm']['timezone'])).date().isoformat()
    return mint(context)


def existing_log(conn,ctx,recording_id,submission_hash):
    row=conn.execute(select(logs.c.id,logs.c.submission_hash).where(
        logs.c.farm_id==ctx.farm_id,logs.c.recording_id==recording_id)).mappings().first()
    if not row:
        return None
    if row['submission_hash']!=submission_hash:
        raise AppError(409,'SUBMISSION_CONFLICT','This recording already has a report with a different linked shift.')
    return detail(conn,ctx,row['id'])


def load_extraction(ctx,data,submission_hash):
    with transaction() as conn:
        role=recheck(conn,ctx)
        recording=require_resource(conn,recordings,ctx.farm_id,data.recording_id)
        if role!='admin' and recording['employee_id']!=ctx.user_id:
            not_found()
        previous=existing_log(conn,ctx,data.recording_id,submission_hash)
        if previous:
            return None,previous
        if not recording['uploaded_at'] or not recording['object_version_id']:
            raise AppError(422,'AUDIO_NOT_UPLOADED','Finish uploading this recording before creating a report.')
        context=farm_vocabulary(conn,ctx)
        context.update(transcript=recording['transcript'],recorded_at=recording['recorded_at'],interview_version=recording['interview_version'])
        if data.shift_id:
            shift=require_resource(conn,shifts,ctx.farm_id,data.shift_id)
            if shift['employee_id']!=recording['employee_id']:
                not_found()
            context['scheduled_assignment']=dict(shift)
        return context,None


async def extract(context):
    from app.providers.ai import extract as provider_extract
    return await provider_extract(context)


def commit_extraction(ctx,data,submission_hash,output):
    def commit_once():
        with transaction() as conn:
            role=recheck(conn,ctx)
            recording=require_resource(conn,recordings,ctx.farm_id,data.recording_id)
            if role!='admin' and recording['employee_id']!=ctx.user_id:
                not_found()
            previous=existing_log(conn,ctx,data.recording_id,submission_hash)
            if previous:
                return previous,200
            if data.shift_id:
                shift=require_resource(conn,shifts,ctx.farm_id,data.shift_id)
                if shift['employee_id']!=recording['employee_id']:
                    not_found()
            refs={}
            for key,table in [('field_id',fields),('activity_id',activities),('fertilizer_id',fertilizers)]:
                raw=getattr(output,key)
                try:
                    ref=UUID(raw) if raw else None
                except ValueError as exc:
                    raise AppError(502,'INVALID_EXTRACTION','The model returned an invalid catalog ID. Your recording is saved.',True) from exc
                if ref and not conn.execute(select(table.c.id).where(table.c.farm_id==ctx.farm_id,table.c.id==ref)).first():
                    raise AppError(502,'INVALID_EXTRACTION','The model returned an unavailable catalog ID. Your recording is saved.',True)
                refs[key]=ref
            rid=uuid4()
            conn.execute(logs.insert().values(id=rid,farm_id=ctx.farm_id,employee_id=recording['employee_id'],
                recording_id=recording['id'],shift_id=data.shift_id,recorded_at=recording['recorded_at'],**refs,
                summary=output.summary.strip(),answers=output.answers.model_dump(),extraction_confidence=output.extraction_confidence,
                extractor_model=settings().openai_extract_model,extraction_version=extraction_v1.VERSION,submission_hash=submission_hash))
            return detail(conn,ctx,rid),201
    try:
        return commit_once()
    except IntegrityError:
        with transaction() as conn:
            recheck(conn,ctx)
            previous=existing_log(conn,ctx,data.recording_id,submission_hash)
            if previous:
                return previous,200
        raise AppError(409,'REFERENCE_CHANGED','A referenced assignment or catalog entry changed. Your recording is saved.',True)


async def generate_log(ctx,data):
    submission_hash=digest(canonical({'recording_id':data.recording_id,'shift_id':data.shift_id}))
    try:
        async with asyncio.timeout(50):
            context,previous=await run_in_threadpool(load_extraction,ctx,data,submission_hash)
            if previous:
                return previous,200
            output=await extract(context)
            return await run_in_threadpool(commit_extraction,ctx,data,submission_hash,output)
    except TimeoutError as exc:
        raise AppError(504,'EXTRACTION_TIMEOUT','Your recording is saved. Try creating the report again.',True,recording_id=str(data.recording_id)) from exc
    except AppError as exc:
        exc.recording_id=str(data.recording_id)
        raise
