const {test}=require('node:test'),assert=require('node:assert/strict');
const {createSdkBytePort}=require('./node-byte-port.cjs');
const invoke=(p,method,...args)=>new Promise((resolve,reject)=>p[method](...args,e=>e?reject(e):resolve()));
test('SDK byte ports retain binary data, isolate peripherals and release ownership on close',async()=>{
 const endpoint=()=>{let sink;const writes=[];return {writes,emit:b=>sink?.(b),provider:{subscribe:cb=>{sink=cb;return()=>sink=undefined;},connect(){},disconnect(){},write:b=>writes.push(Buffer.from(b))}};};
 const a=endpoint(),b=endpoint(),A=createSdkBytePort(a.provider),B=createSdkBytePort(b.provider),one=new A(),two=new B(),duplicate=new A();
 const received=[];one.on('data',b=>received.push(b));await invoke(one,'open');await invoke(two,'open');await assert.rejects(invoke(duplicate,'open'),/already open/);
 const binary=Buffer.from([0,255,128,10]);await invoke(one,'write',binary);assert.deepEqual(a.writes,[binary]);assert.equal(b.writes.length,0);
 a.emit(binary);b.emit(Buffer.from([1]));assert.deepEqual(received,[binary]);await invoke(one,'close');a.emit(binary);assert.equal(received.length,1);
 await assert.rejects(invoke(one,'write',binary),/closed/);await invoke(duplicate,'open');await invoke(duplicate,'close');await invoke(two,'close');
});
