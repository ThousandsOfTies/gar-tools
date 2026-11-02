import {pcm16,samples16} from './audio-pcm.mjs';
/** Recognisable USB speakerphone; local audio only, no network or App semantics. */
export class GarSpeakerphone extends HTMLElement{
  static observedAttributes=['label','volume'];
  constructor(){
    super();this.generation=0;this.sources=new Set();this.muted=false;this.playing=false;this.active=false;
    this.attachShadow({mode:'open'}).innerHTML=`<style>
      :host{display:block;color:var(--gar-component-text,#263b3b);font:inherit}*{box-sizing:border-box}
      .device{width:210px;max-width:100%;margin:auto;padding:22px 22px 16px;border:2px solid #404a4d;border-radius:23px;background:linear-gradient(135deg,#343c3f,#171d20);box-shadow:0 8px 18px #0002;color:#e3eeee;text-align:center;position:relative}
      .grille{width:126px;height:126px;max-width:100%;margin:0 auto 14px;border-radius:50%;border:5px solid #424e51;background:radial-gradient(circle,#111 1.4px,transparent 1.8px) 0 0/6px 6px,#2a3438;display:grid;place-items:center}
      .grille span{font:11px ui-monospace,monospace;background:#263438e8;padding:7px;border-radius:4px;color:#9aafaf}
      .controls{display:flex;align-items:center;gap:10px;justify-content:center}button{background:#465254;color:white;border:1px solid #718183;border-radius:50%;width:36px;height:36px;cursor:pointer;font-size:16px}button[aria-pressed=true]{background:#7c3434}button:focus-visible,input:focus-visible{outline:3px solid #56b8a4;outline-offset:3px}
      .led{width:7px;height:7px;border-radius:50%;background:#5c6768;position:absolute;top:13px;left:calc(50% - 3px)}:host([active]) .led{background:#63d6a7}:host([muted]) .led{background:#e68a78}:host([playing]) .grille{border-color:#70b2a9}
      .usb{width:30px;height:9px;border:2px solid #748487;background:#0f1517;border-radius:5px;margin:15px auto 0}label{display:flex;gap:10px;align-items:center;font-size:11px;margin-top:13px;white-space:nowrap}input{width:100%;accent-color:#76b9ad;min-width:0}meter{width:100%;height:7px;margin-top:12px}.caption{text-align:center;font-size:11px;color:var(--gar-component-muted,#738078);margin:13px 0 0}output{display:block;text-align:center;font-size:12px;min-height:20px;margin-top:9px}
    </style><div class="device"><i class="led"></i><div class="grille"><span>MIC + SPEAKER</span></div><div class="controls"><button type="button" aria-label="マイクをミュート" aria-pressed="false">🎙</button><span>USB AUDIO</span></div><label>音量<input aria-label="スピーカー音量" type="range" min="0" max="100" value="55"></label><meter aria-label="マイク入力レベル" min="0" max="1" value="0"></meter><div class="usb" title="USB"></div></div><p class="caption"></p><output role="status">停止中</output>`;
    this.shadowRoot.querySelector('button').onclick=()=>{this.muted=!this.muted;this.toggleAttribute('muted',this.muted);this.shadowRoot.querySelector('button').setAttribute('aria-pressed',String(this.muted));if(this.muted)this.shadowRoot.querySelector('meter').value=0;for(const track of this.stream?.getAudioTracks()||[])track.enabled=!this.muted;this.emit('gar-audio-mute',{muted:this.muted});};
    this.shadowRoot.querySelector('input').oninput=event=>{this.volume=Number(event.target.value);};
  }
  connectedCallback(){this.attributeChangedCallback();}
  get volume(){const value=Number(this.getAttribute('volume')??55);return Number.isFinite(value)?Math.max(0,Math.min(100,value)):55;}
  set volume(value){this.setAttribute('volume',String(value));}
  attributeChangedCallback(){if(this.shadowRoot){this.shadowRoot.querySelector('.caption').textContent=this.getAttribute('label')||'USBマイク・スピーカー';this.shadowRoot.querySelector('input').value=this.volume;if(this.gain)this.gain.gain.value=this.volume/100;}}
  disconnectedCallback(){this.stop().catch(()=>{});}
  emit(type,detail){this.dispatchEvent(new CustomEvent(type,{detail,bubbles:true,composed:true}));}
  status(text){this.shadowRoot.querySelector('output').textContent=text;}
  async start(){
    if(this.active||this.starting)throw new Error('Audio is already active');
    const generation=++this.generation;this.starting=true;
    try{
      if(!globalThis.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw new Error('マイクにはlocalhostまたはHTTPSが必要です');
      const context=new AudioContext({sampleRate:16000});this.context=context;await context.resume();
      const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true,...(this.getAttribute('device-id')?{deviceId:{exact:this.getAttribute('device-id')}}:{})}});
      if(generation!==this.generation){stream.getTracks().forEach(track=>track.stop());return;}
      this.stream=stream;for(const track of stream.getAudioTracks())track.enabled=!this.muted;
      for(const track of stream.getTracks())track.onended=()=>{if(generation===this.generation){this.emit('gar-audio-error',{message:'マイクが切断されました'});this.stop().catch(()=>{});}};
      await context.audioWorklet.addModule(new URL('./audio-capture-worklet.js',import.meta.url));
      if(generation!==this.generation)return;
      this.capture=new AudioWorkletNode(context,'gar-audio-capture');this.source=context.createMediaStreamSource(stream);this.silence=context.createGain();this.silence.gain.value=0;
      this.source.connect(this.capture);this.capture.connect(this.silence);this.silence.connect(context.destination);
      this.gain=context.createGain();this.gain.gain.value=Number(this.shadowRoot.querySelector('input').value)/100;this.gain.connect(context.destination);
      this.capture.port.onmessage=event=>{
        if(generation!==this.generation||this.muted)return;const values=event.data;let power=0;for(const value of values)power+=value*value;
        this.shadowRoot.querySelector('meter').value=Math.min(1,Math.sqrt(power/values.length)*5);
        this.emit('gar-audio-input',{bytes:pcm16(values,context.sampleRate,16000),sampleRate:16000});
      };
      this.active=true;this.toggleAttribute('active',true);this.status('PCのマイク・スピーカーを使用中');this.emit('gar-audio-state',{active:true});
    }catch(error){if(generation===this.generation){await this.stop();throw error;}}
    finally{if(generation===this.generation)this.starting=false;}
  }
  playPcm(bytes,{sampleRate=24000}={}){
    if(!this.context||!this.active)throw new Error('Audio is stopped');
    if(!Number.isInteger(sampleRate)||sampleRate<8000||sampleRate>48000)throw new Error('Invalid playback rate');
    const values=samples16(bytes);if(!values.length)return;
    const context=this.context,start=Math.max(context.currentTime+.025,this.nextTime||0);
    if(start-context.currentTime+values.length/sampleRate>4)throw new Error('再生音声が遅延しています。接続し直してください');
    const buffer=context.createBuffer(1,values.length,sampleRate);buffer.getChannelData(0).set(values);
    const source=context.createBufferSource();source.buffer=buffer;source.connect(this.gain);this.sources.add(source);
    source.onended=()=>{this.sources.delete(source);if(!this.sources.size)this.setPlaying(false);};
    source.start(start);this.nextTime=start+buffer.duration;this.setPlaying(true);
  }
  setPlaying(value){if(this.playing===value)return;this.playing=value;this.toggleAttribute('playing',value);this.emit('gar-audio-playback',{playing:value});}
  stopPlayback(){for(const source of this.sources){source.onended=null;try{source.stop();}catch{}}this.sources.clear();this.nextTime=0;this.setPlaying(false);}
  async stop(){
    ++this.generation;this.starting=false;this.active=false;this.stopPlayback();
    this.capture?.disconnect();this.source?.disconnect();this.silence?.disconnect();this.gain?.disconnect();
    for(const track of this.stream?.getTracks()||[]){track.onended=null;track.stop();}this.stream=null;
    const context=this.context;this.context=null;if(context&&context.state!=='closed')await context.close();
    this.toggleAttribute('active',false);this.shadowRoot.querySelector('meter').value=0;this.status('停止中');this.emit('gar-audio-state',{active:false});
  }
}
customElements.define('gar-speakerphone',GarSpeakerphone);
