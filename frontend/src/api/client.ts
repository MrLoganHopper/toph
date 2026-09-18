let csrfToken='';
export function setCsrf(value:string){csrfToken=value;}
export class ApiError extends Error {
  constructor(public status:number,public code:string,message:string,public requestId?:string,public retryable=false,public recordingId?:string){super(message);this.name='ApiError';}
}
export type ApiOptions=Omit<RequestInit,'body'> & {body?:unknown};
export function queryString(values:object){const params=new URLSearchParams();for(const [key,value] of Object.entries(values)){if(value!==undefined&&value!==null&&value!=='')params.set(key,String(value));}const text=params.toString();return text?'?'+text:'';}
export async function api<T=unknown>(path:string,options:ApiOptions={}):Promise<T>{
  const base=import.meta.env.VITE_API_BASE_URL||'/api/v1';
  if(!base.startsWith('/')||base.startsWith('//'))throw new Error('VITE_API_BASE_URL must be a same-origin relative path.');
  const method=(options.method||'GET').toUpperCase();const headers=new Headers(options.headers);
  headers.set('Accept','application/json');
  if(options.body!==undefined)headers.set('Content-Type','application/json');
  if(!['GET','HEAD','OPTIONS'].includes(method)&&csrfToken)headers.set('X-CSRF-Token',csrfToken);
  let response:Response;
  try{response=await fetch(base+path,{...options,method,headers,body:options.body!==undefined?JSON.stringify(options.body):undefined,credentials:'same-origin',cache:'no-store'});}
  catch(error){if(error instanceof DOMException&&error.name==='AbortError')throw error;throw new ApiError(0,'NETWORK_ERROR','Could not reach the server. Check your connection and try again.',undefined,true);}
  if(response.status===204)return undefined as T;
  if(!(response.headers.get('content-type')||'').includes('application/json'))throw new ApiError(response.status,'API_ROUTING_ERROR','The API returned a non-JSON response. Check the backend deployment and the /api rewrite.');
  const value=await response.json() as {error?:{code:string;message:string;request_id?:string;retryable?:boolean;recording_id?:string}};
  if(!response.ok){const e=value.error;throw new ApiError(response.status,e?.code||'API_ERROR',e?.message||'The request failed.',e?.request_id,e?.retryable,e?.recording_id);}
  return value as T;
}
