import test from 'node:test';
import assert from 'node:assert/strict';
import {GeminiLive} from '../components/gemini-live.mjs';
import {pcm16,samples16,base64,unbase64} from '../components/audio-pcm.mjs';
class Socket{
  constructor(){this.readyState=1;this.sent=[];}
  send(text){this.sent.push(JSON.parse(text));}
  close(){this.closed=true;}
  receive(message){this.onmessage?.({data:JSON.stringify(message)});}
}
async function fixture(onTool){
  const socket=new Socket(),client=new GeminiLive({socketFactory:()=>socket,onTool});
  const ready=client.connect({apiKey:'fake-test-key',model:'gemini-3.8-live',voice:'Puck',instruction:'Test',tools:[{name:'move_body'}]});
  socket.onopen();socket.receive({setupComplete:{}});await ready;return {socket,client};
}
const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
test('PCM conversion is signed little endian, bounded and round trips base64',()=>{
  const bytes=pcm16(new Float32Array([-2,-.5,0,.5,2]),16000);
  assert.deepEqual([...samples16(bytes)],[-1,-.5,0,16383/32768,32767/32768]);
  assert.deepEqual(unbase64(base64(bytes)),bytes);assert.throws(()=>samples16(new Uint8Array(3)),/Incomplete/);
  assert.equal(pcm16(new Float32Array(4800),48000).length,3200);
});
test('audio streams independently of a pending tool, duplicate calls execute once',async()=>{
  let finish,count=0;const {client,socket}=await fixture(()=>{count++;return new Promise(resolve=>{finish=resolve;});});
  const audio=[];client.addEventListener('audio',event=>audio.push(event.detail));
  const call={id:'body-1',name:'move_body',args:{mode:'lie'}};
  socket.receive({toolCall:{functionCalls:[call]}});await settle();
  socket.receive({toolCall:{functionCalls:[call]},serverContent:{modelTurn:{parts:[{inlineData:{mimeType:'audio/pcm;rate=24000',data:'AAA='}}]}}});await settle();
  assert.equal(count,1);assert.equal(audio.length,1);assert.equal(socket.sent.some(v=>v.toolResponse),false);
  finish({status:'completed'});await settle();assert.equal(socket.sent.at(-1).toolResponse.functionResponses[0].id,'body-1');
  client.sendAudio(new Uint8Array(3200));assert.equal(socket.sent.at(-1).realtimeInput.audio.mimeType,'audio/pcm;rate=16000');
  client.stop();
});
test('cancellation and stopped sessions cannot send late tool results or audio',async()=>{
  let finish;const {client,socket}=await fixture(()=>new Promise(resolve=>{finish=resolve;}));
  const call={id:'cancel-1',name:'move_body',args:{mode:'forward'}};
  let cancelled=0,audio=0;client.addEventListener('cancel',()=>cancelled++);client.addEventListener('audio',()=>audio++);
  socket.receive({toolCall:{functionCalls:[call]}});await settle();
  socket.receive({toolCallCancellation:{ids:[call.id]},serverContent:{interrupted:true,modelTurn:{parts:[{inlineData:{data:'AAA='}}]}}});
  finish({status:'completed'});await settle();assert.equal(cancelled,1);assert.equal(audio,0);assert.equal(socket.sent.some(value=>value.toolResponse),false);
  client.stop();assert.equal(client.sendAudio(new Uint8Array(10)),false);
});
test('two protocol instances keep connection state independent and sanitize errors',async()=>{
  const first=await fixture(async()=>({})),second=await fixture(async()=>({}));
  let error;first.client.addEventListener('error',event=>{error=event.detail;});
  first.socket.receive({error:{message:'fake-test-key must never be displayed'}});await settle();
  assert.ok(!error.includes('fake-test-key'));assert.equal(first.client.ready,false);assert.equal(second.client.ready,true);second.client.stop();
});
test('socket constructor errors cannot expose a credential-bearing URL',()=>{
  const client=new GeminiLive({socketFactory:url=>{throw new Error(url);}});
  assert.throws(()=>client.connect({apiKey:'never-display-this',model:'test-model',voice:'Puck',instruction:'test'}),error=>!error.message.includes('never-display-this')&&error.message.includes('Cannot open'));
});
