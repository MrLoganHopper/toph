import { useCallback,useEffect,useRef,useState } from 'react';
import { api } from '../../api/client';
import type { RealtimeSecret,Turn } from '../../api/types';
import { type Draft,saveDraft } from './drafts';
import { downsamplePeaks,supportedMime } from './audio';
export const QUESTIONS = ['What activity did you do?','What fertilizer did you use?','What field did you work on?','Tell me about the work.','Any problems or observations?'];
type Phase = 'ready'|'connecting'|'listening'|'speaking'|'finishing'|'review';
type UIState = {step:number;phase:'asking'|'confirming'|'confirmed'|'done';answer:string};
interface ProviderEvent {type:string;item_id?:string;response_id?:string;delta?:string;transcript?:string;name?:string;arguments?:string;call_id?:string;response?:{id:string;status?:string};error?:{code?:string;message?:string}}
interface LiveResources {pc:RTCPeerConnection;channel:RTCDataChannel;mic:MediaStream;context:AudioContext;recorder:MediaRecorder;output:HTMLAudioElement;destination:MediaStreamAudioDestinationNode;analyser:AnalyserNode;animation:number;timer:number;started:number;chunks:Blob[];peaks:number[];turns:Map<string,Turn>;offsets:Map<string,number>;pending:Set<string>;finishing:boolean;responseActive:boolean;queuedResponse:boolean;shiftId:string|null;interviewVersion:string;size:number;transcriptionFailed:boolean}
const sleep = (ms:number) => new Promise(resolve => setTimeout(resolve,ms));
export function useVoiceInterview({userId,farmId,path}:{userId:string;farmId:string;path:string}) {
  const [phase,setPhase] = useState<Phase>('ready'),[ui,setUi] = useState<UIState>({step:0,phase:'asking',answer:''}),[liveText,setLiveText] = useState(''),[speaker,setSpeaker] = useState<'worker'|'assistant'>('assistant'),[amplitude,setAmplitude] = useState(0),[elapsed,setElapsed] = useState(0),[error,setError] = useState<unknown>(),[draft,setDraft] = useState<Draft | null>(null);
  const resources = useRef<LiveResources | null>(null), finishRef = useRef<() => Promise<Draft | null>>(async () => null), starting = useRef(false), mounted = useRef(true);
  const cleanup = useCallback((r: LiveResources) => {
    cancelAnimationFrame(r.animation); clearInterval(r.timer); r.channel.close(); r.pc.close(); r.mic.getTracks().forEach(t => t.stop());
    r.output.pause(); r.output.srcObject = null; r.destination.stream.getTracks().forEach(t => t.stop()); r.context.close().catch(() => undefined);
    if (resources.current === r) resources.current = null; setAmplitude(0);
  },[]);
  const finish = useCallback(async (): Promise<Draft | null> => {
    const r = resources.current; if (!r || r.finishing) return null;
    r.finishing = true; setPhase('finishing');
    // Let final ASR messages arrive before freezing immutable recording metadata.
    const deadline = Date.now()+3000;
    r.mic.getTracks().forEach(track=>{track.enabled=false;});
    if (r.channel.readyState === 'open') {
      try{r.channel.send(JSON.stringify({type:'input_audio_buffer.commit'}));
      if (r.responseActive) r.channel.send(JSON.stringify({type:'response.cancel'}));}
      catch{r.transcriptionFailed=true;}
    }else{r.transcriptionFailed=true;}
    await sleep(400);
    while (r.pending.size > 0 && Date.now() < deadline) await sleep(100);
    const duration = Math.max(1,Math.min(600000,Date.now()-r.started));
    await new Promise<void>(resolve => {
      if (r.recorder.state === 'inactive') { resolve(); return; }
      const timer=window.setTimeout(resolve,4000); r.recorder.addEventListener('stop',() => {clearTimeout(timer);resolve();},{once:true}); r.recorder.stop();
    });
    const contentType = r.recorder.mimeType.split(';')[0], blob = new Blob(r.chunks,{type:contentType});
    const turns = [...r.turns.values()].filter(t => t.text.trim()).sort((a,b) => a.offset_ms-b.offset_ms).map(t => ({...t,offset_ms:Math.min(duration,t.offset_ms)}));
    const completed: Draft = {id:crypto.randomUUID(),user_id:userId,farm_id:farmId,blob,content_type:contentType,duration_ms:duration,recorded_at:new Date(r.started).toISOString(),transcript:turns,waveform_peaks:downsamplePeaks(r.peaks),interview_version:r.interviewVersion,shift_id:r.shiftId,transcription_incomplete:r.transcriptionFailed||r.pending.size>0||!turns.some(t=>t.speaker==='worker')};
    cleanup(r); setDraft(completed); setPhase('review');
    let persisted=false;
    try { await saveDraft(completed); persisted=true; } catch { setError(new Error('This browser could not save the audio to device storage. Keep this page open and use Save audio backup before leaving.')); }
    if (completed.transcription_incomplete) setError(new Error(persisted?'Some speech was not transcribed. Your audio draft is saved on this device. Review the transcript before submitting.':'Some speech was not transcribed, and device storage is unavailable. Keep this page open and save an audio backup before reviewing.'));
    return completed;
  },[cleanup,farmId,userId]);
  finishRef.current = finish;
  const sendText = useCallback((text: string) => {
    const r = resources.current; if (!r || r.channel.readyState !== 'open' || r.finishing) return;
    const id = crypto.randomUUID();
    r.turns.set(id,{speaker:'worker',text:`[On-screen response] ${text}`,offset_ms:Math.min(600000,Date.now()-r.started)});
    r.channel.send(JSON.stringify({type:'conversation.item.create',item:{type:'message',role:'user',content:[{type:'input_text',text}]}}));
    if (r.responseActive) r.queuedResponse = true;
    else r.channel.send(JSON.stringify({type:'response.create'}));
  },[]);
  const start = useCallback(async (shiftId: string | null) => {
    if (starting.current || resources.current) return;
    starting.current = true; setError(undefined); setPhase('connecting'); setLiveText(''); setUi({step:0,phase:'asking',answer:''}); setDraft(null); setElapsed(0);
    let mic: MediaStream | undefined, context: AudioContext | undefined;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires HTTPS or localhost.');
      const mime = supportedMime();
      context = new AudioContext(); await context.resume();
      mic = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
      if(!mounted.current)throw new Error('Recording screen closed.');
      const credential = await api<RealtimeSecret>(`${path}/realtime/client-secret`,{method:'POST',body:{shift_id:shiftId}});
      if(!mounted.current)throw new Error('Recording screen closed.');
      const pc = new RTCPeerConnection(), channel = pc.createDataChannel('oai-events'), destination = context.createMediaStreamDestination(), analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      context.createMediaStreamSource(mic).connect(destination);
      context.createMediaStreamSource(destination.stream).connect(analyser);
      const output = new Audio(); output.autoplay = true;
      const recorder = new MediaRecorder(destination.stream,{mimeType:mime,audioBitsPerSecond:128000});
      const r: LiveResources = {pc,channel,mic,context,recorder,output,destination,analyser,animation:0,timer:0,started:Date.now(),chunks:[],peaks:[],turns:new Map(),offsets:new Map(),pending:new Set(),finishing:false,responseActive:false,queuedResponse:false,shiftId,interviewVersion:credential.interview_version,size:0,transcriptionFailed:false};
      resources.current = r;
      const receive = (message: MessageEvent) => {
        let event: ProviderEvent; try { event = JSON.parse(message.data as string) as ProviderEvent; } catch { return; }
        const offset = Math.max(0,Math.min(600000,Date.now()-r.started));
        const id = event.item_id || event.response_id || 'assistant-current';
        if (event.type === 'input_audio_buffer.speech_started') { r.offsets.set(id,offset); if(event.item_id)r.pending.add(event.item_id); setSpeaker('worker'); setLiveText(''); if (!r.finishing) setPhase('listening'); }
        if (event.type === 'input_audio_buffer.committed' && event.item_id) r.pending.add(event.item_id);
        if (event.type === 'conversation.item.input_audio_transcription.delta') { setSpeaker('worker'); setLiveText(old => old+(event.delta || '')); }
        if (event.type === 'conversation.item.input_audio_transcription.completed') {
          r.pending.delete(id);
          if (event.transcript?.trim()) r.turns.set(id,{speaker:'worker',text:event.transcript.trim(),offset_ms:r.offsets.get(id) ?? offset});
          setSpeaker('worker'); setLiveText(event.transcript || '');
        }
        if (event.type === 'conversation.item.input_audio_transcription.failed') { r.transcriptionFailed=true; r.pending.delete(id); setError(new Error('Speech transcription failed. Finish to preserve your local audio draft.')); }
        if (event.type === 'response.created') { r.responseActive = true; r.offsets.set(event.response?.id || id,offset); setSpeaker('assistant'); setLiveText(''); }
        if (['response.output_audio_transcript.delta','response.audio_transcript.delta'].includes(event.type)) { setSpeaker('assistant'); setLiveText(old => old+(event.delta || '')); }
        if (['response.output_audio_transcript.done','response.audio_transcript.done'].includes(event.type) && event.transcript?.trim()) {
          r.turns.set('assistant:'+id,{speaker:'assistant',text:event.transcript.trim(),offset_ms:r.offsets.get(event.response_id || id) ?? offset}); setSpeaker('assistant'); setLiveText(event.transcript);
        }
        if (event.type === 'output_audio_buffer.started' && !r.finishing) setPhase('speaking');
        if (event.type === 'output_audio_buffer.stopped' && !r.finishing) setPhase('listening');
        if (event.type === 'response.function_call_arguments.done' && event.name === 'set_interview_state') {
          try {
            const value = JSON.parse(event.arguments || '{}') as UIState;
            if (Number.isInteger(value.step) && value.step >= 0 && value.step < 5 && ['asking','confirming','confirmed','done'].includes(value.phase) && typeof value.answer === 'string') setUi({...value,answer:value.answer.slice(0,240)});
            channel.send(JSON.stringify({type:'conversation.item.create',item:{type:'function_call_output',call_id:event.call_id,output:'{"updated":true}'}}));
            r.queuedResponse = true;
          } catch { setError(new Error('The assistant sent an invalid display update. You can continue speaking or finish your recording.')); }
        }
        if (event.type === 'response.done') {
          r.responseActive = false;
          if (r.queuedResponse && !r.finishing && channel.readyState === 'open') { r.queuedResponse = false; channel.send(JSON.stringify({type:'response.create'})); }
        }
        if (event.type === 'error' && !['input_audio_buffer_commit_empty','response_cancel_not_active','conversation_already_has_active_response'].includes(event.error?.code || '')) setError(new Error('The voice service reported an error. Finish to preserve the conversation, then retry.'));
      };
      channel.addEventListener('message',receive);
      channel.addEventListener('close',() => { if (!r.finishing) {r.transcriptionFailed=true;setError(new Error('Voice connection closed. Finish and preserve this recording before starting another.'));} });
      pc.onconnectionstatechange = () => { if (['failed','disconnected'].includes(pc.connectionState) && !r.finishing) {r.transcriptionFailed=true;setError(new Error('The voice connection was interrupted. Keep this page open; finish to preserve your audio.'));} };
      pc.ontrack = event => {
        const remote = event.streams[0] || new MediaStream([event.track]);
        // Remote speech has one speaker output path and one recording path.
        output.srcObject = remote; output.play().catch(() => setError(new Error('Tap Resume assistant audio to allow playback.')));
        r.context.createMediaStreamSource(remote).connect(destination);
      };
      pc.addTrack(mic.getAudioTracks()[0],mic);
      recorder.ondataavailable = event => { if (event.data.size) { r.chunks.push(event.data); r.size += event.data.size; if (r.size >= 24*1024*1024 && !r.finishing) void finishRef.current(); } };
      recorder.onerror = () => setError(new Error('The browser recorder reported an error. Finish to preserve the available audio.'));
      recorder.start(1000);
      const values = new Uint8Array(analyser.fftSize); let lastSample = 0;
      const animate = (time: number) => {
        if (time-lastSample > 50) { analyser.getByteTimeDomainData(values); const rms = Math.sqrt(values.reduce((sum,value) => sum+((value-128)/128)**2,0)/values.length); const level = Math.min(1,rms*5); setAmplitude(level); r.peaks.push(level); lastSample = time; }
        r.animation = requestAnimationFrame(animate);
      };
      r.animation = requestAnimationFrame(animate);
      r.timer = window.setInterval(() => { setElapsed(Math.floor((Date.now()-r.started)/1000)); if (Date.now()-r.started >= 595000 && !r.finishing) void finishRef.current(); },1000);
      const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
      const response = await fetch('https://api.openai.com/v1/realtime/calls',{method:'POST',body:offer.sdp,headers:{Authorization:`Bearer ${credential.client_secret}`,'Content-Type':'application/sdp'},signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw new Error('The voice provider rejected the connection. Check enabled models and the server configuration.');
      await pc.setRemoteDescription({type:'answer',sdp:await response.text()});
      await new Promise<void>((resolve,reject) => { if (channel.readyState === 'open') { resolve(); return; } const timer = setTimeout(() => reject(new Error('Voice connection timed out.')),15000); channel.addEventListener('open',() => { clearTimeout(timer); resolve(); },{once:true}); });
      if (!r.finishing) { setPhase('listening'); channel.send(JSON.stringify({type:'response.create'})); }
    } catch(e) {
      if (resources.current && !resources.current.finishing) await finishRef.current();
      else { mic?.getTracks().forEach(t => t.stop()); await context?.close().catch(() => undefined); setPhase('ready'); }
      setError(e instanceof DOMException && e.name === 'NotAllowedError' ? new Error('Microphone permission was denied. Allow the microphone for this site in your browser settings and try again.') : e);
    } finally { starting.current = false; }
  },[path]);
  useEffect(() => {
    mounted.current=true;
    const warn = (event: BeforeUnloadEvent) => { if (resources.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload',warn);
    return () => { mounted.current=false; window.removeEventListener('beforeunload',warn); const r = resources.current; if (r) { r.finishing = true; if (r.recorder.state !== 'inactive') r.recorder.stop(); cleanup(r); } };
  },[cleanup]);
  const resumeAudio = () => { const r = resources.current; if (r) { r.context.resume().catch(setError); r.output.play().catch(setError); } };
  return {phase,ui,liveText,speaker,amplitude,elapsed,error,draft,start,finish,sendText,resumeAudio,active:['connecting','listening','speaking','finishing'].includes(phase)};
}
