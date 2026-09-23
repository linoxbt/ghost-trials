'use strict';
// Read-only evidence workflows: viewing a comparison never launches paid jobs.
let comparisonRequest=0;
const evidenceOrigin=t=>t.metrics?.evidence_origin==='synthetic'||t.tier_used?.startsWith('deterministic-rubric')?'synthetic':t.metrics?.evidence_origin||'unknown';
const valueText=value=>value===null||value===undefined?'Not recorded':typeof value==='boolean'?(value?'Yes':'No'):String(value);

function comparisonPage(query){
 const choices=trials.filter(t=>t.status==='done');
 const left=query.get('baseline')||choices[0]?.trial_id||'',right=query.get('candidate')||choices[1]?.trial_id||'';
 const options=selected=>'<option value="">Choose a completed trial</option>'+choices.map(t=>`<option value="${escapeHtml(t.trial_id)}" ${t.trial_id===selected?'selected':''}>${escapeHtml(title(t))} · seed ${t.scenario.seed} · ${escapeHtml(t.trial_id)}</option>`).join('');
 return heading('Compare runs','Inspect matched scenarios. Separate measured differences from claims of improvement.')+
 `<section class="panel comparison-picker"><div class="field"><label for="baselineTrial">Baseline run</label><select id="baselineTrial">${options(left)}</select></div><div class="field"><label for="candidateTrial">Candidate run</label><select id="candidateTrial">${options(right)}</select></div></section><div id="comparisonResult" aria-live="polite">Choose two completed trials to compare.</div>`;
}

async function loadComparison(){
 const node=$('#comparisonResult');if(!node)return;
 const left=$('#baselineTrial').value,right=$('#candidateTrial').value;
 const request=++comparisonRequest;
 if(!left||!right){node.textContent='Choose two completed trials to compare.';return;}
 node.innerHTML='<p class="finding">Checking evidence and matching conditions…</p>';
 try{
  const result=await json(`/comparisons?baseline=${encodeURIComponent(left)}&candidate=${encodeURIComponent(right)}`);
  if(!node.isConnected||request!==comparisonRequest)return;
  const a=trials.find(t=>t.trial_id===left),b=trials.find(t=>t.trial_id===right);
  node.innerHTML=`<div class="report-banner"><div><h2>${result.comparable?(result.comparison_type==='repeatability'?'Matched repeatability check':'Matched policy comparison'):'Exploratory comparison only'}</h2><p>${result.comparable?'Setup metadata matches. This pair is not a general safety guarantee.':'These records cannot establish a policy improvement.'}</p>${result.warnings.length?`<ul class="evidence-warnings">${result.warnings.map(w=>`<li>${escapeHtml(w)}</li>`).join('')}</ul>`:''}</div><span class="chip">${result.comparable?'MATCHED SETUP':'NOT COMPARABLE'}</span></div>
  <div class="preview-grid compare-media">${[a,b].map((t,i)=>`<section class="panel"><div class="preview-label">${i?'CANDIDATE':'BASELINE'}<span class="chip">${escapeHtml(evidenceOrigin(t))}</span></div>${media(t.metrics?.simulation_video_url,`${i?'Candidate':'Baseline'} policy recording`,evidenceOrigin(t)==='synthetic')}<div class="panel-foot"><span class="mono">${escapeHtml(t.trial_id)}</span><a class="text-link" href="${hrefTrial(t)}">Inspect evidence ↗</a></div></section>`).join('')}</div>
  <div class="comparison-controls"><button class="button" id="playPair">Play both recordings</button><button class="button" id="pausePair">Pause both</button><label class="sync-toggle"><input id="syncPair" type="checkbox" ${result.comparable?'checked':''}> Link recording positions</label><button class="button" id="exportComparison">Export comparison</button></div>
  <section class="panel"><div class="panel-header"><h2>Measured differences</h2><p>Candidate minus baseline · descriptive, not causal</p></div><div class="comparison-ledger"><div class="ledger-row ledger-head"><span>Measurement</span><span>Baseline</span><span>Candidate</span><span>Delta</span></div>${result.metrics.map(m=>`<div class="ledger-row"><strong>${escapeHtml(human(m.name))}</strong><span data-label="Baseline">${escapeHtml(valueText(m.baseline))}</span><span data-label="Candidate">${escapeHtml(valueText(m.candidate))}</span><span data-label="Delta">${m.delta===null?'—':escapeHtml(m.delta)}</span></div>`).join('')}</div></section><p class="tip">${result.limitations.map(escapeHtml).join(' ')} Linked playback uses recording-relative time, not alignment of generated Cosmos footage.</p>`;
  const videos=[...node.querySelectorAll('video')];
  $('#playPair').disabled=$('#pausePair').disabled=videos.length!==2;
  $('#playPair').onclick=async()=>{const outcomes=await Promise.allSettled(videos.map(v=>v.play()));if(outcomes.some(o=>o.status==='rejected'))notify('A recording could not play. Check artifact access or use the individual controls.');};
  $('#pausePair').onclick=()=>videos.forEach(v=>v.pause());
  videos.forEach(video=>video.addEventListener('seeked',()=>{if(!$('#syncPair')?.checked)return;videos.filter(v=>v!==video).forEach(v=>{if(Number.isFinite(v.duration)&&Math.abs(v.currentTime-video.currentTime)>.25)v.currentTime=Math.min(v.duration,video.currentTime);});}));
  $('#exportComparison').onclick=()=>download(result,`comparison-${left}-${right}.json`);
 }catch(error){if(node.isConnected)node.textContent=error.message;}
}

