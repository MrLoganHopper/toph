import {useCallback,useEffect,useMemo,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import type {DateRange,LogFilters} from '../../api/types';
import {parseFilters} from './filterCore';
export function useFilters(defaultRange:DateRange='all'){
 const [params,setParams]=useSearchParams();const key=params.toString();
 const filters=useMemo(()=>parseFilters(new URLSearchParams(key),defaultRange),[key,defaultRange]);
 const [search,setSearch]=useState(params.get('q')||'');
 const patch=useCallback((values:Partial<LogFilters>)=>setParams(old=>{const next=new URLSearchParams(old);for(const [name,value] of Object.entries(values)){if(value===undefined||value==='')next.delete(name);else next.set(name,String(value));}next.delete('cursor');return next;},{replace:true}),[setParams]);
 useEffect(()=>{setSearch(filters.q||'');},[filters.q]);
 useEffect(()=>{if(search===(filters.q||''))return;const timeout=setTimeout(()=>patch({q:search.trim().slice(0,200)}),300);return()=>clearTimeout(timeout);},[search,filters.q,patch]);
 const range=(value:DateRange)=>patch({range:value,from:undefined,to:undefined});
 const reset=()=>{setSearch('');patch({range:'all',from:undefined,to:undefined,employee_id:undefined,field_id:undefined,activity_id:undefined,fertilizer_id:undefined,tag_id:undefined,q:undefined,direction:'desc'});};
 return {filters,patch,range,reset,search,setSearch};
}
export type FilterState=ReturnType<typeof useFilters>;
