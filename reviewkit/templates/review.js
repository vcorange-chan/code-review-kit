const map=document.getElementById('map'),paths=document.getElementById('paths');
const stages=[...document.querySelectorAll('.stage')];
const jump=document.getElementById('jump');
let sourceScroll=0;
function showSnapshot(id){const target=document.getElementById(id),view=document.getElementById('source-view');if(!target||!view)return;if(view.hidden)sourceScroll=scrollY;view.hidden=false;target.closest('details').open=true;document.querySelectorAll('.source-line.focused').forEach(n=>n.classList.remove('focused'));target.classList.add('focused');requestAnimationFrame(()=>target.scrollIntoView({behavior:'smooth',block:'center'}))}
document.querySelectorAll('[data-snapshot]').forEach(a=>a.addEventListener('click',event=>{event.preventDefault();showSnapshot(a.dataset.snapshot);history.replaceState(null,'','#'+a.dataset.snapshot)}));
const sourceBack=document.getElementById('source-back');if(sourceBack)sourceBack.addEventListener('click',()=>{document.getElementById('source-view').hidden=true;history.replaceState(null,'',location.href.split('#')[0]);scrollTo({top:sourceScroll,behavior:'smooth'})});
if(location.hash.startsWith('#source-'))showSnapshot(location.hash.slice(1));
stages.forEach((stage,i)=>{const op=document.createElement('option');op.value=stage.id;op.textContent=`${i+1} · ${stage.querySelector('h2').textContent}`;jump.append(op)});
jump.addEventListener('change',()=>document.getElementById(jump.value).scrollIntoView({behavior:'smooth',block:'start'}));
document.getElementById('expand').addEventListener('click',()=>stages.forEach(s=>{const d=s.querySelector('.function>details');if(d)d.open=true}));
document.getElementById('collapse').addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=false));
document.querySelectorAll('.function-link').forEach(b=>b.addEventListener('click',()=>{const d=[...b.closest('.function').children].find(x=>x.tagName==='DETAILS'&&x.querySelector('summary').textContent==='代码位置与源码');d.open=true;d.scrollIntoView({behavior:'smooth',block:'nearest'})}));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(b.dataset.copy);const t=document.getElementById('toast');t.hidden=false;setTimeout(()=>t.hidden=true,1500)}catch{prompt('代码位置',b.dataset.copy)}}));
function draw(){
 const origin=map.getBoundingClientRect();
 const box=n=>{const b=n.getBoundingClientRect();return{x:b.x-origin.x,y:b.y-origin.y,w:b.width,h:b.height}};
 const line=(d,kind,extra='')=>`<path class="${kind}" d="${d}" ${extra}/>`;
 let html='',previous=null;
 const start=document.getElementById('flow-start');
 if(start){const b=box(start);previous=b.y+b.h}
 for(const s of stages){
  const input=box(s.querySelector('.input')),fn=box(s.querySelector('.function')),out=box(s.querySelector('.stage-output')),cx=fn.x+fn.w/2;
  if(previous!==null)html+=line(`M${cx} ${previous}V${input.y}`,'success');
  html+=line(`M${cx} ${input.y+input.h}V${fn.y}`,'success')+line(`M${cx} ${fn.y+fn.h}V${out.y}`,'success');
  previous=out.y+out.h;
  for(const side of ['left','right']){
   const aside=s.querySelector('.fault.'+side);
   if(!aside.offsetWidth||getComputedStyle(aside).visibility==='hidden')continue;
   const groups=[...aside.querySelectorAll('.branch')];
   const targets=groups.length?groups:[aside];
   targets.forEach((target,i)=>{
    const t=box(target),kind=target.classList.contains('degrade')?'degrade':'error';
    const y=fn.y+Math.min(70+i*20,fn.h-12),fromX=side==='left'?fn.x:fn.x+fn.w;
    const endX=side==='left'?t.x+t.w:t.x;
    if(innerWidth>760){const bend=side==='left'?endX+18:endX-18;html+=line(`M${fromX} ${y}H${bend}V${t.y+15}H${endX}`,kind)}
    else{const from=side==='left'?fn.x+8:fn.x+fn.w-8;html+=line(`M${from} ${fn.y+fn.h}V${t.y-9}H${t.x+t.w/2}V${t.y}`,kind)}
    if(target.dataset.resume){
     const destination=document.getElementById(target.dataset.resume);
     if(!destination)return;
     const port=destination.querySelector(target.dataset.port==='input'?'.input':'.stage-output');
     const d=box(port),targetX=side==='left'?d.x:d.x+d.w,targetY=d.y+d.h/2;
     const outer=side==='left'?Math.min(t.x,d.x)-8:Math.max(t.x+t.w,d.x+d.w)+8;
     const sourceX=side==='left'?t.x:t.x+t.w;
     html+=line(`M${sourceX} ${t.y+t.h-8}H${outer}V${targetY}H${targetX}`,'resume',`data-from="${s.id}" data-to="${destination.id}"`);
    }
   });
  }
 }
 const end=document.getElementById('flow-end');
 if(end&&previous!==null){const b=box(end);html+=line(`M${b.x+b.w/2} ${previous}V${b.y}`,'success')}
 paths.innerHTML=html;
}
let pending=false;const schedule=()=>{if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;draw()})};
new ResizeObserver(schedule).observe(map);window.addEventListener('resize',schedule);schedule();
