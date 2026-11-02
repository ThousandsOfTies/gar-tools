'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {PassThrough,Writable}=require('node:stream');
const {AlsaDuplex}=require('./duplex.cjs');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function processes(){
  const calls=[];
  const spawnProcess=(command,args,options)=>{
    const child=new EventEmitter();child.stdout=new PassThrough();child.stderr=new PassThrough();child.bytes=[];
    child.stdin=new Writable({write(chunk,encoding,callback){child.bytes.push(Buffer.from(chunk));setImmediate(callback);}});
    child.kill=signal=>{child.signal=signal;setImmediate(()=>child.emit('close',null,signal));return true;};
    calls.push({command,args,options,child});setImmediate(()=>child.emit('spawn'));return child;
  };
  return {calls,spawnProcess};
}
test('duplex captures aligned 100ms PCM and drains a long streamed reply before ending playback',async()=>{
  const fixture=processes(),audio=new AlsaDuplex({capture:'plughw:CARD=USB,DEV=0',playback:'plughw:CARD=USB,DEV=0',...fixture});
  const inputs=[],states=[];audio.on('input',bytes=>inputs.push(bytes));audio.on('playback',value=>states.push(value));
  await audio.start();const recorder=fixture.calls[0];
  assert.equal(recorder.command,'arecord');assert.ok(recorder.args.includes('16000'));assert.equal(recorder.options.shell,false);
  recorder.child.stdout.write(Buffer.alloc(3,7));recorder.child.stdout.write(Buffer.alloc(6397,8));
  assert.deepEqual(inputs.map(bytes=>bytes.length),[3200,3200]);assert.equal(inputs[0][0],7);
  audio.playPcm(new Uint8Array(24000*2*8));audio.endTurn();
  for(let i=0;i<6;i++)await settle();
  const player=fixture.calls[1];assert.equal(player.command,'aplay');assert.ok(player.args.includes('24000'));
  assert.equal(Buffer.concat(player.child.bytes).length,24000*2*8);assert.equal(player.child.stdin.writableEnded,true);
  assert.equal(audio.playing,true,'stdin completion must not pretend the speaker has drained');
  player.child.emit('close',0,null);await settle();assert.deepEqual(states,[true,false]);
  await audio.close();assert.equal(recorder.child.signal,'SIGTERM');assert.equal(audio.pendingBytes,0);
});
test('interruption drops old playback; a later turn never receives stale bytes',async()=>{
  const fixture=processes(),audio=new AlsaDuplex({capture:'mic',playback:'speaker',...fixture});await audio.start();
  audio.playPcm(new Uint8Array([1,2]));await settle();await settle();
  const old=fixture.calls[1];const stopping=audio.stopPlayback();
  audio.playPcm(new Uint8Array([3,4]));audio.endTurn();await stopping;for(let i=0;i<6;i++)await settle();
  assert.equal(old.child.signal,'SIGTERM');assert.deepEqual([...Buffer.concat(fixture.calls[2].child.bytes)],[3,4]);
  assert.throws(()=>audio.playPcm(new Uint8Array(24000*2*61)),/60 seconds/);
  await audio.close();assert.throws(()=>audio.playPcm(new Uint8Array([1,2])),/closed/);
});
test('invalid devices and formats fail before an audio process starts',async()=>{
  const fixture=processes();assert.throws(()=>new AlsaDuplex({capture:null,playback:'speaker',...fixture}),/explicit/);
  const audio=new AlsaDuplex({capture:'mic',playback:'speaker',...fixture});
  assert.throws(()=>audio.playPcm(new Uint8Array(3)),/PCM16/);assert.throws(()=>audio.playPcm(new Uint8Array(2),{sampleRate:16000}),/24kHz/);assert.equal(fixture.calls.length,0);await audio.close();
});

test('successive turns keep separate playback children and preserve every PCM chunk',async()=>{
  const fixture=processes(),audio=new AlsaDuplex({capture:'mic',playback:'speaker',...fixture});
  audio.playPcm(new Uint8Array([1,2]));audio.endTurn();audio.playPcm(new Uint8Array([3,4]));audio.endTurn();
  for(let i=0;i<6;i++)await settle();assert.equal(fixture.calls.length,1);
  assert.deepEqual([...Buffer.concat(fixture.calls[0].child.bytes)],[1,2]);fixture.calls[0].child.emit('close',0,null);
  for(let i=0;i<6;i++)await settle();assert.equal(fixture.calls.length,2);assert.deepEqual([...Buffer.concat(fixture.calls[1].child.bytes)],[3,4]);
  fixture.calls[1].child.emit('close',0,null);await settle();assert.equal(audio.playing,false);await audio.close();
});
