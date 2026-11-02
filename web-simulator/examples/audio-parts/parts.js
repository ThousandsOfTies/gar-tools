import '/gar-components/speakerphone.mjs';
for(const phone of document.querySelectorAll('gar-speakerphone')){
  let samples=0;
  phone.addEventListener('gar-audio-input',({detail})=>{samples+=detail.bytes.length/2;document.getElementById(phone.id+'-count').textContent=`${samples} samples · ${detail.sampleRate} Hz`;});
}
for(const button of document.querySelectorAll('[data-start]'))button.onclick=()=>document.getElementById(button.dataset.start).start().catch(error=>alert(error.message));
for(const button of document.querySelectorAll('[data-stop]'))button.onclick=()=>document.getElementById(button.dataset.stop).stop();
for(const button of document.querySelectorAll('[data-tone]'))button.onclick=()=>{
  const bytes=new Uint8Array(4800*2),view=new DataView(bytes.buffer),frequency=button.dataset.tone==='first'?440:660;
  for(let i=0;i<4800;i++)view.setInt16(i*2,Math.sin(i*2*Math.PI*frequency/24000)*3000,true);
  document.getElementById(button.dataset.tone).playPcm(bytes);
};
