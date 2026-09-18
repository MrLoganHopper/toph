import { lazy, Suspense, useRef, useState } from 'react';
import { Play, Star, Expand, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { AudioAuthorization,GeoCollection } from '../../api/types';
import { useFarm } from '../auth/Auth';
import { useLog } from './queries';
import { Busy,Button,Dropdown,ErrorBox,Modal,dateLabel,timeLabel,Empty } from '../../components/ui';
const FieldMap = lazy(() => import('../map/FieldMap'));
export function LogDetailView({ id }: { id: string }) {
  const { path,data,userId,farmId,role } = useFarm(); const query = useLog(id); const cache = useQueryClient();
  const audio = useRef<HTMLAudioElement>(null); const [audioUrl,setAudioUrl] = useState(''),[audioError,setAudioError] = useState<unknown>(),[audioBusy,setAudioBusy] = useState(false),[expandedMap,setExpandedMap] = useState(false),[progress,setProgress] = useState(0),[tagError,setTagError] = useState<unknown>();
  const resumeAt = useRef(0), autoPlay = useRef(false);
  if (query.isPending) return <Busy label="Opening report..."/>;
  if (query.error) return <ErrorBox error={query.error} retry={() => { query.refetch(); }}/>;
  const log = query.data;
  const geo: GeoCollection = {type:'FeatureCollection',features:log.field_geometry ? [{type:'Feature',id:log.field?.id,properties:{id:log.field?.id || '',name:log.field?.name || 'Field'},geometry:log.field_geometry}] : [],next_cursor:null,farm_bbox:null};
  const playback = async (renew = false) => {
    setAudioError(undefined); setAudioBusy(true);
    try {
      if (!audioUrl || renew) { resumeAt.current = audio.current?.currentTime || 0; autoPlay.current = true; const result = await api<AudioAuthorization>(`${path}/logs/${id}/audio-url`); setAudioUrl(result.url); }
      else await audio.current?.play();
    } catch(e) { setAudioError(e); } finally { setAudioBusy(false); }
  };
  const tag = async (tagId: string,remove = false) => {
    setTagError(undefined);
    try { await api(`${path}/logs/${id}/tags/${tagId}`,{method:remove ? 'DELETE' : 'PUT'}); await cache.invalidateQueries({queryKey:[userId,farmId]}); }
    catch(e) { setTagError(e); }
  };
  const peaks = log.recording.waveform_peaks;
  return <div className="log-detail"><section className="report-left"><div className="waveform" aria-label="Recording waveform, decorative" onClick={e => { if (audio.current?.duration) audio.current.currentTime = (e.clientX-e.currentTarget.getBoundingClientRect().left)/e.currentTarget.clientWidth*audio.current.duration; }}>
    {peaks?.length ? peaks.map((peak,index) => <span key={index} style={{height:`${Math.max(3,peak*88)}%`,opacity:index/peaks.length*100 <= progress ? 1 : .3}}/>) : <span className="muted">Waveform unavailable</span>}
  </div><Button className="full-width playback" disabled={audioBusy} onClick={() => { playback(); }}><Play size={16}/>{audioBusy ? 'Opening audio...' : 'Play Recording'}</Button>
    {audioUrl && <audio ref={audio} src={audioUrl} controls preload="metadata" className="audio-control" onLoadedMetadata={() => { if (audio.current) { audio.current.currentTime = Math.min(resumeAt.current,audio.current.duration || 0); if (autoPlay.current) { autoPlay.current = false; audio.current.play().catch(() => setAudioError(new Error('Press Play in the audio controls to start playback.'))); } } }} onTimeUpdate={() => setProgress((audio.current?.currentTime || 0)/(audio.current?.duration || 1)*100)} onError={() => setAudioError(new Error('Audio could not load or its access link expired. Renew playback and try again.'))}/>}
    {!!audioError && <ErrorBox error={audioError} retry={() => { playback(true); }}/>} 
    {role === 'admin' && <Dropdown className="tag-dropdown" label={<><Star size={17}/> Add Tag</>}>{data.tags.filter(t => !log.tags.some(v => v.id === t.id)).map(t => <Button key={t.id} onClick={() => { tag(t.id); }}>{t.name}</Button>)}{data.tags.length === 0 && <p className="muted small">Create tags in Settings.</p>}</Dropdown>}
    {!!tagError && <ErrorBox error={tagError}/>}<div className="tag-list">{log.tags.map(t => <span className="tag" key={t.id}>{t.name}{role === 'admin' && <button aria-label={`Remove ${t.name} tag`} onClick={() => { tag(t.id,true); }}><X size={12}/></button>}</span>)}</div>
    <h3>Summary</h3><p className="summary-text">{log.summary}</p><dl className="report-meta"><div><dt>Activity</dt><dd>{log.activity?.name || 'Not identified'}</dd></div><div><dt>Fertilizer</dt><dd>{log.fertilizer?.name || 'None identified'}</dd></div><div><dt>Recorded</dt><dd>{dateLabel(log.recorded_at,data.farm.timezone)}, {timeLabel(log.recorded_at,data.farm.timezone)}</dd></div><div><dt>Scheduled time</dt><dd>{log.scheduled_shift ? `${timeLabel(log.scheduled_shift.start_at,data.farm.timezone)} - ${timeLabel(log.scheduled_shift.end_at,data.farm.timezone)}` : 'No linked shift'}</dd></div></dl>
    <details className="transcript"><summary>Work details and transcript</summary><h4>Work details</h4><p>{log.answers.details || 'Not provided'}</p><h4>Problems or observations</h4><p>{log.answers.issues || 'Not provided'}</p>{log.recording.transcript.map((turn,i) => <p key={i}><strong>{turn.speaker === 'assistant' ? 'TOPH' : log.employee.name}</strong><br/>{turn.text}</p>)}</details>
  </section><section className="report-right">{log.field_geometry ? <><Suspense fallback={<Busy label="Loading map..."/>}><FieldMap data={geo} selectedId={log.field?.id}/></Suspense><Button className="full-width" onClick={() => setExpandedMap(true)}><Expand size={16}/> Expand Map</Button></> : <Empty title="Field not identified">This report has no single confirmed field boundary.</Empty>}</section>
    {expandedMap && <Modal title={log.field?.name || 'Field map'} close={() => setExpandedMap(false)} wide><Suspense fallback={<Busy/>}><FieldMap data={geo} selectedId={log.field?.id} className="expanded-field-map"/></Suspense></Modal>}
  </div>;
}
export function LogDialog({ id,close }: { id: string;close: () => void }) { return <Modal title="Employee report" close={close} wide><LogDetailView id={id}/></Modal>; }
