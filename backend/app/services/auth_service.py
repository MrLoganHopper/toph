"""Opaque server sessions and farm-scoped authorization. No browser role is trusted."""
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID,uuid4
import secrets
from sqlalchemy import select,delete,func
from argon2.exceptions import VerificationError,InvalidHashError
from app.config import settings
from app.errors import AppError,missing_config,not_found
from app.db.session import transaction
from app.services.primitives import PASSWORDS,now,digest,mac

@dataclass(frozen=True)
class Context:
    user_id:UUID
    session_id:UUID
    token_hash:str
    farm_id:UUID|None=None
    role:str|None=None

def check_secrets():
    cfg=settings();missing_config(CSRF_SECRET=cfg.csrf_secret,RATE_LIMIT_SECRET=cfg.rate_limit_secret)
    if min(len(cfg.csrf_secret),len(cfg.rate_limit_secret))<32 or cfg.csrf_secret==cfg.rate_limit_secret:
        raise AppError(503,'CONFIGURATION_REQUIRED','Set two independent server secrets of at least 32 characters.')
    if cfg.app_env in ('production','preview') and not cfg.cookie_secure:
        raise AppError(503,'CONFIGURATION_REQUIRED','Enable COOKIE_SECURE for HTTPS deployments.')

def safe_user(row):
    return {k:row[k] for k in ('id','name','username','must_change_password')}

def identity(token,allow_password_change=False):
    if not token or len(token)>256:raise AppError(401,'AUTH_REQUIRED','Log in to continue.')
    check_secrets()
    from app.models.tables import users,sessions
    with transaction() as conn:
        row=conn.execute(select(users,sessions.c.id.label('session_id')).join(sessions,users.c.id==sessions.c.user_id).where(
            sessions.c.token_hash==digest(token),sessions.c.expires_at>now(),users.c.is_enabled.is_(True))).mappings().first()
        if not row:raise AppError(401,'AUTH_REQUIRED','Your session expired. Log in to continue.')
        if row['must_change_password'] and not allow_password_change:
            raise AppError(403,'PASSWORD_CHANGE_REQUIRED','Change your temporary password to continue.')
        return Context(row['id'],row['session_id'],digest(token))

def recheck(conn,ctx,admin=False):
    from app.models.tables import users,sessions,memberships
    user=conn.execute(select(users.c.id,users.c.must_change_password).join(sessions,users.c.id==sessions.c.user_id).where(
        users.c.id==ctx.user_id,users.c.is_enabled.is_(True),sessions.c.id==ctx.session_id,
        sessions.c.token_hash==ctx.token_hash,sessions.c.expires_at>now())).mappings().first()
    if not user:raise AppError(401,'AUTH_REQUIRED','Your session expired. Log in to continue.')
    if user['must_change_password']:raise AppError(403,'PASSWORD_CHANGE_REQUIRED','Change your temporary password to continue.')
    role=conn.execute(select(memberships.c.role).where(memberships.c.farm_id==ctx.farm_id,
        memberships.c.user_id==ctx.user_id,memberships.c.is_enabled.is_(True))).scalar_one_or_none()
    if role is None:not_found()
    if admin and role!='admin':raise AppError(403,'ADMIN_REQUIRED','An administrator is required for this action.')
    return role

def auth_result(conn,user_id,token):
    from app.models.tables import users,memberships,farms
    user=conn.execute(select(users).where(users.c.id==user_id,users.c.is_enabled.is_(True))).mappings().first()
    if not user:raise AppError(401,'AUTH_REQUIRED','Log in to continue.')
    rows=conn.execute(select(memberships.c.id.label('membership_id'),memberships.c.role,memberships.c.is_enabled,farms).join(farms,farms.c.id==memberships.c.farm_id).where(memberships.c.user_id==user_id,memberships.c.is_enabled.is_(True)).order_by(farms.c.name,farms.c.id)).mappings()
    member=[{'id':r['membership_id'],'role':r['role'],'is_enabled':r['is_enabled'],
        'farm':{k:r[k] for k in ('id','name','timezone','created_at','updated_at')}} for r in rows]
    return {'user':safe_user(user),'memberships':member,'csrf_token':mac(settings().csrf_secret,token),'must_change_password':user['must_change_password']}

def new_session(conn,user_id):
    from app.models.tables import sessions
    token=secrets.token_urlsafe(48);stamp=now()
    conn.execute(sessions.insert().values(id=uuid4(),user_id=user_id,token_hash=digest(token),created_at=stamp,expires_at=stamp+timedelta(hours=12)))
    return token

def login(data):
    check_secrets()
    from app.models.tables import users
    with transaction() as conn:
        row=conn.execute(select(users).where(users.c.username==data.username).with_for_update()).mappings().first()
        # A valid Argon2 hash with no login identity supplies the same work for unknown users.
        encoded=row['password_hash'] if row else DUMMY_HASH
        valid=False
        try:valid=PASSWORDS.verify(encoded,data.password)
        except (VerificationError,InvalidHashError):pass
        if not row or not valid or not row['is_enabled']:
            raise AppError(401,'LOGIN_FAILED','Username or password is incorrect.')
        if PASSWORDS.check_needs_rehash(encoded):conn.execute(users.update().where(users.c.id==row['id']).values(password_hash=PASSWORDS.hash(data.password),updated_at=now()))
        token=new_session(conn,row['id'])
        return auth_result(conn,row['id'],token),token

DUMMY_HASH=PASSWORDS.hash(secrets.token_urlsafe(48))

def change_password(ctx,data):
    from app.models.tables import users,sessions
    with transaction() as conn:
        user=conn.execute(select(users).where(users.c.id==ctx.user_id,users.c.is_enabled.is_(True)).with_for_update()).mappings().first()
        if not user:raise AppError(401,'AUTH_REQUIRED','Log in to continue.')
        try:PASSWORDS.verify(user['password_hash'],data.current_password)
        except (VerificationError,InvalidHashError) as exc:raise AppError(403,'PASSWORD_INCORRECT','The current password is incorrect.') from exc
        conn.execute(users.update().where(users.c.id==ctx.user_id).values(password_hash=PASSWORDS.hash(data.new_password),must_change_password=False,updated_at=now()))
        conn.execute(delete(sessions).where(sessions.c.user_id==ctx.user_id))
        token=new_session(conn,ctx.user_id)
        return auth_result(conn,ctx.user_id,token),token

def rate_limit(policy,subject,limit,seconds):
    check_secrets()
    from app.models.tables import rate_buckets
    from sqlalchemy.dialects.postgresql import insert
    check_secrets();stamp=now();start=stamp.replace(microsecond=0)-timedelta(seconds=int(stamp.timestamp())%seconds)
    key=mac(settings().rate_limit_secret,policy+':'+str(subject))
    with transaction() as conn:
        count=conn.execute(insert(rate_buckets).values(key_hash=key,bucket_start=start,request_count=1,expires_at=start+timedelta(seconds=seconds*2)).on_conflict_do_update(
            index_elements=[rate_buckets.c.key_hash,rate_buckets.c.bucket_start],set_={'request_count':rate_buckets.c.request_count+1}).returning(rate_buckets.c.request_count)).scalar_one()
    if count>limit:raise AppError(429,'RATE_LIMIT','Too many attempts. Try again later.',True,max(1,int((start+timedelta(seconds=seconds)-stamp).total_seconds())))
