'use strict';
const fs=require('node:fs');
const settings=JSON.parse(fs.readFileSync(0,'utf8'));


async function main(){
  const socket=new WebSocket(settings.url),pending=new Map();let nextId=0;
  const rpc=(method,params={})=>new Promise((resolve,reject)=>{
    const id=++nextId;
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Inspector request timeout'));},settings.durationMs+15000);
    pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});
    socket.send(JSON.stringify({id,method,params}));
  });
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    const request=pending.get(message.id);if(!request)return;pending.delete(message.id);
    message.error?request.reject(new Error('Inspector request failed')):request.resolve(message.result);
  };
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=()=>reject(new Error('Inspector connection failed'));});
  try{
    // The binding selects a module prototype and an App-owned observer; no heap or
    // credentials are serialized. queryObjects returns opaque object handles.
    const expression=`process.getBuiltinModule('module').createRequire(${JSON.stringify(settings.module)})(${JSON.stringify(settings.module)})[${JSON.stringify(settings.prototypeExport)}].prototype`;
    const prototype=await rpc('Runtime.evaluate',{expression});
    if(!prototype.result?.objectId)throw new Error('Runtime prototype unavailable');
    const objects=await rpc('Runtime.queryObjects',{prototypeObjectId:prototype.result.objectId});
    const result=await rpc('Runtime.callFunctionOn',{objectId:objects.objects.objectId,functionDeclaration:Buffer.from(settings.traceFunctionBase64,'base64').toString('utf8'),arguments:[{value:settings.durationMs},{value:!!settings.closeInspector}],awaitPromise:true,returnByValue:true});
    if(result.exceptionDetails||!result.result?.value?.ok)throw new Error('Trace unavailable');
    return result.result.value;
  }finally{
    if(settings.closeInspector)await rpc('Runtime.evaluate',{expression:"setTimeout(()=>process.getBuiltinModule('inspector').close(),200);true"}).catch(()=>{});
    socket.close();
  }
}
main().then(value=>process.stdout.write(JSON.stringify(value)+'\n'),()=>{process.stdout.write(JSON.stringify({ok:false,error:'trace_failed'})+'\n');process.exitCode=1;});
