import secrets
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select,func,delete
from app.schemas.contracts import Page,Member,MemberInput,MemberUpdate,MemberCreated,PasswordReset
from app.api.dependencies import require_farm_admin,throttle
from app.services.auth_service import Context,recheck
from app.services.catalog_service import page,require_resource,member_view
from app.services.primitives import PASSWORDS,now
from app.db.session import transaction
from app.errors import AppError
router=APIRouter(prefix='/api/v1/farms/{farm_id}/members',tags=['Members'])

@router.get('',response_model=Page[Member])
def members(role:str|None=None,enabled:bool|None=None,q:str=Query('',max_length=200),cursor:str|None=None,limit:int=Query(100,ge=1,le=100),ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import memberships as m,users as u
    if role not in (None,'admin','worker'):raise AppError(422,'INVALID_ROLE','Choose admin or worker.')
    with transaction() as conn:
        recheck(conn,ctx,admin=True);where=[m.c.farm_id==ctx.farm_id]
        if role:where.append(m.c.role==role)
        if enabled is not None:where.append(m.c.is_enabled==enabled)
        if q:where.append(u.c.name.icontains(q,autoescape=True)|u.c.username.icontains(q,autoescape=True))
        join=m.join(u,u.c.id==m.c.user_id)
        stmt=select(m.c.id,m.c.user_id,m.c.role,m.c.is_enabled,u.c.name,u.c.username).select_from(join).where(*where)
        return page(conn,stmt,select(func.count()).select_from(join).where(*where),['members',str(ctx.farm_id),role,enabled,q],cursor,limit,m.c.id)

@router.post('',response_model=MemberCreated,status_code=201)
def create_member(data:MemberInput,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import memberships as m,users as u
    throttle(ctx,'account-create',20);secret=secrets.token_urlsafe(18);uid,mid=uuid4(),uuid4()
    hashed=PASSWORDS.hash(secret)
    with transaction() as conn:
        recheck(conn,ctx,admin=True)
        if conn.execute(select(u.c.id).where(u.c.username==data.username)).first():raise AppError(409,'USERNAME_TAKEN','This username is already used. Choose another username.')
        conn.execute(u.insert().values(id=uid,username=data.username,name=data.name,password_hash=hashed,must_change_password=True))
        conn.execute(m.insert().values(id=mid,farm_id=ctx.farm_id,user_id=uid,role=data.role))
        return {'member':member_view(conn,ctx.farm_id,mid),'temporary_password':secret}

@router.patch('/{membership_id}',response_model=Member)
def update_member(membership_id:UUID,data:MemberUpdate,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import memberships as m,farms,users
    with transaction() as conn:
        # Lock before checking the acting admin so a queued, newly demoted admin cannot act.
        conn.execute(select(farms.c.id).where(farms.c.id==ctx.farm_id).with_for_update())
        recheck(conn,ctx,admin=True);old=require_resource(conn,m,ctx.farm_id,membership_id)
        conn.execute(select(users.c.id).where(users.c.id==old['user_id']).with_for_update())
        values=data.model_dump(exclude_unset=True)
        removes_admin=old['role']=='admin' and old['is_enabled'] and (values.get('role',old['role'])!='admin' or not values.get('is_enabled',old['is_enabled']))
        if removes_admin:
            count=conn.execute(select(func.count()).select_from(m.join(users,users.c.id==m.c.user_id)).where(m.c.farm_id==ctx.farm_id,m.c.role=='admin',m.c.is_enabled.is_(True),users.c.is_enabled.is_(True))).scalar_one()
            if count<=1:raise AppError(409,'LAST_ADMIN','Keep at least one enabled administrator in this farm.')
        conn.execute(m.update().where(m.c.farm_id==ctx.farm_id,m.c.id==membership_id).values(**values,updated_at=now()))
        return member_view(conn,ctx.farm_id,membership_id)

@router.post('/{membership_id}/reset-password',response_model=PasswordReset)
def reset(membership_id:UUID,ctx:Context=Depends(require_farm_admin)):
    from app.models.tables import memberships as m,users as u,sessions
    throttle(ctx,'account-reset',20);secret=secrets.token_urlsafe(18);hashed=PASSWORDS.hash(secret)
    with transaction() as conn:
        recheck(conn,ctx,admin=True);target=require_resource(conn,m,ctx.farm_id,membership_id)
        conn.execute(select(u.c.id).where(u.c.id==target['user_id']).with_for_update())
        all_members=list(conn.execute(select(m.c.farm_id,m.c.role).where(m.c.user_id==target['user_id'])).mappings())
        if target['role']!='worker' or any(r['farm_id']!=ctx.farm_id or r['role']=='admin' for r in all_members):
            raise AppError(403,'OPERATOR_REQUIRED','An operator must reset an admin or shared account.')
        conn.execute(u.update().where(u.c.id==target['user_id']).values(password_hash=hashed,must_change_password=True,updated_at=now()))
        conn.execute(delete(sessions).where(sessions.c.user_id==target['user_id']))
    return {'temporary_password':secret,'must_change_password':True}
