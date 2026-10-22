/* Physical recording management. No robot-control commands or camera fabrication. */
function physicalPage(){return heading('Physical recordings','Prepare hardware capture now. Record real policy execution when robot access is available.')+
 `<div class="report-banner"><div><h2>Observe the robot. Keep the evidence.</h2><p>This workspace records externally running policies; it cannot start robot motion. Camera video, DDS feedback and policy commands are uploaded together. Hardware identity remains operator-declared until reviewed on site.</p></div><span class="chip">READ-ONLY HARDWARE</span></div>
 <div class="physical-layout"><form class="panel" id="physicalPlan"><div class="panel-header"><h2>Prepare a capture session</h2><span class="chip">NO HARDWARE REQUIRED TO PLAN</span></div><div class="form-body">
 <div class="field"><label for="physicalPrompt">Supervised task description</label><textarea id="physicalPrompt" required minlength="8" maxlength="400" placeholder="Observe the robot executing an approved low-risk walking task…"></textarea></div>
 <div class="field"><label for="physicalPolicy">Policy name</label><input id="physicalPolicy" required minlength="2" maxlength="100" value="G1 policy — pending access"></div>
 <div class="field-grid"><div class="field"><label for="physicalSerial">Robot serial (when available)</label><input id="physicalSerial" minlength="2" maxlength="64"></div><div class="field"><label for="physicalVariant">Hardware compatibility</label><select id="physicalVariant"><option value="unconfirmed">Not confirmed yet</option><option value="g1_29dof">G1 29-DOF — checked locally</option></select></div></div>
 <div class="field"><label for="physicalDigest">Policy checkpoint digest (when available)</label><input id="physicalDigest" placeholder="sha256: followed by 64 lowercase hex characters" pattern="sha256:[a-f0-9]{64}"><small>A declared digest does not prove which weights the robot ran. Verify on site.</small></div>
 <div class="field-grid"><div class="field"><label for="physicalHazard">Evaluation type</label><select id="physicalHazard"><option value="path_obstruction">Path obstruction</option><option value="falling_object">Falling object observation</option><option value="surface_instability">Traction observation</option></select></div><div class="field"><label for="physicalSeverity">Recorded severity</label><select id="physicalSeverity"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></div></div>
 <label class="physical-consent"><input type="checkbox" id="physicalOperator"> An on-site operator has confirmed hardware and recording readiness. Leave unchecked while waiting for access.</label></div>
 <p class="inline-error" id="physicalError" hidden role="alert"></p><div class="form-footer"><p>Planning and uploads do not invoke paid models.</p><button class="button primary" type="submit">Prepare session</button></div></form>
 <aside class="panel physical-guide"><div class="panel-header"><h2>Hardware handoff</h2></div><ol class="step-list"><li><span>01</span><div><h3>Prepare</h3><p>Save the task and download the capture setup. Missing robot identity or weights remain explicitly pending.</p></div></li><li><span>02</span><div><h3>Observe locally</h3><p>An on-site operator runs the read-only SDK2 observer alongside the approved policy and a local camera.</p></div></li><li><span>03</span><div><h3>Validate</h3><p>Upload response.mp4, telemetry.jsonl and capture.json. The server decodes the video and checks timing, identity and measurements.</p></div></li><li><span>04</span><div><h3>Review</h3><p>Inspect the camera recording and trace. Real Nemotron judging is explicit, budget-gated and cannot certify operator-declared provenance.</p></div></li></ol><p class="tip">No motor publishers, controller deployment or generated hazards. A local emergency stop and qualified supervision are still required.</p><a class="button" href="/docs#physical">Read the physical capture guide ↗</a></aside></div>
 <div class="section-heading"><h2>Capture sessions</h2><p>Private to your organization</p></div><div id="physicalSessions" aria-live="polite">Loading capture sessions…</div>`;}

