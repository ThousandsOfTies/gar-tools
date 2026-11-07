const {EventEmitter}=require('node:events');
// Byte endpoint for an SDK-hosted peripheral. The provider owns SDK link and
// security callbacks. No application packets or session identities live here.
function createSdkBytePort(provider) {
  let owner;
  return class SdkBytePort extends EventEmitter {
    constructor(){super();this.isOpen=false;}
    open(callback){setImmediate(()=>{
      if(owner){callback(Error('SDK peripheral already open'));return;}
      owner=this;
      try{this.unsubscribe=provider.subscribe(bytes=>{if(this.isOpen)this.emit('data',Buffer.from(bytes));});this.isOpen=true;provider.connect();callback();}
      catch(error){this.close(()=>callback(error));}
    });}
    write(bytes,callback){const packet=Buffer.from(bytes);setImmediate(()=>{
      if(!this.isOpen){callback(Error('SDK endpoint closed'));return;}
      try{provider.write(packet);callback();}catch(error){callback(error);this.close();}
    });}
    drain(callback){setImmediate(callback);}
    close(callback=()=>{}){
      if(this.isOpen){this.isOpen=false;this.unsubscribe?.();provider.disconnect();if(owner===this)owner=undefined;this.emit('close');}
      setImmediate(callback);
    }
  };
}
module.exports={createSdkBytePort};
