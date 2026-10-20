'use strict';
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
const menu=document.querySelector('.site-menu'), header=document.querySelector('.site-header');
if(menu){menu.onclick=()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));header.classList.toggle('menu-open',open);};header.querySelector('nav').addEventListener('click',e=>{if(e.target.closest('a')){header.classList.remove('menu-open');menu.setAttribute('aria-expanded','false');}});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&header.classList.contains('menu-open')){header.classList.remove('menu-open');menu.setAttribute('aria-expanded','false');menu.focus();}});}
if(!reduced.matches&&'IntersectionObserver' in window){document.body.classList.add('motion-ready');const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target);}}),{threshold:.08});document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));}
document.querySelectorAll('.copy-button').forEach(button=>button.onclick=async()=>{const code=button.closest('.code-block').querySelector('code').textContent;try{await navigator.clipboard.writeText(code);button.textContent='Copied';}catch{button.textContent='Select to copy';const range=document.createRange();range.selectNodeContents(button.closest('.code-block').querySelector('code'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}setTimeout(()=>button.textContent='Copy',2000);});
const search=document.querySelector('#docsSearch');
if(search){const links=[...document.querySelectorAll('.docs-sidebar nav a')];search.oninput=()=>{const q=search.value.toLowerCase().trim();let count=0;links.forEach(a=>{const href=a.getAttribute('href');const content=href?.startsWith('#')?document.querySelector(href)?.textContent||'':'';a.hidden=!`${a.textContent} ${content}`.toLowerCase().includes(q);if(!a.hidden)count++;});document.querySelector('#docsSearchResult').textContent=q?`${count} matching sections`:'';};const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){links.forEach(a=>{const active=a.hash==='#'+e.target.id;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}},{rootMargin:'-10% 0px -65% 0px'});document.querySelectorAll('.docs-content section').forEach(s=>observer.observe(s));}
const canvas=document.querySelector('#world');
if(canvas){
 const ctx=canvas.getContext('2d');let w=600,h=560,t=0,last=0,paused=reduced.matches,scene='falling',frame=0,inView=true,pointer=0;
 const motion=document.querySelector('#motionToggle');
 function updateButton(){motion.textContent=paused?'▷':'Ⅱ';motion.setAttribute('aria-label',paused?'Play illustration':'Pause illustration');}
 const project=([x,y,z])=>{const angle=.62+pointer*.08,rx=x*Math.cos(angle)-z*Math.sin(angle),rz=x*Math.sin(angle)+z*Math.cos(angle),s=Math.min(w/7.8,h/6.9);return [w*.5+rx*s,h*.65-y*s+rz*s*.38];};
 function line(points,color,width=1,dash=[]){ctx.beginPath();points.forEach((p,i)=>{const [x,y]=project(p);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([]);}
 function poly(points,fill,stroke='#a7a394'){ctx.beginPath();points.forEach((p,i)=>{const [x,y]=project(p);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.closePath();ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=.7;ctx.stroke();}}
 function box(x,y,z,sx,sy,sz,color){const a=[x-sx/2,y,z-sz/2],b=[x+sx/2,y,z-sz/2],c=[x+sx/2,y,z+sz/2],d=[x-sx/2,y,z+sz/2],top=p=>[p[0],p[1]+sy,p[2]];poly([d,c,top(c),top(d)],color[0]);poly([b,c,top(c),top(b)],color[1]);poly([top(a),top(b),top(c),top(d)],color[2]);}
 function joint(p,r){const [x,y]=project(p);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle='#e7e5db';ctx.fill();ctx.lineWidth=1.5;ctx.strokeStyle='#5e6861';ctx.stroke();}
 function robot(){const sway=Math.sin(t*1.2)*.025;const dark=['#545c56','#353e37','#8b9388'],light=['#d5d7cb','#aeb4a5','#f4f2e7'];
  ctx.save();const ground=project([-.55,0,0]);ctx.translate(...ground);ctx.scale(1,.32);ctx.beginPath();ctx.ellipse(0,0,49,27,0,0,Math.PI*2);ctx.fillStyle='#565d4214';ctx.fill();ctx.restore();
  for(const side of [-1,1]){const x=-.55+side*.24,hip=[x,1.48,0],knee=[x+side*.025,.79,.03+side*sway],ankle=[x+side*.06,.15,.05];line([hip,knee,ankle],'#626b62',17);line([hip,knee,ankle],'#d6dbcd',11);joint(hip,6);joint(knee,6);joint(ankle,4);box(x+side*.06,.02,.02,.27,.13,.52,dark);}
  box(-.55,1.39,0,.63,.27,.4,dark);box(-.55,1.66,0,.79,.72,.44,light);box(-.55,1.77,.235,.35,.29,.04,dark);
  for(const side of [-1,1]){const shoulder=[-.55+side*.48,2.24,0],elbow=[-.55+side*.64,1.87,.05],hand=[-.55+side*.72,1.5,-.1];line([shoulder,elbow,hand],'#798373',14);line([shoulder,elbow,hand],'#d8ddcf',9);joint(shoulder,7);joint(elbow,5);box(hand[0],hand[1]-.12,hand[2],.14,.24,.17,dark);}
  box(-.55,2.37,0,.16,.13,.17,dark);box(-.55,2.49,0,.5,.42,.42,light);box(-.55,2.59,.22,.38,.14,.015,dark);const eye=project([-.59,2.65,.24]);ctx.fillStyle='#ed773a';ctx.fillRect(eye[0]-3,eye[1]-1,13,2);
 }
 function draw(){ctx.clearRect(0,0,w,h);for(let i=-5;i<=5;i++){line([[i*.65,0,-3.3],[i*.65,0,3.3]],'#ccc6b850');line([[-3.3,0,i*.65],[3.3,0,i*.65]],'#ccc6b850');}
  // A technical scene illustration, intentionally independent of trial metrics.
  const scan=(t*.27)%4-2;poly([[-3,0,scan],[3,0,scan],[3,0,scan+.3],[-3,0,scan+.3]],'#ef82420c',null);line([[-3,0,scan],[3,0,scan]],'#dcaa7860');
  for(const x of [1.2,2.5])for(const z of [-1.4,-.7])line([[x,0,z],[x,2.7,z]],'#a8a591',2);
  for(const y of [.6,1.6,2.6])box(1.85,y,-1.05,1.45,.06,.82,['#c2baa7','#a99e8b','#ece5d4']);
  box(2.14,.67,-1.05,.44,.48,.45,['#d0b58c','#b59468','#ebd3ad']);
  const cycle=(t*.24)%1,bx=scene==='falling'?1.3-cycle*.4:1.8-cycle*1.1,by=scene==='falling'?Math.max(.05,2.68-8*cycle*cycle):.03,bz=scene==='falling'?-.32:1.2;
  line([[bx,0,bz],[bx,3.2,bz]],'#d38a5860',1,[3,5]);box(bx,by,bz,.51,.5,.51,['#ed8a48','#c66a30','#f7b87f']);
  const halo=Array.from({length:45},(_,i)=>{const a=i/44*Math.PI*2;return [bx+Math.cos(a)*.6,.01,bz+Math.sin(a)*.6];});line(halo,'#dd7a3960',1,[4,4]);
  robot();line([[-.55,.03,.4],[-.8,.03,1.2],[-1.25,.03,1.65],[-1.15,.03,2.5]],'#d57a42',1.5,[5,5]);
  const cp=project([-.55,3.15,0]);ctx.strokeStyle='#b3ae9e';ctx.beginPath();ctx.moveTo(cp[0],cp[1]);ctx.lineTo(cp[0]+35,cp[1]-25);ctx.lineTo(cp[0]+100,cp[1]-25);ctx.stroke();ctx.fillStyle='#8e8676';ctx.font='8px monospace';ctx.fillText('POLICY UNDER TEST',cp[0]+39,cp[1]-32);
 }
 function resize(){const rect=canvas.getBoundingClientRect();w=rect.width;h=rect.height;const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);draw();}
 function loop(now){frame=0;if(paused||!inView||document.hidden){last=0;return;}if(last)t+=Math.min((now-last)/1000,.04);last=now;draw();frame=requestAnimationFrame(loop);}
 function start(){if(!frame&&!paused&&inView&&!document.hidden)frame=requestAnimationFrame(loop);}
 motion.onclick=()=>{paused=!paused;updateButton();if(paused){cancelAnimationFrame(frame);frame=0;last=0;}else start();};
 document.querySelectorAll('[data-scene]').forEach(b=>b.onclick=()=>{scene=b.dataset.scene;t=0;document.querySelector('#hazardName').textContent=scene==='falling'?'FALLING OBJECT':'PATH OBSTRUCTION';document.querySelectorAll('[data-scene]').forEach(btn=>{const active=btn===b;btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));});draw();});
 canvas.addEventListener('pointermove',e=>{if(reduced.matches)return;pointer=(e.offsetX/w-.5);if(paused)draw();});
 new ResizeObserver(resize).observe(canvas);new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;if(inView)start();}).observe(canvas);document.addEventListener('visibilitychange',start);reduced.addEventListener('change',e=>{paused=e.matches;updateButton();draw();start();});updateButton();resize();start();
}
