'use strict';
// A visualization of saved MuJoCo state samples, never camera or generated video.
async function mountCpuReplay(trial){
 const panel=document.querySelector('#content .preview-grid .panel');
 if(!panel||!trial.metrics?.trace_url)return;
 const holder=document.createElement('div');holder.className='cpu-replay';
 holder.innerHTML='<canvas width="700" height="250" role="img" aria-label="Recorded MuJoCo block and gantry positions"></canvas><div class="cpu-replay-controls"><button type="button" class="button small" data-play>Play state replay</button><input type="range" min="0" value="0" aria-label="Replay position"><span data-time>0.00 / 3.00 s</span></div><p>Animation of recorded state samples—not camera footage or a rendered robot video.</p>';
 panel.insertBefore(holder,panel.querySelector('figure.media'));
 const canvas=holder.querySelector('canvas'),ctx=canvas.getContext('2d'),slider=holder.querySelector('input');
 const play=holder.querySelector('[data-play]'),clock=holder.querySelector('[data-time]');
 try{
  const response=await fetch(trial.metrics.trace_url,{credentials:'same-origin'});
  if(!response.ok)throw new Error(`Telemetry unavailable (${response.status})`);
  const raw=await response.text();
  if(raw.length>1_500_000)throw new Error('Telemetry exceeds replay limit');
  const rows=raw.trim().split('\n').map(line=>JSON.parse(line));
  if(rows.length<2||rows.length>2000||rows.some((r,i)=>
   !Number.isFinite(r.timestamp_ms)||i>0&&r.timestamp_ms<=rows[i-1].timestamp_ms||
   ![r.object_position_m?.[0],r.object_position_m?.[1],r.pusher_position_m?.[0],r.pusher_position_m?.[1]].every(Number.isFinite)))
   throw new Error('Telemetry cannot be replayed');
  if(!holder.isConnected)return;
  panel.querySelector('figure.media')?.setAttribute('hidden','');
  slider.max=String(rows.length-1);
  let frame=null,last=null,index=0,playheadMs=rows[0].timestamp_ms;
  const x=value=>35+value*680,y=value=>120-value*250;
  function draw(){
   const row=rows[index];ctx.fillStyle='#151b25';ctx.fillRect(0,0,700,250);
   ctx.fillStyle='rgba(92,180,117,.3)';ctx.fillRect(x(.64),95,x(.86)-x(.64),50);
   ctx.strokeStyle='rgba(255,128,84,.45)';ctx.lineWidth=2;ctx.beginPath();
   rows.slice(0,index+1).forEach((r,i)=>i?ctx.lineTo(x(r.object_position_m[0]),y(r.object_position_m[1])):ctx.moveTo(x(r.object_position_m[0]),y(r.object_position_m[1])));ctx.stroke();
   ctx.fillStyle='#ff8054';ctx.beginPath();ctx.arc(x(row.object_position_m[0]),y(row.object_position_m[1]),9,0,Math.PI*2);ctx.fill();
   ctx.fillStyle='#77c9ff';ctx.beginPath();ctx.arc(x(row.pusher_position_m[0]),y(row.pusher_position_m[1]),8,0,Math.PI*2);ctx.fill();
   ctx.fillStyle='#fff';ctx.font='13px sans-serif';ctx.fillText('TARGET',x(.64)+8,92);ctx.fillText('Orange: block · Blue: pusher',25,226);
   slider.value=String(index);clock.textContent=`${(row.timestamp_ms/1000).toFixed(2)} / ${(rows.at(-1).timestamp_ms/1000).toFixed(2)} s`;
  }
  function stop(){if(frame)cancelAnimationFrame(frame);frame=null;last=null;play.textContent='Play state replay';}
  function tick(now){
   if(!holder.isConnected){stop();return;}
   if(last===null)last=now;
   playheadMs+=now-last;last=now;
   while(index<rows.length-1&&rows[index+1].timestamp_ms<=playheadMs)index++;
   draw();if(index>=rows.length-1){stop();return;}frame=requestAnimationFrame(tick);
  }
  play.onclick=()=>{if(frame){stop();return;}if(index>=rows.length-1)index=0;playheadMs=rows[index].timestamp_ms;play.textContent='Pause state replay';frame=requestAnimationFrame(tick);};
  slider.oninput=()=>{stop();index=Number(slider.value);playheadMs=rows[index].timestamp_ms;draw();};
  draw();
 }catch(error){holder.remove();}
}
