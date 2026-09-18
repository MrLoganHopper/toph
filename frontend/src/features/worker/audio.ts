export function supportedMime(){
 if(typeof MediaRecorder==='undefined')throw new Error('This browser cannot record audio. Use current Safari, Chrome, or Edge.');
 const candidates=['audio/webm;codecs=opus','audio/mp4;codecs=mp4a.40.2','audio/mp4','audio/webm','audio/ogg;codecs=opus'];
 const supported=candidates.find(type=>MediaRecorder.isTypeSupported(type));
 if(!supported)throw new Error('This browser has no supported audio recording format.');
 return supported;
}
export function downsamplePeaks(values:number[],target=256):number[]{
 if(!Number.isInteger(target)||target<1||target>512)throw new Error('Waveform target must be between 1 and 512.');
 if(!values.length)return [];
 const result:number[]=[];const length=Math.min(target,values.length);
 for(let i=0;i<length;i++){const start=Math.floor(i*values.length/length),end=Math.max(start+1,Math.floor((i+1)*values.length/length));let max=0;for(let j=start;j<end;j++){const value=values[j];if(Number.isFinite(value))max=Math.max(max,Math.min(1,Math.max(0,value)));}result.push(max);}return result;
}
