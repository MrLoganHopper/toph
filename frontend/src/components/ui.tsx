import {useEffect,useId,useRef,useState,type ButtonHTMLAttributes,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {AlertCircle,LoaderCircle,X} from 'lucide-react';
import {ApiError} from '../api/client';
export function Button({className='',type='button',...props}:ButtonHTMLAttributes<HTMLButtonElement>){return <button type={type} className={`button ${className}`} {...props}/>;}
export function Busy({label='Loading...'}:{label?:string}){return <div className="busy" role="status"><LoaderCircle className="spin" size={20}/><span>{label}</span></div>;}
export function ErrorBox({error,retry}:{error:unknown;retry?:()=>void}){return <div className="error-box" role="alert"><AlertCircle size={18}/><div><p>{error instanceof Error?error.message:'Something went wrong. Please try again.'}</p>{error instanceof ApiError&&error.requestId&&<p className="small">Reference: {error.requestId}</p>}{retry&&<Button onClick={retry}>Try again</Button>}</div></div>;}
export function Empty({title,children}:{title:string;children?:ReactNode}){return <div className="empty-state"><h3>{title}</h3><p>{children}</p></div>;}
export function Dropdown({label,children,className=''}:{label:ReactNode;children:ReactNode;className?:string}){
 const [open,setOpen]=useState(false);const ref=useRef<HTMLDivElement>(null);const id=useId();
 useEffect(()=>{if(!open)return;const close=(event:PointerEvent)=>{if(!ref.current?.contains(event.target as Node))setOpen(false);};const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);ref.current?.querySelector('button')?.focus();}};document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key);};},[open]);
 return <div className={`dropdown ${className}`} ref={ref}><Button aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{label}</Button>{open&&<div id={id} className="dropdown-panel route-enter">{children}</div>}</div>;
}
export function Modal({title,close,children,wide=false}:{title:string;close:()=>void;children:ReactNode;wide?:boolean}){
 const ref=useRef<HTMLDivElement>(null);const titleId=useId();const onClose=useRef(close);onClose.current=close;
 useEffect(()=>{const old=document.activeElement as HTMLElement|null;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';ref.current?.focus();
 const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.stopPropagation();onClose.current();return;}if(event.key==='Tab'){const focusable=Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],audio[controls],[tabindex="0"]')||[]);const first=focusable[0],last=focusable.at(-1);if(!first){event.preventDefault();return;}if(event.shiftKey&&(document.activeElement===first||document.activeElement===ref.current)){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}};
 const element=ref.current;element?.addEventListener('keydown',onKey);return()=>{element?.removeEventListener('keydown',onKey);document.body.style.overflow=overflow;old?.focus();};},[]);
 return createPortal(<div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)close();}}><div role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className={`modal ${wide?'modal-wide':''}`} ref={ref}><header className="modal-heading"><h2 id={titleId}>{title}</h2><Button aria-label="Close dialog" onClick={close}><X size={18}/></Button></header>{children}</div></div>,document.body);
}
export const dateLabel=(date:string,zone:string)=>new Intl.DateTimeFormat('en-US',{timeZone:zone,month:'long',day:'numeric',year:'numeric'}).format(new Date(date));
export const timeLabel=(date:string,zone:string)=>new Intl.DateTimeFormat('en-US',{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(date));
