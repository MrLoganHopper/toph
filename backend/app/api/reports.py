from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy import select,delete
from app.schemas.contracts import LogFilters,Page,LogItem,LogDetail,DashboardResult,LogCreate,RecordingInput,RecordingReceipt,RecordingDetail,UploadAuthorization,AudioAuthorization,RealtimeInput,RealtimeSecret,Named
from app.api.dependencies import require_farm_member,require_farm_admin,throttle
from app.services.auth_service import Context,recheck
from app.db.session import transaction
router=APIRouter(prefix='/api/v1/farms/{farm_id}',tags=['Reports, audio and voice'])

@router.get('/logs',response_model=Page[LogItem])
def get_logs(filters:Annotated[LogFilters,Query()],ctx:Context=Depends(require_farm_member)):
    from app.services.log_service import list_logs
    with transaction() as conn:return list_logs(conn,ctx,filters)

@router.get('/dashboard',response_model=DashboardResult)
def get_dashboard(filters:Annotated[LogFilters,Query()],ctx:Context=Depends(require_farm_admin)):
    from app.services.log_service import dashboard
    with transaction() as conn:return dashboard(conn,ctx,filters)

@router.get('/logs/{log_id}',response_model=LogDetail)
def get_log(log_id:UUID,ctx:Context=Depends(require_farm_member)):
    from app.services.log_service import detail
    with transaction() as conn:return detail(conn,ctx,log_id)

@router.post('/realtime/client-secret',response_model=RealtimeSecret)
def realtime(data:RealtimeInput,ctx:Context=Depends(require_farm_member)):
    from app.services.ai_service import mint_realtime
    throttle(ctx,'voice',10);return mint_realtime(ctx,data.shift_id)

@router.post('/recordings',response_model=RecordingReceipt,status_code=201)
def create_recording(data:RecordingInput,response:Response,ctx:Context=Depends(require_farm_member)):
    from app.services.recording_service import initialize
    throttle(ctx,'recording',30);result,status=initialize(ctx,data);response.status_code=status;return result

@router.get('/recordings/{recording_id}',response_model=RecordingDetail)
def get_recording(recording_id:UUID,ctx:Context=Depends(require_farm_member)):
    from app.services.recording_service import get_receipt
    return get_receipt(ctx,recording_id)

@router.post('/recordings/{recording_id}/upload-url',response_model=UploadAuthorization)
def get_upload_url(recording_id:UUID,ctx:Context=Depends(require_farm_member)):
    from app.services.recording_service import authorize_upload
    throttle(ctx,'upload-signing',60);return authorize_upload(ctx,recording_id)

@router.post('/recordings/{recording_id}/complete',response_model=RecordingReceipt)
def confirm_upload(recording_id:UUID,ctx:Context=Depends(require_farm_member)):
    from app.services.recording_service import complete
    return complete(ctx,recording_id)

@router.post('/logs',response_model=LogDetail,status_code=201)
async def create_log(data:LogCreate,response:Response,ctx:Context=Depends(require_farm_member)):
    from app.services.ai_service import generate_log
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(throttle,ctx,'extraction',30)
    result,status=await generate_log(ctx,data);response.status_code=status;return result

@router.get('/logs/{log_id}/audio-url',response_model=AudioAuthorization)
def get_audio(log_id:UUID,ctx:Context=Depends(require_farm_member)):
    from app.services.recording_service import playback
    return playback(ctx,log_id)

@router.put('/logs/{log_id}/tags/{tag_id}',response_model=list[Named])
def attach_tag(log_id:UUID,tag_id:UUID,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import logs,tags,log_tags
    from app.services.catalog_service import require_resource
    from app.services.log_service import tags_for
    from sqlalchemy.dialects.postgresql import insert
    with transaction() as conn:
        recheck(conn,ctx,admin=True);require_resource(conn,logs,ctx.farm_id,log_id);require_resource(conn,tags,ctx.farm_id,tag_id)
        conn.execute(insert(log_tags).values(farm_id=ctx.farm_id,log_id=log_id,tag_id=tag_id).on_conflict_do_nothing())
        return tags_for(conn,ctx,[log_id])[log_id]

@router.delete('/logs/{log_id}/tags/{tag_id}',status_code=204)
def detach_tag(log_id:UUID,tag_id:UUID,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import logs,tags,log_tags
    from app.services.catalog_service import require_resource
    with transaction() as conn:
        recheck(conn,ctx,admin=True);require_resource(conn,logs,ctx.farm_id,log_id);require_resource(conn,tags,ctx.farm_id,tag_id)
        conn.execute(delete(log_tags).where(log_tags.c.farm_id==ctx.farm_id,log_tags.c.log_id==log_id,log_tags.c.tag_id==tag_id))
