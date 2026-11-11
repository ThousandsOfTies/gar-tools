import '/gar-components/microphone-input.mjs';
for(const button of document.querySelectorAll('button[data-target]'))button.onclick=()=>{const mic=document.getElementById(button.dataset.target);mic.active=!mic.active;};
for(const id of ['one','two']){let count=0;document.getElementById(id).addEventListener('gar-microphone-pcm',e=>{count+=e.detail.samples.length;document.getElementById(id+'-count').textContent=`${count} samples`;});}
