/** A generic microphone part. No App messages, endpoints or speech recognition. */
export class GarMicrophoneInput extends HTMLElement {
  constructor(){
    super();this.attachShadow({mode:'open'}).innerHTML=`<style>:host{display:block;font:14px system-ui}section{display:flex;align-items:center;gap:12px;border:1px solid #65716b;border-radius:10px;padding:12px}.mic{font-size:30px}button{cursor:pointer}output{display:block;font-size:12px} :host([active]) .mic{color:#e53c50}</style><section><span class="mic" aria-hidden="true">🎙</span><div><b>マイク</b><output>未接続 · PCM16 / 16kHz</output></div><button type="button">マイクを準備</button></section>`;
    this.shadowRoot.querySelector('button').onclick=()=>this.stream?this.close():this.prepare();
  }
  get active(){return this.hasAttribute('active');}
  set active(value){this.toggleAttribute('active',!!value);for(const t of this.stream?.getTracks()??[])t.enabled=!!value;this.status();}
  status(){this.shadowRoot.querySelector('output').textContent=this.errorMessage||(this.stream?(this.active?'収録中 · PCM16 / 16kHz':'準備済み · 収録停止'):'未接続 · PCM16 / 16kHz');this.shadowRoot.querySelector('button').textContent=this.stream?'接続を解除':'マイクを準備';}
  async prepare(){
    this.errorMessage='';
    try{
      this.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false}});
      const context=this.context=new AudioContext({sampleRate:16000});
      if(context.sampleRate!==16000)throw Error('16kHz audio is unavailable');
      await context.audioWorklet.addModule(new URL('./microphone-worklet.mjs',import.meta.url));
      this.source=context.createMediaStreamSource(this.stream);this.node=new AudioWorkletNode(context,'gar-pcm-input');
      this.node.port.onmessage=e=>{if(this.active)this.dispatchEvent(new CustomEvent('gar-microphone-pcm',{detail:{samples:Array.from(e.data),sampleRate:16000},bubbles:true,composed:true}));};
      const mute=context.createGain();mute.gain.value=0;this.source.connect(this.node).connect(mute).connect(context.destination);
      await context.resume();this.active=this.active;
    }catch(error){this.close();this.errorMessage='マイクを利用できません。Edge等で開き、ブラウザ・OSのマイク許可を確認してください。';this.status();this.dispatchEvent(new CustomEvent('gar-microphone-error',{detail:{message:String(error)},bubbles:true,composed:true}));}
  }
  close(){this.node?.disconnect();this.source?.disconnect();for(const t of this.stream?.getTracks()??[])t.stop();this.context?.close();this.stream=this.context=this.node=this.source=undefined;this.status();}
  disconnectedCallback(){this.close();}
}
if(!customElements.get('gar-microphone-input'))customElements.define('gar-microphone-input',GarMicrophoneInput);
