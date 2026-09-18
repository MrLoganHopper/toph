import json
import logging
import time
import traceback
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.config import settings
from app.errors import AppError
from app.api import auth,farms,catalogs,members,shifts,reports

logger=logging.getLogger('toph')
app=FastAPI(title='TOPH Farm Voice Reporting',version='1.0.0',docs_url='/docs' if settings().app_env!='production' else None,redoc_url=None)
for module in (auth,farms,catalogs,members,shifts,reports):
    app.include_router(module.router)


def error_response(request,status,code,message,retryable=False,retry_after=None,recording_id=None):
    payload={'error':{'code':code,'message':message,'retryable':retryable,'request_id':getattr(request.state,'request_id','unavailable')}}
    if recording_id:
        payload['error']['recording_id']=recording_id
    return JSONResponse(payload,status_code=status,headers={'Cache-Control':'private, no-store','CDN-Cache-Control':'no-store','Vercel-CDN-Cache-Control':'no-store','X-Content-Type-Options':'nosniff',**({'Retry-After':str(retry_after)} if retry_after else {})})

@app.exception_handler(AppError)
async def app_error(request:Request,exc:AppError):
    return error_response(request,exc.status,exc.code,exc.message,exc.retryable,exc.retry_after,exc.recording_id)

@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,_exc:RequestValidationError):
    return error_response(request,422,'INVALID_INPUT','Check the required fields, date ranges, and permitted values.')

@app.exception_handler(HTTPException)
async def http_error(request:Request,exc:HTTPException):
    return error_response(request,exc.status_code,'NOT_FOUND' if exc.status_code==404 else 'HTTP_ERROR',
                          'This API resource does not exist.' if exc.status_code==404 else 'The request could not be completed.')

@app.exception_handler(IntegrityError)
async def integrity_error(request:Request,_exc:IntegrityError):
    return error_response(request,409,'CONFLICT','A name is already used or a historical reference prevents this change.')

@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.exception(
        "DATABASE ERROR request_id=%s original=%r",
        getattr(request.state, "request_id", ""),
        getattr(exc, "orig", exc),
    )
    return error_response(
        request,
        503,
        "DATABASE_UNAVAILABLE",
        "The database is temporarily unavailable. Check the server configuration and retry.",
        True,
    )

@app.exception_handler(Exception)
async def unexpected_error(request:Request,exc:Exception):
    logger.error(json.dumps({'request_id':getattr(request.state,'request_id',''),'type':type(exc).__name__}))
    return error_response(request,500,'INTERNAL_ERROR','The request could not be completed. Contact your administrator with the request ID.',True)

@app.get('/healthz')
def healthz():
    return {'ok':True}


class RequestBoundary:
    """Bound JSON size before routing and add private response/security headers."""
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        started=time.monotonic()
        rid=str(uuid4())
        scope.setdefault('state',{})['request_id']=rid
        headers={k.decode('latin-1').lower():v.decode('latin-1') for k,v in scope['headers']}
        status=500
        async def safe_send(message):
            nonlocal status
            if message['type']=='http.response.start':
                status=message['status']
                hs=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in (b'cache-control',b'cdn-cache-control',b'vercel-cdn-cache-control')]
                hs.extend([(b'cache-control',b'private, no-store'),(b'cdn-cache-control',b'no-store'),
                           (b'vercel-cdn-cache-control',b'no-store'),(b'x-request-id',rid.encode()),(b'x-content-type-options',b'nosniff')])
                message['headers']=hs
            await send(message)
        async def reject(code,text,statuscode):
            response=JSONResponse({'error':{'code':code,'message':text,'retryable':False,'request_id':rid}},status_code=statuscode)
            await response(scope,receive,safe_send)
        if scope['method'] not in ('GET','HEAD','OPTIONS'):
            if headers.get('origin') not in settings().app_origins:
                return await reject('ORIGIN_INVALID','This application origin is not permitted.',403)
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            body.extend(message.get('body',b''))
            if len(body)>262144:
                return await reject('BODY_TOO_LARGE','Request metadata exceeds 256 KiB. Audio must upload directly to storage.',413)
            if not message.get('more_body',False):
                break
        if body and scope['method'] not in ('GET','HEAD') and headers.get('content-type','').split(';')[0].strip()!='application/json':
            return await reject('CONTENT_TYPE','Use application/json for API metadata.',415)
        consumed=False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        try:
            await self.app(scope,replay,safe_send)
        finally:
            logger.info(json.dumps({'request_id':rid,'method':scope['method'],'path':scope['path'],
                                    'status':status,'elapsed_ms':round((time.monotonic()-started)*1000)}))

app.add_middleware(RequestBoundary)
