'use strict';
const {spawn}=require('node:child_process');
const {EventEmitter}=require('node:events');
const {deviceName}=require('./audio.cjs');

/** Raw ALSA PCM streams. No cloud, application commands, credentials or files. */
class AlsaDuplex extends EventEmitter{
  constructor({capture,playback,spawnProcess=spawn}={}){
    super();this.captureDevice=deviceName(capture);this.playbackDevice=deviceName(playback);this.spawnProcess=spawnProcess;
    this.turns=[];this.intake=null;this.pendingBytes=0;this.playing=false;this.closed=false;this.stopping=null;
  }
  child(command,args){
    const child=this.spawnProcess(command,args,{stdio:['pipe','pipe','pipe'],shell:false,windowsHide:true});
    const job={child,expected:false,detail:'',error:null};
    child.stderr.on('data',chunk=>{job.detail=(job.detail+chunk.toString()).slice(-2048);});
    // Do not leak arbitrary environment values or provider credentials through errors.
    child.stdin.on('error',error=>{if(!job.expected&&error.code!=='EPIPE')job.error=error;});
    job.done=new Promise(resolve=>{
      let finished=false;
      const finish=error=>{if(finished)return;finished=true;job.finished=true;clearTimeout(job.killTimer);job.error=error;resolve(error);};
      child.once('error',()=>finish(new Error(`${command} could not start`)));
      child.once('close',(code,signal)=>finish(job.expected?null:job.error||(code===0?null:new Error(`${command} failed (${signal||code}): ${job.detail.trim()}`))));
    });
    job.ready=new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',()=>reject(new Error(`${command} could not start`)));});
    return job;
  }
  async start(){
    if(this.closed||this.capture)throw new Error('Audio is closed or already started');
    const job=this.child('arecord',['-q','-D',this.captureDevice,'-t','raw','-f','S16_LE','-r','16000','-c','1','--period-time=20000','--buffer-time=100000']);
    this.capture=job;let remainder=Buffer.alloc(0);
    job.child.stdin.end();
    job.child.stdout.on('data',chunk=>{
      if(this.closed||job.expected)return;
      remainder=Buffer.concat([remainder,chunk]);
      while(remainder.length>=3200){const bytes=Buffer.from(remainder.subarray(0,3200));remainder=remainder.subarray(3200);this.emit('input',bytes);}
    });
    job.done.then(error=>{if(!this.closed&&!job.expected)this.emit('failure',error||new Error('Microphone capture ended'));});
    await job.ready;
  }
  playPcm(bytes,{sampleRate=24000}={}){
    if(this.closed)throw new Error('Audio is closed');
    if(sampleRate!==24000||!(bytes instanceof Uint8Array)||bytes.length%2)throw new Error('Expected 24kHz mono PCM16 playback');
    if(!bytes.length)return;
    if(this.pendingBytes+bytes.length>24000*2*60)throw new Error('Audio playback queue exceeded 60 seconds');
    if(!this.intake){this.intake={queue:[],ended:false,writing:false,job:null};this.turns.push(this.intake);}
    this.intake.queue.push(Buffer.from(bytes));this.pendingBytes+=bytes.length;this.pump();
  }
  endTurn(){if(this.intake){this.intake.ended=true;this.intake=null;this.pump();}}
  setPlaying(value){if(this.playing!==value){this.playing=value;this.emit('playback',value);}}
  pump(){
    const turn=this.turns[0];if(this.closed||this.stopping||!turn||turn.writing)return;
    turn.writing=true;
    (async()=>{
      if(!turn.job){
        turn.job=this.child('aplay',['-q','-D',this.playbackDevice,'-t','raw','-f','S16_LE','-r','24000','-c','1','--buffer-time=100000']);
        turn.job.child.stdout.resume();
        turn.job.done.then(error=>{
          if(this.turns[0]!==turn)return;
          this.turns.shift();if(this.intake===turn)this.intake=null;
          if(!this.turns.length)this.setPlaying(false);
          if(error||!turn.ended){this.emit('failure',error||new Error('Speaker playback ended unexpectedly'));return;}
          this.pump();
        });
        await turn.job.ready;if(this.turns[0]!==turn)return;this.setPlaying(true);
      }
      while(turn.queue.length&&this.turns[0]===turn){
        const bytes=turn.queue.shift();
        try{await new Promise((resolve,reject)=>turn.job.child.stdin.write(bytes,error=>error?reject(error):resolve()));}
        finally{if(this.turns[0]===turn)this.pendingBytes-=bytes.length;}
      }
      if(this.turns[0]===turn&&turn.ended)turn.job.child.stdin.end();
    })().catch(()=>{if(this.turns[0]===turn&&!this.closed)this.emit('failure',new Error('Speaker PCM stream failed'));}).finally(()=>{turn.writing=false;});
  }
  async terminate(job){
    if(!job||job.finished)return;job.expected=true;job.child.stdin.destroy();job.child.kill('SIGTERM');
    job.killTimer=setTimeout(()=>job.child.kill('SIGKILL'),1000);job.killTimer.unref();await job.done;
  }
  stopPlayback(){
    if(this.stopping)return this.stopping;
    const jobs=this.turns.map(turn=>turn.job);this.turns=[];this.intake=null;this.pendingBytes=0;this.setPlaying(false);
    this.stopping=Promise.all(jobs.map(job=>this.terminate(job))).finally(()=>{this.stopping=null;this.pump();});return this.stopping;
  }
  async close(){if(this.closed)return this.closing;this.closed=true;this.closing=Promise.all([this.terminate(this.capture),this.stopPlayback()]);await this.closing;}
}
module.exports={AlsaDuplex};
