import '/gar-components/sbc-board.mjs';
const a=document.querySelector('#a'),b=document.querySelector('#b');
function check(condition,message){if(!condition)throw new Error(message);}
try{
  a.ports=['USB0','USB1'];b.ports=['ETH','USB-C'];
  check(a.powered&&!b.powered,'independent initial power');
  let event=null;document.addEventListener('gar-board-power',e=>event=e);
  a.shadowRoot.querySelector('button').click();
  check(!a.powered&&!b.powered,'independent toggle');
  check(event?.detail.powered===false&&event.composed,'composed public input');
  b.powered=true;check(!a.powered&&b.powered,'independent property setter');
  const labels=a.ports;labels.push('mutated');check(a.ports.length===2,'copy ports');
  a.setAttribute('label','<img src=x onerror=alert(1)>');check(!a.shadowRoot.querySelector('img'),'text input is escaped');a.setAttribute('label','Board A');
  check(b.shadowRoot.querySelector('.memory').textContent==='4 GB','configurable memory');
  a.powered=true;b.powered=false;
  document.querySelector('#result').textContent='PASS: independent state, configuration, power event, escaped labels';
}catch(error){document.querySelector('#result').textContent='FAIL: '+error.message;throw error;}
