import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {api} from '../src/api/client';
import {saveDraft,deleteDraft,type Draft} from '../src/features/worker/drafts';
import {submitDraft} from '../src/features/worker/submission';
vi.mock('../src/api/client',()=>({api:vi.fn()}));
vi.mock('../src/features/worker/drafts',()=>({saveDraft:vi.fn(),deleteDraft:vi.fn()}));
const apiMock=vi.mocked(api),saveMock=vi.mocked(saveDraft),deleteMock=vi.mocked(deleteDraft);
const receipt={id:'recording-1',recorded_at:'2026-09-17T13:00:00Z',uploaded_at:null,linked_log_id:null};
function draft():Draft{return {id:'submission-1',user_id:'worker-1',farm_id:'farm-1',blob:new Blob(['audio-bytes'],{type:'audio/webm'}),content_type:'audio/webm',duration_ms:5000,recorded_at:'2026-09-17T13:00:00Z',transcript:[{speaker:'worker',text:'Watered field A, no fertilizer.',offset_ms:500}],waveform_peaks:[0.1,0.2],interview_version:'interview-v1',shift_id:null};}
const upload={url:'https://private-storage.example/upload',method:'POST',fields:{key:'farm/recording','Content-Type':'audio/webm'},expires_at:'2026-09-17T13:10:00Z',max_size_bytes:26214400};
beforeEach(()=>{vi.resetAllMocks();saveMock.mockResolvedValue(undefined);deleteMock.mockResolvedValue(undefined);vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(null,{status:204})));});
afterEach(()=>vi.unstubAllGlobals());
describe('durable recording submission',()=>{
 it('posts metadata, uploads directly without application cookies, confirms storage, then generates',async()=>{
  apiMock.mockResolvedValueOnce(receipt).mockResolvedValueOnce(upload).mockResolvedValueOnce({...receipt,uploaded_at:'now'}).mockResolvedValueOnce({id:'log-1'});
  const stages:string[]=[];const d=draft();const result=await submitDraft('/farms/farm-1',d,s=>stages.push(s));
  expect(result.id).toBe('log-1');expect(stages).toEqual(['saving','uploading','generating','completed']);expect(saveMock).toHaveBeenCalledWith(expect.objectContaining({recording_id:'recording-1'}));
  expect(fetch).toHaveBeenCalledWith(upload.url,expect.objectContaining({credentials:'omit',method:'POST',body:expect.any(FormData)}));
  expect(apiMock.mock.calls[0][1]?.body).not.toHaveProperty('blob');
  expect(apiMock.mock.calls[3][1]?.body).toEqual({recording_id:'recording-1',shift_id:null});expect(deleteMock).toHaveBeenCalledWith('submission-1');
 });
 it('reuses a confirmed recording and never reuploads it',async()=>{const d={...draft(),recording_id:'recording-1'};apiMock.mockResolvedValueOnce({...receipt,uploaded_at:'now'}).mockResolvedValueOnce({id:'log-1'});await submitDraft('/farms/farm-1',d,()=>{});expect(apiMock.mock.calls[0][0]).toContain('/recordings/recording-1');expect(fetch).not.toHaveBeenCalled();expect(saveMock).not.toHaveBeenCalled();expect(deleteMock).toHaveBeenCalledOnce();});
 it('checks explicit shift consistency even when a report already exists',async()=>{apiMock.mockResolvedValueOnce({...receipt,uploaded_at:'now',linked_log_id:'log-1'}).mockResolvedValueOnce({id:'log-1'});await submitDraft('/farms/farm-1',{...draft(),recording_id:'recording-1',shift_id:'shift-2'},()=>{});expect(apiMock.mock.calls[1]).toEqual([expect.stringContaining('/logs'),expect.objectContaining({method:'POST',body:{recording_id:'recording-1',shift_id:'shift-2'}})]);});
 it('retains the local draft on an extraction timeout',async()=>{apiMock.mockResolvedValueOnce({...receipt,uploaded_at:'now'}).mockRejectedValueOnce(new Error('Extraction timeout'));await expect(submitDraft('/farms/farm-1',{...draft(),recording_id:'recording-1'},()=>{})).rejects.toThrow('timeout');expect(deleteMock).not.toHaveBeenCalled();});
 it('retains metadata and audio after a failed upload',async()=>{apiMock.mockResolvedValueOnce(receipt).mockResolvedValueOnce(upload);vi.mocked(fetch).mockResolvedValueOnce(new Response(null,{status:403}));const d=draft();await expect(submitDraft('/farms/farm-1',d,()=>{})).rejects.toThrow('upload failed');expect(d.recording_id).toBe('recording-1');expect(deleteMock).not.toHaveBeenCalled();expect(apiMock).toHaveBeenCalledTimes(2);});
 it('prevents submission of unreviewed failed transcription',async()=>{await expect(submitDraft('/farms/farm-1',{...draft(),transcription_incomplete:true},()=>{})).rejects.toThrow('Review and confirm');expect(apiMock).not.toHaveBeenCalled();expect(deleteMock).not.toHaveBeenCalled();});
 it('never fabricates an absent worker transcript',async()=>{await expect(submitDraft('/farms/farm-1',{...draft(),transcript:[]},()=>{})).rejects.toThrow('Review and confirm');expect(apiMock).not.toHaveBeenCalled();});
 it('keeps confirmed server success when local cleanup fails',async()=>{apiMock.mockResolvedValueOnce({...receipt,uploaded_at:'now'}).mockResolvedValueOnce({id:'log-1'});deleteMock.mockRejectedValueOnce(new Error('Storage blocked'));const warning=vi.fn();const report=await submitDraft('/farms/farm-1',{...draft(),recording_id:'recording-1'},()=>{},warning);expect(report.id).toBe('log-1');expect(warning).toHaveBeenCalledWith(expect.stringContaining('saved on the server'));});
 it('rejects an empty recording before initializing server metadata',async()=>{await expect(submitDraft('/farms/farm-1',{...draft(),blob:new Blob([])},()=>{})).rejects.toThrow('must contain audio');expect(apiMock).not.toHaveBeenCalled();});
});
