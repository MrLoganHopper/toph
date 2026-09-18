import {afterEach,describe,it,expect,vi} from 'vitest';
import {supportedMime,downsamplePeaks} from '../src/features/worker/audio';
afterEach(()=>vi.unstubAllGlobals());
describe('audio container feature detection',()=>{
 it('chooses WebM only when the browser supports it',()=>{vi.stubGlobal('MediaRecorder',{isTypeSupported:(t:string)=>t.startsWith('audio/webm')});expect(supportedMime()).toBe('audio/webm;codecs=opus');});
 it('supports MP4-only browsers',()=>{vi.stubGlobal('MediaRecorder',{isTypeSupported:(t:string)=>t==='audio/mp4'});expect(supportedMime()).toBe('audio/mp4');});
 it('gives a visible error if recording is unavailable',()=>{vi.stubGlobal('MediaRecorder',undefined);expect(supportedMime).toThrow('cannot record audio');});
 it('rejects unsupported recording formats',()=>{vi.stubGlobal('MediaRecorder',{isTypeSupported:()=>false});expect(supportedMime).toThrow('no supported');});
});
describe('waveform metadata',()=>{
 it('allows missing waveforms',()=>expect(downsamplePeaks([])).toEqual([]));
 it('bounds every number and discards non-finite amplitudes',()=>expect(downsamplePeaks([NaN,Infinity,-1,0.4,2],5)).toEqual([0,0,0,0.4,1]));
 it('keeps the peak from each segment',()=>expect(downsamplePeaks([0,0.8,0.2,0.5],2)).toEqual([0.8,0.5]));
 it('downsamples a long recording into at most 256 peaks',()=>expect(downsamplePeaks(Array(10000).fill(0.2))).toHaveLength(256));
 it.each([0,-1,513,1.5])('rejects invalid target %s',target=>expect(()=>downsamplePeaks([0.1],target)).toThrow());
});
