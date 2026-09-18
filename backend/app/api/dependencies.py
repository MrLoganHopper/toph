from dataclasses import replace
import hmac,os,ipaddress
from uuid import UUID
from fastapi import Depends,Request
from app.config import settings
from app.errors import AppError
from app.services.auth_service import Context,identity,recheck,rate_limit
from app.services.primitives import mac
from app.db.session import transaction

ALLOWED_PASSWORD_PATHS={'/api/v1/me','/api/v1/auth/logout','/api/v1/auth/change-password'}

def current_user(request:Request):
    token=request.cookies.get(settings().cookie_name,'')
    ctx=identity(token,request.url.path in ALLOWED_PASSWORD_PATHS)
    if request.method not in ('GET','HEAD','OPTIONS'):
        supplied=request.headers.get('x-csrf-token','')
        if len(supplied)!=64 or not supplied.isascii() or not hmac.compare_digest(supplied,mac(settings().csrf_secret,token)):
            raise AppError(403,'CSRF_INVALID','Refresh the page and try again.')
    return ctx

def require_farm_member(farm_id:UUID,ctx:Context=Depends(current_user)):
    ctx=replace(ctx,farm_id=farm_id)
    with transaction() as conn:role=recheck(conn,ctx)
    return replace(ctx,role=role)

def require_farm_admin(ctx:Context=Depends(require_farm_member)):
    if ctx.role!='admin':raise AppError(403,'ADMIN_REQUIRED','An administrator is required for this page.')
    return ctx

def client_ip(request:Request):
    peer=request.client.host if request.client else 'unknown'
    if settings().trust_vercel_proxy and os.getenv('VERCEL')=='1':
        raw=request.headers.get('x-vercel-forwarded-for','').split(',')[0].strip()
        try:peer=str(ipaddress.ip_address(raw))
        except ValueError:pass
    return peer

def throttle(ctx,policy,limit=30,seconds=3600):
    rate_limit(policy,f'{ctx.farm_id}:{ctx.user_id}',limit,seconds)
