from fastapi import APIRouter,Depends,Request,Response
from sqlalchemy import delete
from app.schemas.contracts import AuthResult,LoginInput,PasswordChange
from app.config import settings
from app.api.dependencies import current_user,client_ip
from app.services import auth_service
from app.services.auth_service import Context
from app.db.session import transaction
router=APIRouter(prefix='/api/v1',tags=['Authentication'])

def set_cookie(response,token):
    cfg=settings()
    response.set_cookie(cfg.cookie_name,token,max_age=43200,httponly=True,secure=cfg.cookie_secure,samesite='lax',path='/')

@router.post('/auth/login',response_model=AuthResult)
def login(data:LoginInput,request:Request,response:Response):
    ip=client_ip(request)
    auth_service.rate_limit('login-ip',ip,60,900)
    auth_service.rate_limit('login-user-ip',data.username+':'+ip,10,900)
    result,token=auth_service.login(data);set_cookie(response,token);return result

@router.get('/me',response_model=AuthResult)
def me(request:Request,ctx:Context=Depends(current_user)):
    with transaction() as conn:return auth_service.auth_result(conn,ctx.user_id,request.cookies[settings().cookie_name])

@router.post('/auth/logout',status_code=204)
def logout(response:Response,ctx:Context=Depends(current_user)):
    from app.models.tables import sessions
    with transaction() as conn:conn.execute(delete(sessions).where(sessions.c.id==ctx.session_id))
    response.delete_cookie(settings().cookie_name,path='/',secure=settings().cookie_secure,httponly=True,samesite='lax')

@router.post('/auth/change-password',response_model=AuthResult)
def change(data:PasswordChange,response:Response,ctx:Context=Depends(current_user)):
    auth_service.rate_limit('self-password-change',str(ctx.user_id),20,3600)
    result,token=auth_service.change_password(ctx,data);set_cookie(response,token);return result
