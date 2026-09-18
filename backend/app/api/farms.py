from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from uuid import UUID
from fastapi import APIRouter,Depends
from sqlalchemy import select
from app.schemas.contracts import Farm,FarmUpdate,Bootstrap
from app.api.dependencies import require_farm_member,require_farm_admin
from app.services.auth_service import Context,recheck,safe_user
from app.services.catalog_service import named,member_view
from app.services.primitives import now
from app.db.session import transaction
router=APIRouter(prefix='/api/v1/farms/{farm_id}',tags=['Farms'])

@router.get('',response_model=Farm)
def read_farm(ctx:Context=Depends(require_farm_member)):
    from app.models.tables import farms
    with transaction() as conn:recheck(conn,ctx);return dict(conn.execute(select(farms).where(farms.c.id==ctx.farm_id)).mappings().one())

@router.patch('',response_model=Farm)
def edit_farm(data:FarmUpdate,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import farms
    with transaction() as conn:
        recheck(conn,ctx,admin=True)
        return dict(conn.execute(farms.update().where(farms.c.id==ctx.farm_id).values(**data.model_dump(exclude_unset=True),updated_at=now()).returning(farms)).mappings().one())

@router.get('/bootstrap',response_model=Bootstrap)
def bootstrap(local_date:date|None=None,ctx:Context=Depends(require_farm_member)):
    from app.models.tables import farms,users,memberships,fields,activities,fertilizers,tags,shifts
    from app.services.shift_service import shift_statement,view
    with transaction() as conn:
        role=recheck(conn,ctx)
        farm=dict(conn.execute(select(farms).where(farms.c.id==ctx.farm_id)).mappings().one())
        user=conn.execute(select(users).where(users.c.id==ctx.user_id)).mappings().one()
        mid=conn.execute(select(memberships.c.id).where(memberships.c.farm_id==ctx.farm_id,memberships.c.user_id==ctx.user_id)).scalar_one()
        zone=ZoneInfo(farm['timezone']);day=local_date or now().astimezone(zone).date();start=datetime.combine(day,datetime.min.time(),zone);end=start+timedelta(days=1)
        own=[view(r) for r in conn.execute(shift_statement().where(shifts.c.farm_id==ctx.farm_id,shifts.c.employee_id==ctx.user_id,shifts.c.start_at<end,shifts.c.end_at>start).order_by(shifts.c.start_at)).mappings()]
        workers=[dict(r) for r in conn.execute(select(users.c.id,users.c.name).join(memberships,memberships.c.user_id==users.c.id).where(memberships.c.farm_id==ctx.farm_id,memberships.c.role=='worker').order_by(users.c.name)).mappings()] if role=='admin' else []
        return {'user':safe_user(user),'farm':farm,'membership':member_view(conn,ctx.farm_id,mid),'fields':named(conn,fields,ctx.farm_id),
            'activities':named(conn,activities,ctx.farm_id),'fertilizers':named(conn,fertilizers,ctx.farm_id),'tags':named(conn,tags,ctx.farm_id) if role=='admin' else [],'workers':workers,'shifts':own}
