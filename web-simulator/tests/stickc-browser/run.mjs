import '/gar-components/m5stickc-plus2.mjs';
const a=document.querySelector('#one'),b=document.querySelector('#two'),out=document.querySelector('#results');
const events=[],other=[];a.addEventListener('gar-button',e=>events.push(e));b.addEventListener('gar-button',e=>other.push(e));
const button=(d,key)=>d.shadowRoot.querySelector(`[data-key=${key}]`);
const edge=(key,type,repeat=false)=>button(a,key).dispatchEvent(new KeyboardEvent(type,{key:'Enter',repeat,bubbles:true,composed:true,cancelable:true}));
const check=(x,m)=>{if(!x)throw Error(m);};let failed=0;const lines=[];
function run(name,fn){try{fn();lines.push('PASS '+name);}catch(e){failed++;lines.push('FAIL '+name+': '+e.message);}out.textContent=lines.join('\n');}
run('different resolutions/orientations and independent input',()=>{
  edge('A','keydown');edge('A','keyup');check(events.length===2&&other.length===0,'independent events');
  check(events[0].composed&&events[0].bubbles,'composed public event');
  check(events[0].detail.button==='A'&&events[1].detail.phase==='up','button/phase');
  check(a.querySelector('canvas').width===240&&b.querySelector('canvas').width===135,'native resolutions');
});
run('key repeat does not duplicate down and cancellation prevents release',()=>{
  const n=events.length;edge('B','keydown');edge('B','keydown',true);a.cancelAll();edge('B','keyup');
  check(events.length===n+2&&events.at(-1).detail.phase==='cancel','one down, one cancel');
});
run('power-off cancels current contact; only C remains available',()=>{
  edge('A','keydown');a.powered=false;check(events.at(-1).detail.phase==='cancel','cancel on power change');
  const n=events.length;edge('A','keydown');edge('A','keyup');check(events.length===n,'A disabled');
  edge('C','keydown');edge('C','keyup');check(events.length===n+2,'power switch C works');a.powered=true;
});
run('reconnect installs one set of listeners and has no LCD touch control',()=>{
  a.remove();document.querySelector('main').append(a);const n=events.length;edge('A','keydown');edge('A','keyup');
  check(events.length===n+2,'no duplicate listeners');
  a.querySelector('canvas').dispatchEvent(new MouseEvent('click',{bubbles:true,composed:true}));
  check(events.length===n+2,'LCD click is not a physical button');
});
out.dataset.failed=String(failed);out.dataset.complete='true';
