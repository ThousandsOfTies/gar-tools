import {base64,unbase64} from './audio-pcm.mjs';
const endpoint='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent';
/** Browser/Node-neutral Live protocol. App instructions and tool execution are injected. */
export class GeminiLive extends EventTarget{
  constructor({socketFactory=url=>new WebSocket(url),onTool=async()=>{throw new Error('No tool adapter');}}={}){super();this.factory=socketFactory;this.onTool=onTool;this.generation=0;this.ready=false;this.calls=new Map();}
  emit(type,detail){const event=new Event(type);event.detail=detail;this.dispatchEvent(event);}
  connect({apiKey,model,voice,instruction,tools=[]}){
    if(this.socket)throw new Error('Already connected');
    if(typeof apiKey!=='string'||!apiKey.trim())throw new Error('API key is required');
    if(!/^[\w.-]{1,100}$/.test(model)||!/^[\w.-]{1,40}$/.test(voice))throw new Error('Invalid model or voice');
    const generation=++this.generation,setup={model:`models/${model}`,generationConfig:{responseModalities:['AUDIO'],speechConfig:{voiceConfig:{prebuiltVoiceConfig:{voiceName:voice}}}},systemInstruction:{parts:[{text:instruction}]},tools:[{functionDeclarations:tools}],inputAudioTranscription:{},outputAudioTranscription:{}};
    this.allowed=new Set(tools.map(tool=>tool.name));this.calls.clear();this.ready=false;
    let socket;
    try{socket=this.factory(endpoint+'?key='+encodeURIComponent(apiKey.trim()));}
    catch{throw new Error('Cannot open the Gemini connection. Check browser network access.');}
    this.socket=socket;
    this.emit('state','connecting');
    const ready=new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});
    this.timer=setTimeout(()=>this.fail('Gemini connection timed out'),15000);
    socket.onopen=()=>{if(this.socket===socket)socket.send(JSON.stringify({setup}));};
    socket.onmessage=event=>this.receive(event.data,socket,generation).catch(()=>this.fail('Invalid Gemini response'));
    socket.onerror=()=>{if(this.socket===socket)this.fail('Gemini connection failed. Check the API key and model access.');};
    socket.onclose=()=>{if(this.socket===socket)this.fail('Gemini connection ended. Reconnect to continue.');};
    return ready;
  }
  send(value){if(this.socket?.readyState!==1)return false;this.socket.send(JSON.stringify(value));return true;}
  sendAudio(bytes){
    if(!this.ready)return false;
    if(!(bytes instanceof Uint8Array)||bytes.length>65536||bytes.length%2)throw new Error('Invalid PCM input');
    if((this.socket.bufferedAmount||0)>65536){this.fail('Audio upload is too slow; reconnect');return false;}
    return this.send({realtimeInput:{audio:{data:base64(bytes),mimeType:'audio/pcm;rate=16000'}}});
  }
  audioEnd(){if(this.ready)this.send({realtimeInput:{audioStreamEnd:true}});}
  text(text){if(!this.ready||typeof text!=='string'||!text.trim()||text.length>2000)throw new Error('Conversation is not ready or text is invalid');this.send({clientContent:{turns:[{role:'user',parts:[{text}]}],turnComplete:true}});}
  async receive(raw,socket,generation){
    if(raw instanceof Blob)raw=await raw.text();
    if(this.socket!==socket||generation!==this.generation)return;
    if(typeof raw!=='string'||raw.length>1048576)throw new Error('Invalid message');
    const message=JSON.parse(raw);
    if(message.error){this.fail('Gemini rejected the request. Check API settings and quota.');return;}
    if(message.setupComplete&&!this.ready){clearTimeout(this.timer);this.ready=true;this.resolve?.();this.resolve=this.reject=null;this.emit('state','ready');}
    if(message.goAway){this.fail('Gemini session is ending. Reconnect to continue.');return;}
    const content=message.serverContent;
    if(content?.interrupted){this.emit('interrupted',{});}
    else for(const part of content?.modelTurn?.parts||[])if(part.inlineData?.data){
      const mime=part.inlineData.mimeType||'audio/pcm;rate=24000';
      if(!/^audio\/pcm(?:;|$)/.test(mime))throw new Error('Unsupported Live audio format');
      this.emit('audio',{bytes:unbase64(part.inlineData.data),sampleRate:24000});
    }
    if(content?.inputTranscription?.text)this.emit('transcript',{role:'user',text:content.inputTranscription.text.slice(0,4000)});
    if(content?.outputTranscription?.text)this.emit('transcript',{role:'model',text:content.outputTranscription.text.slice(0,4000)});
    if(content?.turnComplete)this.emit('turn-end',{});
    if(message.toolCallCancellation?.ids){for(const id of message.toolCallCancellation.ids)this.calls.get(id)?.abort.abort();this.emit('cancel',{ids:message.toolCallCancellation.ids});}
    for(const call of message.toolCall?.functionCalls||[])this.tool(call,generation);
  }
  tool(call,generation){
    if(typeof call.id!=='string'||!call.id||call.id.length>160||!this.allowed.has(call.name))return;
    const existing=this.calls.get(call.id);
    if(existing){if(existing.response)this.send({toolResponse:{functionResponses:[existing.response]}});return;}
    if(this.calls.size>=128){this.fail('Tool call limit reached; reconnect');return;}
    const state={abort:new AbortController()};this.calls.set(call.id,state);
    Promise.resolve().then(()=>this.onTool(call,{signal:state.abort.signal})).then(result=>({result}),()=>({error:'The application could not execute this operation.'})).then(response=>{
      if(generation!==this.generation||state.abort.signal.aborted)return;
      state.response={id:call.id,name:call.name,response};this.send({toolResponse:{functionResponses:[state.response]}});
    });
  }
  fail(message){this.stop();this.emit('error',message);}
  stop(){
    clearTimeout(this.timer);++this.generation;this.ready=false;
    this.reject?.(new Error('Live connection stopped'));this.resolve=this.reject=null;
    for(const call of this.calls.values())call.abort.abort();this.calls.clear();
    const socket=this.socket;this.socket=null;if(socket){socket.onopen=socket.onmessage=socket.onerror=socket.onclose=null;try{socket.close();}catch{}}
    this.emit('state','stopped');
  }
}
