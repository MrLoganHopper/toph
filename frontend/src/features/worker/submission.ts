import {api} from '../../api/client';
import type {LogDetail,RecordingReceipt,UploadAuthorization} from '../../api/types';
import {type Draft,saveDraft,deleteDraft} from './drafts';
export type SaveStage='saving'|'uploading'|'generating'|'completed';
/** Retries reuse the same client submission ID, immutable metadata and confirmed recording. */
export async function submitDraft(path:string,draft:Draft,onStage:(stage:SaveStage)=>void,onWarning?:(message:string)=>void):Promise<LogDetail>{
 if(draft.transcription_incomplete||!draft.transcript.some(t=>t.speaker==='worker'&&t.text.trim()))throw new Error('Review and confirm the worker transcript before submitting. Your local audio is retained.');
 if(!draft.blob.size||draft.blob.size>26214400)throw new Error('The recording must contain audio and be at most 25 MiB.');
 onStage('saving');
 let receipt:RecordingReceipt;
 if(draft.recording_id){receipt=await api<RecordingReceipt>(`${path}/recordings/${draft.recording_id}`);}
 else{receipt=await api<RecordingReceipt>(`${path}/recordings`,{method:'POST',body:{client_submission_id:draft.id,content_type:draft.content_type,size_bytes:draft.blob.size,duration_ms:draft.duration_ms,recorded_at:draft.recorded_at,interview_version:draft.interview_version,transcript:draft.transcript,waveform_peaks:draft.waveform_peaks}});draft.recording_id=receipt.id;await saveDraft(draft);}
 if(!receipt.linked_log_id&&!receipt.uploaded_at){
  onStage('uploading');const auth=await api<UploadAuthorization>(`${path}/recordings/${receipt.id}/upload-url`,{method:'POST'});
  // Only S3 receives bytes. Never send the application's session cookie to storage.
  const form=new FormData();Object.entries(auth.fields).forEach(([key,value])=>form.append(key,value));form.append('file',draft.blob,'recording.'+({ 'audio/webm':'webm','audio/mp4':'m4a','audio/ogg':'ogg'}[draft.content_type]||'audio'));
  const upload=await fetch(auth.url,{method:auth.method,body:form,credentials:'omit',signal:AbortSignal.timeout(120000)});
  if(!upload.ok)throw new Error('Audio upload failed. Your recording is still on this device. Check the connection and retry.');
  receipt=await api<RecordingReceipt>(`${path}/recordings/${receipt.id}/complete`,{method:'POST'});
 }
 onStage('generating');
 // Always POST with the same explicit shift, even on recovery, so conflicting retries cannot be silently accepted.
 const report=await api<LogDetail>(`${path}/logs`,{method:'POST',body:{recording_id:receipt.id,shift_id:draft.shift_id},signal:AbortSignal.timeout(65000)});
 try{await deleteDraft(draft.id);}catch{onWarning?.('Your report is saved on the server. This browser could not clear its local audio draft. Clear this site’s stored data before sharing the device.');}
 onStage('completed');return report;
}
