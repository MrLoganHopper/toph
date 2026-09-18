import { lazy,Suspense,useState,useEffect } from 'react';
import { Link,useSearchParams } from 'react-router-dom';
import { Map as MapIcon,ChartNoAxesCombined,AudioLines,X,Expand } from 'lucide-react';
import { useFarm } from '../auth/Auth';
import { useGeometry,useLogs } from '../logs/queries';
import { useFilters } from '../logs/filters';
import { FiltersBar } from '../logs/FiltersBar';
import { LogCards } from '../logs/LogCards';
import { LogDialog } from '../logs/LogDetailView';
import { Busy,Button,Empty,ErrorBox,Modal } from '../../components/ui';
const FieldMap = lazy(() => import('./FieldMap'));
export default function MapPage({ welcome = false }: { welcome?: boolean }) {
  const { data,farmId } = useFarm(); const geo = useGeometry(); const [params,setParams] = useSearchParams();
  const field = params.get('field'); const [ready,setReady] = useState(false),[fullscreen,setFullscreen] = useState(false);
  const select = (id: string | null) => setParams(old => { const next = new URLSearchParams(old); if (id) next.set('field',id); else next.delete('field'); return next; });
  const [slitComplete,setSlitComplete] = useState(false);
  useEffect(() => { const timer = setTimeout(() => setSlitComplete(true),window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 900); return () => clearTimeout(timer); },[]);
  const open = slitComplete && (ready || !!geo.error);
  const root = `/admin/${farmId}`;
  return <div className={`map-page ${welcome ? 'welcome-page' : ''}`}><div className={`map-frame ${welcome ? `welcome-frame ${open ? 'is-open' : 'is-loading'}` : ''}`}>
    <div className="map-reveal">{geo.isPending ? <Busy label="Loading farm boundaries..."/> : geo.error ? <ErrorBox error={geo.error} retry={() => { geo.refetch(); }}/> : <Suspense fallback={<Busy label="Loading map renderer..."/>}><FieldMap data={geo.data} selectedId={field} onReady={() => setReady(true)} onSelect={welcome ? undefined : id => select(id)}/></Suspense>}</div>
    {welcome && <div className={`welcome-overlay ${open ? 'shown' : ''}`}><div className="welcome-links"><Link to={`${root}/dashboard`}><ChartNoAxesCombined size={15}/>Dashboard</Link><Link to={`${root}/logs`}><AudioLines size={15}/>Activity Monitor</Link><Link to={`${root}/map`}><MapIcon size={15}/>Map</Link></div><h1>Welcome Back</h1></div>}
    {!welcome && <Button className="map-expand-button" onClick={() => setFullscreen(true)}><Expand size={16}/>Expand</Button>}
  </div>{!welcome && <div className="map-field-controls"><label className="form-field">Select a field<select value={field || ''} onChange={e => select(e.target.value || null)}><option value="">All fields</option>{data.fields.map(f => <option value={f.id} key={f.id}>{f.name}</option>)}</select></label>{field && <Button onClick={() => select(null)}><X size={16}/>Close field logs</Button>}<span className="muted small">Select a field boundary to see its latest ten reports.</span></div>}
    {!welcome && field && <FieldLogs key={field} fieldId={field} fieldName={data.fields.find(f => f.id === field)?.name || 'Selected field'}/>}
    {fullscreen && geo.data && <Modal title="Farm map" close={() => setFullscreen(false)} wide><Suspense fallback={<Busy/>}><FieldMap data={geo.data} selectedId={field} onSelect={id => select(id)} className="expanded-field-map"/></Suspense></Modal>}
  </div>;
}
function FieldLogs({fieldId,fieldName}: {fieldId:string;fieldName:string}) {
  const state = useFilters('all'); const query = useLogs({...state.filters,field_id:fieldId,direction:state.filters.direction || 'desc'},10);
  const [opened,setOpened] = useState<string | null>(null);
  return <section className="field-logs route-enter"><FiltersBar state={state} title={`${fieldName} Logs`} total={query.data?.pages[0].total_matching} hideField/>{query.isPending ? <Busy/> : query.error ? <ErrorBox error={query.error} retry={() => { query.refetch(); }}/> : query.data.pages[0].items.length ? <><LogCards items={query.data.pages[0].items} open={setOpened}/><p className="muted small">Showing up to 10 matching reports for {fieldName}.</p></> : <Empty title="No matching field reports">Try a different date range.</Empty>}{opened && <LogDialog id={opened} close={() => setOpened(null)}/>}</section>;
}
