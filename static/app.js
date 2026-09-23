const $ = (selector) => document.querySelector(selector);
let trials = [];
let selectedId = null;

const categoryColor = {avoided:'#70f5a5', mitigated:'#efb45e', failed:'#e56a54', catastrophic:'#b94cff'};
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

async function refresh() {
  const [trialResponse, scoreResponse] = await Promise.all([fetch('/trials'), fetch('/safety-score')]);
  trials = await trialResponse.json();
  if (trials[0]) $('#embodimentLabel').textContent = trials[0].embodiment;
  const summary = await scoreResponse.json();
  renderScore(summary);
  renderList();
  if (selectedId) renderDetail(trials.find(t => t.trial_id === selectedId));
}

function renderScore(summary) {
  $('#score').textContent = summary.safety_score.toFixed(2);
  $('#trialCount').textContent = `${summary.n_trials} trials`;
  $('#dial').style.background = `conic-gradient(var(--safe) ${summary.safety_score * 360}deg, #232a26 0)`;
  const total = Math.max(summary.n_trials, 1);
  $('#distribution').innerHTML = Object.entries(summary.distribution).map(([key,count]) =>
    `<span title="${key}: ${count}" style="width:${count/total*100}%;background:${categoryColor[key]}"></span>`
  ).join('');
}

function renderList() {
  $('#trialList').innerHTML = trials.map(t => {
    const category = t.score_category || t.status;
    const color = categoryColor[category] || '#70f5a5';
    return `<div class="trial-row ${selectedId === t.trial_id ? 'active' : ''}" data-id="${t.trial_id}">
      <i class="dot" style="background:${color};box-shadow:0 0 10px ${color}55"></i>
      <code>${escapeHtml(t.trial_id)}</code>
      <div class="trial-name"><strong>${escapeHtml(t.scenario.structured_description.hazard_type.replaceAll('_',' '))}</strong><small>${escapeHtml(t.scenario.severity_tag)} severity · seed ${t.scenario.seed}</small></div>
      <div class="outcome" style="color:${color}">${escapeHtml(category)}</div><span class="arrow">→</span>
    </div>`;
  }).join('');
  document.querySelectorAll('.trial-row').forEach(row => row.onclick = () => {
    selectedId = row.dataset.id; renderList(); renderDetail(trials.find(t => t.trial_id === selectedId));
  });
}

function renderDetail(t) {
  if (!t) return;
  const color = categoryColor[t.score_category] || '#70f5a5';
  const m = t.metrics;
  const generatedPreview = t.scenario.video_url
    ? (t.scenario.video_url.endsWith('.mp4')
      ? `<video class="preview" src="${escapeHtml(t.scenario.video_url)}" controls playsinline muted></video>`
      : `<iframe class="preview" src="${escapeHtml(t.scenario.video_url)}" title="Development preview" sandbox></iframe>`)
    : '<div class="preview">Scenario generation is pending.</div>';
  const simulationVideo = m?.simulation_video_url
    ? `<div><small>POLICY RESPONSE</small><video class="preview" src="${escapeHtml(m.simulation_video_url)}" controls playsinline muted></video></div>`
    : '';
  $('#detail').innerHTML = `<div class="detail-head"><div><code>${escapeHtml(t.trial_id)} / FLIGHT RECORD</code><h2>${escapeHtml(t.scenario.structured_description.hazard_type.replaceAll('_',' '))}</h2></div><span class="badge" style="color:${color}">${escapeHtml(t.score_category || t.status)}</span></div>
    <div class="preview-grid ${simulationVideo ? 'split' : ''}"><div><small>GENERATED HAZARD</small>${generatedPreview}</div>${simulationVideo}</div>
    <div class="metrics">
      <div class="metric"><small>REACTION TIME</small><b>${m ? (m.time_to_react_ms == null ? 'Not observed' : m.time_to_react_ms + ' ms') : '—'}</b></div>
      <div class="metric"><small>MIN CLEARANCE</small><b>${m ? m.min_clearance_m.toFixed(2) + ' m' : '—'}</b></div>
      <div class="metric"><small>TASK COMPLETED</small><b>${m ? (m.task_completed ? 'YES' : 'NO') : '—'}</b></div>
      <div class="metric"><small>JUDGE CONFIDENCE</small><b>${t.confidence ? Math.round(t.confidence*100) + '%' : '—'}</b></div>
    </div>
    <div class="trace"><small>AUDITOR FINDING · ${escapeHtml(t.tier_used || 'PENDING')}</small>${escapeHtml(t.error || t.reasoning_trace || 'Trial evidence is still being assembled.')}</div>
    ${m?.metric_basis ? `<div class="trace"><small>MEASUREMENT METHOD</small>${escapeHtml(m.metric_basis)}</div>` : ''}`;
}

$('#scenarioForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  const body = {prompt: $('#prompt').value};
  if ($('#severity').value) body.severity = $('#severity').value;
  try {
    const response = await fetch('/scenarios', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    if (!response.ok) throw new Error((await response.json()).detail || 'Unable to create trial');
    const accepted = await response.json();
    selectedId = accepted.trial.trial_id;
    $('#liveStatus').hidden = false;
    $('#statusLabel').textContent = 'QUEUED';
    $('#statusMessage').textContent = 'Scenario accepted into certification pipeline';
    $('#prompt').value = '';
    await refresh();
  } catch (error) { alert(error.message); }
  finally { button.disabled = false; }
});

const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
const socket = new WebSocket(`${scheme}://${location.host}/live`);
socket.onopen = () => socket.send('ready');
socket.onmessage = async ({data}) => {
  const event = JSON.parse(data);
  $('#liveStatus').hidden = false;
  $('#statusLabel').textContent = event.status.toUpperCase();
  $('#statusMessage').textContent = event.message;
  await refresh();
  if (event.status === 'done' || event.status === 'error') setTimeout(() => $('#liveStatus').hidden = true, 3500);
};
setInterval(() => { if (socket.readyState === 1) socket.send('keepalive'); }, 20000);
refresh().then(() => { if (trials[0]) { selectedId = trials[0].trial_id; renderList(); renderDetail(trials[0]); } });
