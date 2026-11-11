const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
test('microphone worklet emits bounded PCM16 frames and keeps separate instances independent',()=>{
 let Processor;const messages=[];
 class Base {constructor(){this.port={postMessage:b=>messages.push(new Int16Array(b))};}}
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../components/microphone-worklet.mjs'),'utf8'),{
  AudioWorkletProcessor:Base,registerProcessor:(name,Class)=>{assert.equal(name,'gar-pcm-input');Processor=Class;},Int16Array,Math
 });
 const a=new Processor(),b=new Processor();
 assert.equal(a.process([]),true);a.process([[Float32Array.from([2,-2,0.5,-0.5])]]);
 assert.equal(messages.length,0);a.process([[new Float32Array(2044)]]);
 assert.equal(messages.length,1);assert.deepEqual(Array.from(messages[0].slice(0,4)),[32767,-32767,16384,-16383]);
 b.process([[new Float32Array(2047)]]);assert.equal(messages.length,1);
 b.process([[Float32Array.from([1])]]);assert.equal(messages.length,2);assert.equal(messages[1][2047],32767);
});
