import {pcm16,samples16} from './audio-pcm.mjs';
/** Recognisable USB speakerphone; local audio only, no network or App semantics. */
export class GarSpeakerphone extends HTMLElement{
  static observedAttributes=['label','volume','device-id'];
  constructor(){
    super();this.generation=0;this.sources=new Set();this.muted=false;this.playing=false;this.active=false;
    this.attachShadow({mode:'open'}).innerHTML=`<style>
      :host{display:block;color:var(--gar-component-text,#263b3b);font:inherit}*{box-sizing:border-box}
      .device{width:210px;max-width:100%;margin:auto;padding:22px 22px 16px;border:2px solid #404a4d;border-radius:23px;background:linear-gradient(135deg,#343c3f,#171d20);box-shadow:0 8px 18px #0002;color:#e3eeee;text-align:center;position:relative}
      .grille{width:126px;height:126px;max-width:100%;margin:0 auto 14px;border-radius:50%;border:5px solid #424e51;background:radial-gradient(circle,#111 1.4px,transparent 1.8px) 0 0/6px 6px,#2a3438;display:grid;place-items:center}
      .grille span{font:11px ui-monospace,monospace;background:#263438e8;padding:7px;border-radius:4px;color:#9aafaf}
      .controls{display:flex;align-items:center;gap:10px;justify-content:center}button{background:#263033;color:#9ba8ad;border:1px solid #718183;border-radius:50%;width:44px;height:44px;display:grid;place-items:center;cursor:pointer}button[data-state=active],button[data-state=muted]{color:#ff6b6b}button svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.mic-slash{display:none;stroke-width:3}button[data-state=muted] .mic-slash{display:block}button:focus-visible,input:focus-visible{outline:3px solid #56b8a4;outline-offset:3px}.controls span{font-size:10px}.mic-state{font-size:12px;line-height:1.6;margin:10px 0 0}.mic-state[data-muted=true]{color:#ffb4a7;font-weight:700}
      .led{width:7px;height:7px;border-radius:50%;background:#5c6768;position:absolute;top:13px;left:calc(50% - 3px)}:host([active]) .led{background:#63d6a7}:host([muted]) .led{background:#e68a78}:host([playing]) .grille{border-color:#70b2a9}
      .usb{width:30px;height:9px;border:2px solid #748487;background:#0f1517;border-radius:5px;margin:15px auto 0}label{display:flex;gap:10px;align-items:center;font-size:11px;margin-top:13px;white-space:nowrap}input{width:100%;accent-color:#76b9ad;min-width:0}meter{width:100%;height:7px;margin-top:12px}.caption{text-align:center;font-size:11px;color:var(--gar-component-muted,#738078);margin:13px 0 0}output{display:block;text-align:center;font-size:12px;min-height:20px;margin-top:9px;overflow-wrap:anywhere}.input-select{display:block;white-space:normal}select{display:block;width:100%;min-width:0;margin-top:6px;padding:8px;font:inherit;color:inherit;background:transparent;border:1px solid #899b94;border-radius:4px}
    </style><div class="device"><i class="led"></i><div class="grille"><span>MIC + SPEAKER</span></div><div class="controls"><button type="button" aria-label="マイクをミュート" aria-pressed="false" data-state="stopped" title="マイク停止中"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/><path class="mic-slash" d="M3 3 21 21"/></svg></button><span>USB AUDIO</span></div><p class="mic-state">マイク：停止中</p><label>音量<input aria-label="スピーカー音量" type="range" min="0" max="100" value="55"></label><meter aria-label="マイク入力レベル" min="0" max="1" value="0"></meter><div class="usb" title="USB"></div></div><p class="caption"></p><output role="status">停止中</output>`;
    this.shadowRoot.querySelector('button').onclick=()=>{this.muted=!this.muted;this.toggleAttribute('muted',this.muted);this.updateMicrophone();if(this.muted)this.shadowRoot.querySelector('meter').value=0;for(const track of this.stream?.getAudioTracks()||[])track.enabled=!this.muted;this.emit('gar-audio-mute',{muted:this.muted});};
    const inputLabel=document.createElement('label');inputLabel.className='input-select';inputLabel.textContent='入力マイク（変更は会話停止中）';
    const select=document.createElement('select');select.setAttribute('aria-label','入力マイク');select.append(new Option('Windowsの既定のマイク',''));inputLabel.append(select);this.shadowRoot.append(inputLabel);
    select.onchange=()=>{if(select.value)this.setAttribute('device-id',select.value);else this.removeAttribute('device-id');};
    this.devicesChanged=()=>this.refreshMicrophones().catch(()=>{});
    this.shadowRoot.querySelector('input').oninput=event=>{this.volume=Number(event.target.value);};
  }
  connectedCallback(){this.attributeChangedCallback();this.devicesChanged();navigator.mediaDevices?.addEventListener('devicechange',this.devicesChanged);}
  get volume(){const value=Number(this.getAttribute('volume')??55);return Number.isFinite(value)?Math.max(0,Math.min(100,value)):55;}
  set volume(value){this.setAttribute('volume',String(value));}
  attributeChangedCallback(){if(this.shadowRoot){this.shadowRoot.querySelector('.caption').textContent=this.getAttribute('label')||'USBマイク・スピーカー';this.shadowRoot.querySelector('input').value=this.volume;if(this.gain)this.gain.gain.value=this.volume/100;const select=this.shadowRoot.querySelector('select');if(select)select.value=this.getAttribute('device-id')||'';}}
  disconnectedCallback(){navigator.mediaDevices?.removeEventListener('devicechange',this.devicesChanged);this.stop().catch(()=>{});}
  async refreshMicrophones(){
    if(!navigator.mediaDevices?.enumerateDevices)return;
    const devices=await navigator.mediaDevices.enumerateDevices();if(!this.isConnected)return;
    const select=this.shadowRoot.querySelector('select'),selected=this.getAttribute('device-id')||'';
    select.replaceChildren(new Option('Windowsの既定のマイク',''));
    for(const device of devices.filter(device=>device.kind==='audioinput'&&device.deviceId))select.append(new Option(device.label||`マイク ${select.options.length}`,device.deviceId));
    if(selected&&![...select.options].some(option=>option.value===selected))select.append(new Option('指定したマイク（未検出）',selected));
    select.value=selected;
  }
  emit(type,detail){this.dispatchEvent(new CustomEvent(type,{detail,bubbles:true,composed:true}));}
  status(text){this.shadowRoot.querySelector('output').textContent=text;}
  updateMicrophone(){
    const button=this.shadowRoot.querySelector('button'),state=this.shadowRoot.querySelector('.mic-state');
    button.setAttribute('aria-pressed',String(this.muted));button.setAttribute('aria-label',this.muted?'マイクのミュートを解除':'マイクをミュート');
    button.dataset.state=this.muted?'muted':this.active?'active':'stopped';button.title=this.muted?'ミュート中：押すと解除します':this.active?'入力中：押すとミュートします':'マイク停止中：押すとミュートを設定します';
    state.dataset.muted=String(this.muted);state.textContent=this.muted?'マイク：ミュート中':this.active?'マイク：入力ON':'マイク：停止中';
    this.shadowRoot.querySelector('select').disabled=Boolean(this.active||this.starting);
  }
  async start(){
    if(this.active||this.starting)throw new Error('Audio is already active');
    const generation=++this.generation;this.starting=true;this.updateMicrophone();
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
      this.active=true;this.toggleAttribute('active',true);this.updateMicrophone();this.status(`入力：${stream.getAudioTracks()[0]?.label||'PCの既定マイク'}`);this.devicesChanged();this.emit('gar-audio-state',{active:true});
    }catch(error){if(generation===this.generation){await this.stop();throw error;}}
    finally{if(generation===this.generation)this.starting=false;}
  }
  playPcm(bytes,{sampleRate=24000}={}){
    if(!this.context||!this.active)throw new Error('Audio is stopped');
    if(!Number.isInteger(sampleRate)||sampleRate<8000||sampleRate>48000)throw new Error('Invalid playback rate');
    const values=samples16(bytes);if(!values.length)return;
    const context=this.context,start=Math.max(context.currentTime+.025,this.nextTime||0);
    // Live providers can generate faster than playback. Bound memory without
    // treating an ordinary sentence arriving ahead of playback as a failure.
    if(start-context.currentTime+values.length/sampleRate>60)throw new Error('再生待ち音声が60秒を超えました。接続し直してください');
    const buffer=context.createBuffer(1,values.length,sampleRate);buffer.getChannelData(0).set(values);
    const source=context.createBufferSource();source.buffer=buffer;source.connect(this.gain);this.sources.add(source);
    source.onended=()=>{source.disconnect();this.sources.delete(source);if(!this.sources.size)this.setPlaying(false);};
    source.start(start);this.nextTime=start+buffer.duration;this.setPlaying(true);
  }
  setPlaying(value){if(this.playing===value)return;this.playing=value;this.toggleAttribute('playing',value);this.emit('gar-audio-playback',{playing:value});}
  stopPlayback(){for(const source of this.sources){source.onended=null;try{source.stop();}catch{}source.disconnect();}this.sources.clear();this.nextTime=0;this.setPlaying(false);}
  async stop(){
    ++this.generation;this.starting=false;this.active=false;this.stopPlayback();
    this.capture?.disconnect();this.source?.disconnect();this.silence?.disconnect();this.gain?.disconnect();
    for(const track of this.stream?.getTracks()||[]){track.onended=null;track.stop();}this.stream=null;
    const context=this.context;this.context=null;if(context&&context.state!=='closed')await context.close();
    this.toggleAttribute('active',false);this.updateMicrophone();this.shadowRoot.querySelector('meter').value=0;this.status('停止中');this.emit('gar-audio-state',{active:false});
  }
}
customElements.define('gar-speakerphone',GarSpeakerphone);
