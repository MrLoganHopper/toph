"""Small HTTP adapters use the documented OpenAI endpoints with bounded requests."""
import asyncio,json
import httpx
from pydantic import ValidationError
from app.config import settings
from app.errors import AppError,missing_config
from app.schemas.contracts import Extraction
from app.prompts import interview_v1,extraction_v1

def mint(context):
    cfg=settings();missing_config(OPENAI_API_KEY=cfg.openai_api_key,OPENAI_REALTIME_MODEL=cfg.openai_realtime_model,OPENAI_TRANSCRIPTION_MODEL=cfg.openai_transcription_model)
    body={'session':{'type':'realtime','model':cfg.openai_realtime_model,'instructions':interview_v1.instructions(context),
        'tools':[interview_v1.UI_TOOL],'tool_choice':'auto','audio':{'input':{'transcription':{'model':cfg.openai_transcription_model},
        'turn_detection':{'type':'semantic_vad','eagerness':'medium','create_response':True,'interrupt_response':True}},'output':{'voice':cfg.openai_voice}}}}
    try:
        with httpx.Client(timeout=httpx.Timeout(12,connect=5)) as client:
            result=client.post('https://api.openai.com/v1/realtime/client_secrets',json=body,headers={'Authorization':'Bearer '+cfg.openai_api_key})
            result.raise_for_status();value=result.json()
            if not isinstance(value['value'],str) or not isinstance(value['expires_at'],int):raise ValueError()
            return {'client_secret':value['value'],'expires_at':value['expires_at'],'model':cfg.openai_realtime_model,'interview_version':interview_v1.VERSION}
    except (httpx.HTTPError,KeyError,ValueError,TypeError) as exc:
        raise AppError(502,'VOICE_PROVIDER_UNAVAILABLE','The voice service could not connect. Check model access and server configuration, then retry.',True) from exc

async def extract(context):
    cfg=settings();missing_config(OPENAI_API_KEY=cfg.openai_api_key,OPENAI_EXTRACT_MODEL=cfg.openai_extract_model)
    body={'model':cfg.openai_extract_model,'store':False,'input':[{'role':'system','content':extraction_v1.INSTRUCTIONS},
        {'role':'user','content':json.dumps(context,default=str,ensure_ascii=False)}],'text':{'format':{'type':'json_schema','name':'farm_report','strict':True,'schema':Extraction.model_json_schema()}},'max_output_tokens':2400}
    try:
        async with asyncio.timeout(cfg.ai_request_timeout_seconds):
            async with httpx.AsyncClient(timeout=httpx.Timeout(cfg.ai_request_timeout_seconds,connect=5)) as client:
                result=await client.post('https://api.openai.com/v1/responses',json=body,headers={'Authorization':'Bearer '+cfg.openai_api_key})
                result.raise_for_status();value=result.json()
                if value.get('status') not in ('completed',None):raise ValueError('Incomplete output')
                content=[entry for output in value.get('output',[]) if output.get('type')=='message' for entry in output.get('content',[])]
                if any(part.get('type')=='refusal' for part in content):raise AppError(502,'EXTRACTION_REFUSED','Your recording is saved. The model could not produce a report. Try again.',True)
                text=''.join(part.get('text','') for part in content if part.get('type')=='output_text')
                return Extraction.model_validate_json(text)
    except (TimeoutError,httpx.TimeoutException) as exc:raise AppError(504,'EXTRACTION_TIMEOUT','Your recording is saved. Try creating the report again.',True) from exc
    except (httpx.HTTPError,ValidationError,ValueError,TypeError,KeyError) as exc:raise AppError(502,'EXTRACTION_FAILED','Your recording is saved. Report generation failed. Try again.',True) from exc