function benchmarkPage(){return heading('Benchmark coverage','Know what was tested, which evidence is real, and where coverage is missing.')+`<div class="report-banner"><div><h2>Coverage, not a certificate.</h2><p>Results are separated by checkpoint, embodiment, simulator, rubric, and evidence origin. Repeated identical seeds do not count as new coverage.</p></div><span class="chip">WAREHOUSE SUITE V1</span></div><div id="benchmarkResult" aria-live="polite">Loading benchmark records…</div>`;}

async function loadBenchmark(){
 const node=$('#benchmarkResult');if(!node)return;
 try{const report=await json('/benchmarks');if(!node.isConnected)return;
  node.innerHTML=`<div class="heading-actions benchmark-actions"><button class="button" id="exportBenchmark">Export benchmark</button><a class="button" href="/docs#evaluation">Evaluation methodology ↗</a></div><div class="benchmark-grid">${report.coverage.map(c=>`<article class="panel coverage-card"><div class="panel-header"><div><span class="eyebrow">${escapeHtml(c.severity)} SEVERITY</span><h2>${escapeHtml(human(c.hazard_type))}</h2></div><span class="badge">${escapeHtml(c.origin)}</span></div><dl class="coverage-metrics">${[['Completed',c.n_trials],['Unique seeds',c.unique_seeds],['Falls / collisions',c.fall_or_collision_count],['Tasks completed',c.task_completion_count],['Insufficient evidence',c.excluded_trials],['Execution errors',c.error_count]].map(([label,value])=>`<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl><div class="panel-foot"><span>${escapeHtml(c.policy_name)}<br><code>${escapeHtml(c.checkpoint_digest||'No checkpoint recorded')}</code><br>${escapeHtml(c.rubric_version)} · ${escapeHtml(c.simulator_version||'Unknown simulator')}</span></div></article>`).join('')||empty('No benchmark evidence yet','Run evaluations before drawing conclusions about coverage.')}</div><section class="panel coverage-scope"><div class="panel-header"><h2>Execution scope</h2></div><p class="finding">Implemented runner recipes: ${report.supported_execution_hazards.map(s=>escapeHtml(human(s))).join(', ')}. GPU validation remains necessary. Reduced traction is implemented only in the SONIC/MuJoCo backend, not Isaac Arena.</p><p class="finding">${report.limitations.map(escapeHtml).join(' ')}</p></section>`;
  $('#exportBenchmark').onclick=()=>download(report,'ghost-trials-benchmark.json');
 }catch(error){if(node.isConnected)node.textContent=error.message;}
}

async function mountEvidence(id){
 const t=trials.find(t=>t.trial_id===id);if(!t)return;
 const node=document.createElement('section');node.className='panel evidence-panel';node.id='evidencePanel';
 node.innerHTML='<div class="panel-header"><h2>Evidence inspector</h2><span class="chip">Loading</span></div>';
 $('#content').append(node);
 const action=document.createElement('a');action.className='button';action.href=`#/compare?baseline=${encodeURIComponent(id)}`;action.textContent='Compare run';$('#content .heading-actions')?.append(action);
 if(t.status==='done'){
  const replay=document.createElement('button');replay.className='button';replay.textContent=local()?'Replay demo scenario':'Replay with configured policy';
  replay.onclick=async()=>{
   if(!local()&&!confirm('This executes the configured robot policy and judge against the saved scenario. Provider charges may apply. Continue?'))return;
   replay.disabled=true;
   try{const accepted=await json(`/trials/${encodeURIComponent(id)}/replay`,{method:'POST'});trials.unshift({...accepted.trial,scenario:accepted.scenario});location.hash=hrefTrial(accepted.trial);notify('Saved scenario reused without regenerating the hazard.');}
   catch(error){notify(error.message);replay.disabled=false;}
  };
  $('#content .heading-actions')?.append(replay);
 }
 try{const report=await json(`/trials/${encodeURIComponent(id)}/evidence`);if(!node.isConnected)return;
  node.innerHTML=`<div class="panel-header"><div><h2>Evidence inspector</h2><p>Measured checks and model interpretation are separate.</p></div><span class="badge ${report.evidence_status==='insufficient_evidence'?'insufficient_evidence':''}">${escapeHtml(human(report.evidence_status))}</span></div><p class="finding">${report.origin==='synthetic'?'This is a synthetic development record. No robot executed this trial. ':''}${report.missing_evidence.length?`Missing evidence: ${report.missing_evidence.map(s=>escapeHtml(human(s))).join(', ')}.`:'Recorded simulation artifacts are present; this is not an independent validation.'}</p>
  <div class="evidence-checks">${report.checks.map(c=>`<div><span>${escapeHtml(human(c.name))}</span><strong>${escapeHtml(valueText(c.observed))}</strong><span class="badge ${c.status==='fail'?'failed':c.status==='unknown'?'insufficient_evidence':'avoided'}">${c.status==='pass'?'Within threshold':c.status==='fail'?'Outside threshold':'Unknown'}</span></div>`).join('')}</div>
  <div class="panel-header"><h2>Incident timeline</h2><span class="chip">Recorded timestamps only</span></div>
  ${report.events.length?`<ol class="incident-timeline">${report.events.map(e=>`<li><button class="button small" data-seek-ms="${e.timestamp_ms}" ${t.metrics?.simulation_video_url?'':'disabled'}>${(e.timestamp_ms/1000).toFixed(3)} s</button><div><strong>${escapeHtml(human(e.kind))}</strong><p>${escapeHtml(e.description)}</p></div></li>`).join('')}</ol>`:'<p class="finding">No timestamped telemetry events were captured for this record. Timeline events are not inferred from a narrative or invented for demo data.</p>'}
  <dl class="metadata"><div><dt>Recorded rubric</dt><dd><code>${escapeHtml(report.rubric_version)}</code></dd></div><div><dt>Inspection rubric</dt><dd><code>${escapeHtml(report.checks_rubric_version)}</code></dd></div><div><dt>Scenario SHA-256</dt><dd><code>${escapeHtml(report.scenario_digest)}</code></dd></div><div><dt>Reaction target</dt><dd>${report.thresholds.reaction_ms} ms</dd></div><div><dt>Clearance target</dt><dd>${report.thresholds.clearance_m==null?'Not applicable':`${report.thresholds.clearance_m} m`}</dd></div>${report.thresholds.max_contact_slip_speed_m_s!=null?`<div><dt>Contact slip target</dt><dd>${report.thresholds.max_contact_slip_speed_m_s} m/s</dd></div>`:''}</dl>
  ${report.judge_interpretation?`<details class="raw-interpretation"><summary>Original judge interpretation (before evidence guardrails)</summary><p>${escapeHtml(report.judge_interpretation.reasoning_trace)}</p><span class="badge">${escapeHtml(human(report.judge_interpretation.score_category))}</span></details>`:''}
  <details class="raw-interpretation"><summary>Artifact checksums and limitations</summary><pre>${escapeHtml(JSON.stringify(report.artifact_manifest,null,2))}</pre><ul>${report.limitations.map(s=>`<li>${escapeHtml(s)}</li>`).join('')}</ul></details><div class="panel-foot"><span>Artifact hashes are reported by the worker, not independent attestation.</span><button class="button small" id="exportEvidence">Export evidence assessment</button></div>`;
  $('#exportEvidence').onclick=()=>download({trial:t,evidence:report},`${id}-evidence.json`);
  node.querySelectorAll('[data-seek-ms]').forEach(button=>button.onclick=()=>{const video=$('#content video[aria-label="Robot policy response"]');if(video&&Number.isFinite(video.duration)){video.pause();video.currentTime=Math.min(video.duration,Number(button.dataset.seekMs)/1000);video.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});}else notify('Recording metadata is not available yet. Load the recording first.');});
 }catch(error){if(node.isConnected)node.innerHTML=`<p class="finding">Evidence assessment unavailable: ${escapeHtml(error.message)}</p>`;}
}

