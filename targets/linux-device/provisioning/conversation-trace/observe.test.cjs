'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');

test('inspects one live session, records boundaries without payloads, and restores handlers',async()=>{
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'gar-trace-test-'));
  const module=path.join(directory,'fixture.cjs');
  fs.writeFileSync(module,`const {EventEmitter}=require('node:events');
class LiveSession{constructor(){this.started=true;this.closed=false;this.duplex=false;
 this.audio=new EventEmitter();this.audio.playing=false;
 this.client={ready:true,send(){return true;},emit(){}};}}
module.exports={LiveSession};`);
  const fixture=`const {LiveSession}=require(process.argv[1]);
global.fixture=new LiveSession();const {client,audio}=global.fixture;
const send=client.send,emit=client.emit;let n=0;
setInterval(()=>{if(++n>12)return;
 client.send({realtimeInput:{audio:{data:'PRIVATE_PCM'}}});
 client.emit('audio',{bytes:new Uint8Array(8)});
 client.emit('transcript',{role:'model',text:'PRIVATE_TEXT_REPEAT'});
 client.send({realtimeInput:{audioStreamEnd:true}});
 audio.playing=false;audio.emit('playback',false);
 client.emit('turn-end',{});
 client.emit('transcript',{role:'user',text:'PRIVATE_TEXT_REPEAT'});
},100);
setTimeout(()=>console.log(JSON.stringify({restored:client.send===send&&client.emit===emit,listeners:audio.listenerCount('playback')})),2200);`;
  const child=spawn(process.execPath,['--inspect=127.0.0.1:0','-e',fixture,module],{stdio:['ignore','pipe','pipe']});
  let output='';child.stdout.on('data',chunk=>output+=chunk);
  try{
    const endpoint=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Inspector did not start')),7000);let error='';
      child.stderr.on('data',chunk=>{error+=chunk;const m=error.match(/ws:\/\/127\.0\.0\.1:\d+\/[a-z0-9-]+/);if(m){clearTimeout(timer);resolve(m[0]);}});
    });
    const observer=spawn(process.execPath,[path.join(__dirname,'observe.cjs')],{stdio:['pipe','pipe','pipe']});
    let report='';observer.stdout.on('data',chunk=>report+=chunk);observer.stderr.resume();
    const traceFunction=function(durationMs){
      const session=this.find(value=>value.started&&!value.closed),client=session.client;
      const original=client.send;let messages=0;
      client.send=function(value){++messages;return original.call(this,value);};
      return new Promise(resolve=>setTimeout(()=>{
        client.send=original;
        resolve({ok:true,trace:{activeSessions:1,messages,restored:true}});
      },durationMs));
    };
    observer.stdin.end(JSON.stringify({url:endpoint,module,prototypeExport:'LiveSession',traceFunctionBase64:Buffer.from(traceFunction.toString()).toString('base64'),durationMs:1200,closeInspector:true}));
    const exit=await new Promise(resolve=>observer.once('close',resolve));
    assert.equal(exit,0);const result=JSON.parse(report);
    assert.equal(result.trace.activeSessions,1);
    assert.ok(result.trace.messages>=2);
    assert.ok(!report.includes('PRIVATE_TEXT_REPEAT'));assert.ok(!report.includes('PRIVATE_PCM'));
    await new Promise(resolve=>setTimeout(resolve,1200));
    assert.ok(output.includes('"restored":true'));assert.ok(output.includes('"listeners":0'));
    await assert.rejects(fetch(new URL('/json/list',endpoint.replace('ws:','http:')),{signal:AbortSignal.timeout(1000)}));
  }finally{
    child.kill();
    assert.ok(path.resolve(directory).startsWith(path.resolve(os.tmpdir())+path.sep+'gar-trace-test-'));
    fs.rmSync(directory,{recursive:true,force:true});
  }
});
