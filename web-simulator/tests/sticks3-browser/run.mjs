import '/gar-components/m5sticks3.mjs';
const one=document.querySelector('#one'),two=document.querySelector('#two');
const events=[];one.addEventListener('gar-button',e=>events.push(e.detail));
let other=0;two.addEventListener('gar-button',()=>other++);
const check=(condition,message)=>{if(!condition)throw Error(message);};
try{
 check(one.powered&&!two.powered,'Independent power attributes');
 one.press('B','test');one.release('B','test');
 check(events.length===2&&events[0].phase==='down'&&events[1].phase==='up','Button edge contract');
 one.press('C','test');one.release('C','test');
 check(events.length===2,'No third application button');
 one.press('A','test');one.cancelAll();
 check(events.at(-1).phase==='cancel','Cancel cannot confirm');
 check(other===0,'Independent instances');
 two.powered=true;check(one.powered&&two.powered,'Public power setter');
 for(const [index,device] of [one,two].entries()){
  const ctx=device.querySelector('canvas').getContext('2d');ctx.fillStyle=index?'#102e48':'#172c21';ctx.fillRect(0,0,240,240);
  ctx.fillStyle='white';ctx.font='15px sans-serif';ctx.fillText(`Display ${index+1}`,8,30);
 }
 document.querySelector('#results').textContent='PASS · independent power, display and events; A/B edges; cancellation; C ignored';
}catch(error){document.querySelector('#results').textContent='FAIL · '+error.message;throw error;}
