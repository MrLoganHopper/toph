from datetime import datetime
from typing import Annotated
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Query
from pydantic import AwareDatetime
from sqlalchemy import select,func,delete
from app.schemas.contracts import Page,Shift,ShiftInput,ShiftUpdate
from app.api.dependencies import require_farm_member,require_farm_admin
from app.services.auth_service import Context,recheck
from app.services.catalog_service import require_resource,page
from app.services import shift_service as service
from app.services.primitives import now
from app.db.session import transaction
from app.errors import AppError
router=APIRouter(prefix='/api/v1/farms/{farm_id}/shifts',tags=['Schedule'])

@router.get('',response_model=Page[Shift])
def list_shifts(from_:Annotated[AwareDatetime,Query(alias='from')],to:AwareDatetime,employee_id:UUID|None=None,cursor:str|None=None,limit:int=Query(100,ge=1,le=100),ctx:Context=Depends(require_farm_member)):
    from app.models.tables import shifts
    if from_>=to:raise AppError(422,'INVALID_RANGE','End time must follow start time.')
    with transaction() as conn:
        role=recheck(conn,ctx);who=ctx.user_id if role!='admin' else employee_id
        where=[shifts.c.farm_id==ctx.farm_id,shifts.c.start_at<to,shifts.c.end_at>from_]
        if who:where.append(shifts.c.employee_id==who)
        result=page(conn,service.shift_statement().where(*where),select(func.count()).select_from(shifts).where(*where),['shifts',str(ctx.farm_id),str(who),from_.isoformat(),to.isoformat()],cursor,limit,shifts.c.id)
        result['items']=[service.view(r) for r in result['items']];return result

@router.post('',response_model=Shift,status_code=201)
def create_shift(data:ShiftInput,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import shifts
    identifier=uuid4();values=data.model_dump()
    with transaction() as conn:
        recheck(conn,ctx,admin=True);service.validate_shift(conn,ctx.farm_id,values)
        conn.execute(shifts.insert().values(id=identifier,farm_id=ctx.farm_id,**values));return service.get_shift(conn,ctx.farm_id,identifier)

@router.patch('/{shift_id}',response_model=Shift)
def update_shift(shift_id:UUID,data:ShiftUpdate,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import shifts,logs
    with transaction() as conn:
        recheck(conn,ctx,admin=True)
        # Lock the shift so an extraction referencing it cannot race an identity change.
        conn.execute(select(shifts.c.id).where(shifts.c.farm_id==ctx.farm_id,shifts.c.id==shift_id).with_for_update())
        old=require_resource(conn,shifts,ctx.farm_id,shift_id);values=data.model_dump(exclude_unset=True)
        if 'employee_id' in values and values['employee_id']!=old['employee_id'] and conn.execute(select(logs.c.id).where(logs.c.farm_id==ctx.farm_id,logs.c.shift_id==shift_id)).first():
            raise AppError(409,'SHIFT_REFERENCED','A linked report prevents changing this assignment to another worker.')
        service.validate_shift(conn,ctx.farm_id,{**old,**values})
        conn.execute(shifts.update().where(shifts.c.farm_id==ctx.farm_id,shifts.c.id==shift_id).values(**values,updated_at=now()))
        return service.get_shift(conn,ctx.farm_id,shift_id)

@router.delete('/{shift_id}',status_code=204)
def delete_shift(shift_id:UUID,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import shifts
    with transaction() as conn:
        recheck(conn,ctx,admin=True);require_resource(conn,shifts,ctx.farm_id,shift_id)
        conn.execute(delete(shifts).where(shifts.c.farm_id==ctx.farm_id,shifts.c.id==shift_id))
