import {useState} from 'react';
import {useFilters} from './filters';
import {useLogs} from './queries';
import {FiltersBar,SearchBox} from './FiltersBar';
import {LogCards} from './LogCards';
import {LogDialog} from './LogDetailView';
import {Busy,Button,Empty,ErrorBox} from '../../components/ui';
export default function LogsPage(){const state=useFilters();const query=useLogs(state.filters);const [opened,setOpened]=useState<string|null>(null);const items=query.data?.pages.flatMap(p=>p.items)||[];const unique=[...new Map(items.map(item=>[item.id,item])).values()];return <><header className="page-heading"><div><h1>Activity Logs</h1><p>A more in-depth look into your employee logs</p></div><SearchBox state={state}/></header><FiltersBar state={state} title="Employee Logs" total={query.data?.pages[0].total_matching}/>{query.isPending?<Busy/>:query.error?<ErrorBox error={query.error} retry={()=>{void query.refetch();}}/>:unique.length?<LogCards items={unique} open={setOpened}/>:<Empty title="No matching reports">Change the filters or create a worker report.</Empty>}{query.hasNextPage&&<Button className="load-more" disabled={query.isFetchingNextPage} onClick={()=>{void query.fetchNextPage();}}>{query.isFetchingNextPage?'Loading...':'Load more logs'}</Button>}{opened&&<LogDialog id={opened} close={()=>setOpened(null)}/>}</>;}
