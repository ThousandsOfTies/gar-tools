// Generic PCM16 mono boundary. AudioContext requests a 16kHz device clock.
class PcmInput extends AudioWorkletProcessor {
  constructor(){super();this.buffer=new Int16Array(2048);this.offset=0;}
  process(inputs){
    const channel=inputs[0]?.[0];if(!channel)return true;
    for(const value of channel){
      this.buffer[this.offset++]=Math.round(Math.max(-1,Math.min(1,value))*32767);
      if(this.offset===this.buffer.length){this.port.postMessage(this.buffer);this.offset=0;}
    }
    return true;
  }
}
registerProcessor('gar-pcm-input',PcmInput);
