export function pcm16(samples,sourceRate,targetRate=16000){
  if(!Number.isFinite(sourceRate)||sourceRate<8000||!Number.isFinite(targetRate)||targetRate<8000)throw new Error('Invalid PCM sample rate');
  const ratio=sourceRate/targetRate,count=Math.floor(samples.length/ratio),bytes=new Uint8Array(count*2),view=new DataView(bytes.buffer);
  for(let i=0;i<count;i++){const position=i*ratio,left=Math.floor(position),right=Math.min(left+1,samples.length-1);const value=Math.max(-1,Math.min(1,samples[left]+(samples[right]-samples[left])*(position-left)));view.setInt16(i*2,value<0?value*32768:value*32767,true);}
  return bytes;
}
export function base64(bytes){let value='';for(let i=0;i<bytes.length;i+=8192)value+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(value);}
export function unbase64(value){if(typeof value!=='string'||value.length>1048576)throw new Error('Invalid audio chunk');return Uint8Array.from(atob(value),c=>c.charCodeAt(0));}
export function samples16(bytes){if(bytes.byteLength%2)throw new Error('Incomplete PCM sample');const data=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),samples=new Float32Array(bytes.byteLength/2);for(let i=0;i<samples.length;i++)samples[i]=data.getInt16(i*2,true)/32768;return samples;}