let physicalEditing=null;
async function mountPhysical(){
 physicalEditing=null;
 const root=$('#physicalSessions');if(!root)return;
 const form=$('#physicalPlan');
 form.onsubmit=async e=>{
  e.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;$('#physicalError').hidden=true;
  const body={prompt:$('#physicalPrompt').value.trim(),policy_name:$('#physicalPolicy').value.trim(),robot_serial:$('#physicalSerial').value.trim()||null,
   robot_variant:$('#physicalVariant').value,checkpoint_digest:$('#physicalDigest').value.trim()||null,
   hazard_type:$('#physicalHazard').value,severity:$('#physicalSeverity').value,on_site_operator_confirmed:$('#physicalOperator').checked};
  try{
   await json(physicalEditing?`/physical/sessions/${physicalEditing}/setup`:'/physical/sessions',{
    method:physicalEditing?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   physicalEditing=null;submit.textContent='Prepare session';notify('Capture setup saved. No robot motion was requested.');await reload();
  }catch(error){$('#physicalError').textContent=error.message;$('#physicalError').hidden=false;}finally{submit.disabled=false;}
 };
 async function reload(){
  try{
   const [sessions,identity]=await Promise.all([json('/physical/sessions'),json('/auth/me')]);
   if(!root.isConnected)return;
   const writable=identity.role!=='viewer';form.querySelector('[type=submit]').disabled=!writable;
   root.innerHTML=sessions.length?`<div class="physical-recordings">${sessions.map(s=>`<article class="panel physical-session" data-session="${escapeHtml(s.session_id)}"><div class="panel-header"><div><span class="eyebrow mono">${escapeHtml(s.session_id)}</span><h2>${escapeHtml(s.setup.policy_name)}</h2></div><span class="badge">${escapeHtml(human(s.status))}</span></div><p class="finding">${escapeHtml(s.setup.prompt)}</p><dl class="metadata"><div><dt>Robot</dt><dd>${escapeHtml(s.setup.robot_serial||'Waiting for hardware access')}</dd></div><div><dt>Checkpoint</dt><dd><code>${escapeHtml(s.setup.checkpoint_digest||'Not available yet')}</code></dd></div><div><dt>Provenance</dt><dd>Operator-declared · not independently attested</dd></div></dl>
   ${s.status==='validated'?`<div class="physical-video"><video src="/physical/sessions/${encodeURIComponent(s.session_id)}/artifacts/response.mp4" controls playsinline preload="metadata" aria-label="Uploaded physical robot recording"></video></div>`:''}
   <div class="physical-actions"><button class="button small" data-setup>Download setup</button>${writable&&s.status==='awaiting_capture'?'<button class="button small" data-edit>Edit setup</button>':''}${writable&&['awaiting_capture','uploading'].includes(s.status)?`<label class="button small">Select recording files<input type="file" data-files multiple accept=".mp4,.json,.jsonl" hidden></label><button class="button small" data-cancel>Cancel session</button>`:''}${s.trial_id?`<a class="button small" href="#/trials/${encodeURIComponent(s.trial_id)}">Inspect flight record ↗</a>${writable?'<button class="button small" data-judge>Request real judge</button>':''}`:''}</div><p class="tip" data-upload-status>${s.verification?'Video decoded and measurements checked. This is not hardware attestation or safety certification.':s.status==='cancelled'?'Session cancelled; existing artifacts retained privately.':'Awaiting recording. No robot footage or metrics have been generated.'}</p></article>`).join('')}</div>`:empty('No physical recordings yet','Prepare a session while you arrange robot access. We do not fabricate hardware footage.');
   for(const card of root.querySelectorAll('[data-session]')){
    const s=sessions.find(s=>s.session_id===card.dataset.session);
    card.querySelector('[data-setup]').onclick=()=>download(s,`${s.session_id}-setup.json`);
    const edit=card.querySelector('[data-edit]');if(edit)edit.onclick=()=>{
     physicalEditing=s.session_id;for(const [id,key] of [['physicalPrompt','prompt'],['physicalPolicy','policy_name'],['physicalSerial','robot_serial'],['physicalVariant','robot_variant'],['physicalDigest','checkpoint_digest'],['physicalHazard','hazard_type'],['physicalSeverity','severity']])$('#'+id).value=s.setup[key]||'';
     $('#physicalOperator').checked=s.setup.on_site_operator_confirmed;form.querySelector('[type=submit]').textContent='Save capture setup';form.scrollIntoView({behavior:'smooth'});
    };
    const fileInput=card.querySelector('[data-files]');if(fileInput)fileInput.onchange=()=>upload(s,card,fileInput.files);
    const cancel=card.querySelector('[data-cancel]');if(cancel)cancel.onclick=async()=>{try{await json(`/physical/sessions/${s.session_id}/cancel`,{method:'POST'});await reload();}catch(e){notify(e.message);}};
    const judge=card.querySelector('[data-judge]');if(judge)judge.onclick=async()=>{
     if(!confirm('Request real Nemotron inference on this uploaded recording? Token Factory charges may apply. Hardware provenance remains unverified.'))return;
     judge.disabled=true;try{const result=await json(`/physical/sessions/${s.session_id}/judge`,{method:'POST'});location.hash=`#/trials/${result.trial_id}`;}catch(e){notify(e.message);judge.disabled=false;}
    };
   }
  }catch(e){if(root.isConnected)root.textContent=e.message;}
 }
 async function upload(session,card,files){
  const status=card.querySelector('[data-upload-status]'),input=card.querySelector('[data-files]');input.disabled=true;
  try{
   if(files.length!==3||new Set([...files].map(f=>f.name)).size!==3||[...files].some(f=>!['response.mp4','telemetry.jsonl','capture.json'].includes(f.name)))throw new Error('Select exactly response.mp4, telemetry.jsonl and capture.json.');
   if(session.setup.robot_variant!=='g1_29dof'||!session.setup.on_site_operator_confirmed||!session.setup.robot_serial||!session.setup.checkpoint_digest)throw new Error('Edit setup to confirm hardware compatibility, the on-site operator, serial and checkpoint before uploading.');
   const limits=await json('/physical/capabilities');if([...files].reduce((a,f)=>a+f.size,0)>limits.maximum_bundle_bytes)throw new Error('Recording exceeds the allowed bundle size.');
   const manifest={};status.textContent='Calculating recording checksums…';
   for(const f of files){const hash=await crypto.subtle.digest('SHA-256',await f.arrayBuffer());manifest[f.name]={bytes:f.size,sha256:[...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('')};}
   const current=await json(`/physical/sessions/${session.session_id}/manifest`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(manifest)});
   for(const file of files){let start=current.uploads[file.name]?.received_bytes||0;
    while(start<file.size){const end=Math.min(start+262144,file.size);status.textContent=`Uploading ${file.name} · ${Math.round(start/file.size*100)}%`;
     const url=`/physical/sessions/${session.session_id}/artifacts/${file.name}`;
     const options={method:'PUT',headers:{'Content-Type':'application/octet-stream','Content-Range':`bytes ${start}-${end-1}/${file.size}`},body:file.slice(start,end)};
     let result;
     for(let attempt=0;attempt<4;attempt++){
      const response=await fetch(url,options);
      if(response.status===429&&attempt<3){const seconds=Math.max(1,Math.min(60,Number(response.headers.get('Retry-After'))||60));status.textContent=`Upload paused for ${seconds}s to respect request limits. Your progress is retained.`;await new Promise(resolve=>setTimeout(resolve,seconds*1000));continue;}
      if(response.status===401){location.assign('/auth/login');throw new Error('Sign in again, then reselect these files to resume.');}
      result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`Upload failed (${response.status}). Reselect the same files to resume.`);break;
     }
     if(!result)throw new Error('Upload request limit reached. Reselect these files later to resume.');
     start=result.received_bytes;
    }
   }
   status.textContent='Decoding video and independently checking telemetry…';
   try{await json(`/physical/sessions/${session.session_id}/validate`,{method:'POST'});}
   catch(e){
    // The hosted proxy can time out while decoding continues on the backend; wait for the stored result.
    if(e.status&&![502,503,504].includes(e.status))throw e;
    status.textContent='Validation is still running on the server; checking its result…';
    let validated=false;
    for(let i=0;i<40&&!validated;i++){await new Promise(done=>setTimeout(done,3000));const current=await json(`/physical/sessions/${session.session_id}`).catch(()=>null);validated=current?.status==='validated';}
    if(!validated)throw new Error('Validation did not finish. Check the recording and select Validate again.');
   }
   notify('Recording validated. No paid judge was called.');await refresh(true);if(root.isConnected)await reload();
  }catch(e){status.textContent=e.message;}finally{input.disabled=false;}
 }
 await reload();
}

function mountPhysicalTrial(id){
 const trial=trials.find(t=>t.trial_id===id);if(trial?.execution_mode!=='physical')return;
 const previews=$$('#content .preview-label');
 if(previews[0])previews[0].firstChild.textContent='SCENARIO BRIEF ';
 if(previews[0]?.querySelector('.chip'))previews[0].querySelector('.chip').textContent='Recorded task description';
 if(previews[1])previews[1].firstChild.textContent='UPLOADED ROBOT CAMERA ';
 const brief=$('#content .preview-grid .media-empty p');if(brief)brief.textContent='This is a recorded physical task. A Cosmos-generated hazard video is not required.';
 for(const dt of document.querySelectorAll('#content dt'))if(dt.textContent==='Simulator')dt.textContent='Capture runtime';
 for(const dt of document.querySelectorAll('#content dt'))if(dt.textContent==='Seed')dt.nextElementSibling.textContent='Not applicable to a physical recording';
 const latencyLabel=$('#content .stats .stat-top');if(latencyLabel)latencyLabel.firstChild.textContent='Command-change latency ';
 const latencyNote=$('#content .stats .stat-note');if(latencyNote)latencyNote.textContent='Observed command-change proxy';
 const note=document.createElement('p');note.className='tip';note.textContent='Physical recording submitted by an operator. Hardware/policy identity is not independently attested. Command-change timing is a proxy, and camera alignment needs on-site verification.';$('#content .progress')?.after(note);
 const progress=$('#content .progress');if(progress)progress.innerHTML=`<span class="reached">Capture uploaded</span><span class="reached">Recording checks</span><span class="${['scoring','done'].includes(trial.status)?'reached':''}">Judge review</span><span class="${trial.status==='done'?'reached':''}">Review evidence</span>`;
 if(trial.status==='recorded')$('#content .finding').textContent='Recording validated. No judge has run. Request the real judge from Physical recordings after spending controls are configured.';
}
function $$(selector){return [...document.querySelectorAll(selector)];}