function mountEvaluation(page,id,query){
 if(page==='compare'){
  const select=()=>{const values=new URLSearchParams({baseline:$('#baselineTrial').value,candidate:$('#candidateTrial').value});history.replaceState(null,'',`#/compare?${values}`);loadComparison();};
  $('#baselineTrial').onchange=select;$('#candidateTrial').onchange=select;loadComparison();
 }
 if(page==='benchmarks')loadBenchmark();
 if(page==='trials'&&id)mountEvidence(id);
 if(page==='trials'&&!id){const option=document.createElement('option');option.value='insufficient_evidence';option.textContent='Insufficient evidence';option.selected=filters.status===option.value;$('#statusFilter').append(option);}
 if(page==='overview'){
  const first=$('#content .stat');if(first){first.querySelector('.stat-top').firstChild.textContent='Evaluation score';first.querySelector('.stat-note').textContent=summary.score_available?'Within one evaluation cohort':'No pooled score across incompatible cohorts';}
  const caption=$('.score-center small');if(caption)caption.textContent='EVALUATION SCORE';
  if(!summary.score_available){if(first)first.querySelector('.stat-value').textContent='—';$('.score-center strong').textContent='—';}
  const note=document.createElement('div');note.className='tip';note.innerHTML=`${summary.groups?.length||0} distinct evaluation cohorts · ${summary.excluded_trials||0} insufficient-evidence records excluded from weighted scores. Scores are not calibrated safety probabilities. <a class="text-link" href="#/benchmarks">Inspect coverage →</a>`;$('#content .stats')?.after(note);
 }
}
