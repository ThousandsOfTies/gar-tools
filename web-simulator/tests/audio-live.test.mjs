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
  socket.receive({toolCall:{functionCalls:[call]}});await settle();
  assert.equal(count,1);assert.equal(socket.sent.filter(value=>value.toolResponse).length,1,'Completed IDs must not generate another result-triggered reply');
  client.sendAudio(new Uint8Array(3200));assert.equal(socket.sent.at(-1).realtimeInput.audio.mimeType,'audio/pcm;rate=16000');
  client.stop();
});

test('parallel results return once together, retaining IDs and individual failures',async()=>{
  let finish;const executed=[];
  const {client,socket}=await fixture(call=>{
    executed.push(call.id);
    if(call.id==='slow')return new Promise(resolve=>{finish=resolve;});
    throw new Error('PRIVATE_TOOL_ERROR');
  });
  const slow={id:'slow',name:'move_body',args:{mode:'lie'}},fast={id:'fast',name:'move_body',args:{mode:'stand'}};
  socket.receive({toolCall:{functionCalls:[slow,fast,slow]}});await settle();
  assert.equal(socket.sent.filter(value=>value.toolResponse).length,0);
  finish({status:'completed'});await settle();
  const replies=socket.sent.filter(value=>value.toolResponse);
  assert.equal(replies.length,1);
  assert.deepEqual(executed,['slow','fast']);
  assert.deepEqual(replies[0].toolResponse.functionResponses.map(value=>value.id),['slow','fast']);
  assert.equal(replies[0].toolResponse.functionResponses[0].response.result.status,'completed');
  assert.ok(replies[0].toolResponse.functionResponses[1].response.error);
  assert.ok(!JSON.stringify(replies).includes('PRIVATE_TOOL_ERROR'));client.stop();
});

test('cancelling one pending call releases the other result without waiting for its work',async()=>{
  let finish;
  const {client,socket}=await fixture(call=>call.id==='cancelled'?new Promise(resolve=>{finish=resolve;}):Promise.resolve({status:'ok'}));
  socket.receive({toolCall:{functionCalls:[{id:'cancelled',name:'move_body'},{id:'remaining',name:'move_body'}]}});await settle();
  socket.receive({toolCallCancellation:{ids:['cancelled']}});await settle();
  assert.deepEqual(socket.sent.filter(value=>value.toolResponse)[0].toolResponse.functionResponses.map(value=>value.id),['remaining']);
  finish({status:'completed'});await settle();
  assert.equal(socket.sent.filter(value=>value.toolResponse).length,1);client.stop();
});

test('reconnect discards a pending old batch and accepts a fresh request once',async()=>{
  let finish;
  const {client,socket}=await fixture(()=>new Promise(resolve=>{finish=resolve;}));
  socket.receive({toolCall:{functionCalls:[{id:'old',name:'move_body'}]}});await settle();client.stop();
  const next=new Socket();client.factory=()=>next;client.onTool=async()=>({status:'fresh'});
  const ready=client.connect({apiKey:'test',model:'gemini-3.8-live',voice:'Puck',instruction:'Test',tools:[{name:'move_body',behavior:'BLOCKING'}]});
  next.onopen();next.receive({setupComplete:{}});await ready;
  finish({status:'stale'});next.receive({toolCall:{functionCalls:[{id:'old',name:'move_body'}]}});await settle();
  assert.equal(socket.sent.some(value=>value.toolResponse),false);
  assert.equal(next.sent.filter(value=>value.toolResponse).length,1);
  assert.equal(next.sent.at(-1).toolResponse.functionResponses[0].response.result.status,'fresh');client.stop();
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

test('ephemeral tokens use the constrained Live endpoint and remain out of errors',async()=>{
  let url;const socket=new Socket(),client=new GeminiLive({socketFactory:value=>{url=value;return socket;}});
  const ready=client.connect({ephemeralToken:'auth_tokens/test-only',apiVersion:'v1alpha',model:'gemini-3.8-live',voice:'Puck',instruction:'Test'});
  assert.equal(new URL(url).pathname,'/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained');
  assert.equal(new URL(url).searchParams.get('access_token'),'auth_tokens/test-only');
  assert.equal(new URL(url).searchParams.has('key'),false);
  socket.onopen();socket.receive({setupComplete:{}});await ready;client.stop();
  assert.throws(()=>new GeminiLive().connect({apiKey:'one',ephemeralToken:'auth_tokens/two'}),/exactly one/);
});
