'use strict';
const $ = (id) => {
  const element = document.getElementById(id);
  if (!element) throw new Error(`The interface is missing its ${id} element. Reload GridShield.`);
  return element;
};
const scenarioButtons = () => Array.from(document.querySelectorAll('.scenario-button'));
const LABEL = {NO_ISSUE_DETECTED: 'No issue detected', ALERT: 'Alert', INSUFFICIENT_EVIDENCE: 'Insufficient evidence'};
const CLASS = {NO_ISSUE_DETECTED: 'normal', ALERT: 'alert', INSUFFICIENT_EVIDENCE: 'unknown'};
let catalog, selected = 'routine', result, proposed = true, busy = false;
const svgNS = 'http://www.w3.org/2000/svg';
function node(tag, attributes = {}, text) {
  const el = document.createElementNS(svgNS, tag);
  Object.entries(attributes).forEach(([key, val]) => el.setAttribute(key, val));
  if (text !== undefined) el.textContent = text;
  return el;
}
function text(el, value) { el.textContent = value; }
function format(value, digits = 3) { return Number.isFinite(value) ? value.toFixed(digits) : '—'; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    throw new Error(failure.message || `The local request failed (${response.status}).`);
  }
  return response.json();
}
function error(message) { $('error').hidden = !message; text($('error'), message || ''); }
function setBusy(value) {
  busy = value;
  ['run', 'benchmark', 'refresh-history'].forEach(id => $(id).disabled = value);
  $('replay').disabled = value || !$('case-file').files.length;
  for (const button of scenarioButtons()) button.disabled = value;
  $('load').disabled = value;
  $('main').setAttribute('aria-busy', String(value));
}
function selectScenario(id) {
  selected = id;
  for (const button of scenarioButtons()) button.setAttribute('aria-pressed', String(button.dataset.id === id));
  const scenario = catalog.scenarios.find(s => s.id === id);
  text($('scenario-description'), scenario.description);
  $('custom-control').hidden = id !== 'custom';
}
function drawNetwork() {
  const svg = $('network');
  svg.replaceChildren();
  const state = result ? (proposed ? result.predicted : result.baseline) : null;
  text($('graph-caption'), result ? `${result.title} · ${proposed ? 'proposed' : 'current'} state${state ? '' : ' unavailable'}` : 'Synthetic network');
  svg.setAttribute('aria-label', `${proposed ? 'Proposed' : 'Current'} six-bus network${state ? `; highest line loading ${state.max_loading_percent.toFixed(1)} percent` : '; no physical assessment available'}`);
  const defs = node('defs');
  const pattern = node('pattern', {id: 'dots', x: 0, y: 0, width: 22, height: 22, patternUnits: 'userSpaceOnUse'});
  pattern.append(node('circle', {cx: 1, cy: 1, r: .7, fill: '#426057', opacity: .5}));
  defs.append(pattern); svg.append(defs, node('rect', {x: 25, y: 30, width: 770, height: 365, fill: 'url(#dots)'}));
  const buses = catalog.network.buses;
  catalog.network.lines.forEach(line => {
    const a = buses.find(b => b.id === line.from), b = buses.find(b => b.id === line.to);
    const data = state?.lines.find(l => l.id === line.id);
    const flagged = data && data.loading_percent > catalog.policy.line_loading_max_percent;
    const coords = {x1: a.x, y1: a.y, x2: b.x, y2: b.y};
    svg.append(node('line', {...coords, class: 'line-track'}), node('line', {...coords, class: `grid-line${flagged ? ' flagged' : ''}`}));
    if (state) svg.append(node('circle', {cx: a.x + (b.x - a.x) * .34, cy: a.y + (b.y - a.y) * .34, r: 3, class: 'flow-dot'}));
    const x = (a.x+b.x)/2, y = (a.y+b.y)/2;
    svg.append(node('rect', {x: x-30, y: y-10, width: 60, height: 19, rx: 3, class: 'line-backing'}));
    svg.append(node('text', {x, y: y+3, 'text-anchor': 'middle', class: `line-value${flagged ? ' flagged' : ''}`}, data ? `${data.loading_percent.toFixed(1)}%` : '—'));
  });
  buses.forEach(bus => {
    const data = state?.buses.find(b => b.id === bus.id);
    const flagged = data && (data.voltage_pu < catalog.policy.voltage_min_pu || data.voltage_pu > catalog.policy.voltage_max_pu);
    svg.append(node('circle', {cx: bus.x, cy: bus.y, r: 16, class: `node-ring${flagged ? ' flagged' : ''}${!state ? ' unknown' : ''}`}));
    svg.append(node('circle', {cx: bus.x, cy: bus.y, r: 4, class: 'node-core'}));
    const direction = bus.y < 200 ? -1 : 1;
    const nameY = bus.y + direction * 37;
    svg.append(node('text', {x: bus.x, y: nameY, 'text-anchor': 'middle', class: 'node-name'}, bus.name));
    svg.append(node('text', {x: bus.x, y: nameY + direction * 18, 'text-anchor': 'middle', class: `node-value${flagged ? ' flagged' : ''}`}, data ? `${data.voltage_pu.toFixed(3)} pu` : 'No result'));
  });
  if (!state) svg.append(node('text', {x: 410, y: 428, 'text-anchor': 'middle', class: 'diagram-unavailable'}, 'Insufficient data or request not eligible for prediction'));
  $('view-current').setAttribute('aria-pressed', String(!proposed));
  $('view-proposed').setAttribute('aria-pressed', String(proposed));
  const demand = result?.predicted?.demand_mw;
  text($('metric-demand'), demand === undefined ? '—' : `${demand.toFixed(2)} MW`);
  text($('metric-loading'), result?.predicted ? `${result.predicted.max_loading_percent.toFixed(1)}%` : '—');
  text($('metric-voltage'), result?.predicted ? `${result.predicted.min_voltage_pu.toFixed(3)} pu` : '—');
  $('metric-loading').classList.toggle('metric-alert', Boolean(result?.predicted && result.predicted.max_loading_percent > 100));
  $('metric-voltage').classList.toggle('metric-alert', Boolean(result?.predicted && result.predicted.min_voltage_pu < .95));
  text($('demand-change'), result?.baseline && result?.predicted ? `Current demand: ${result.baseline.demand_mw.toFixed(2)} MW` : 'Proposed state not assessed');
}
function showAssessment() {
  $('assessment').className = `assessment ${CLASS[result.status]}`;
  text($('result-title'), LABEL[result.status]);
  text($('result-scenario'), `Last assessment: ${result.title} · no equipment action performed`);
  text($('timing'), `${Math.round(result.elapsed_ms)} ms`);
  $('reasons').replaceChildren(...result.reasons.map(r => {const li = document.createElement('li'); li.textContent = r.detail; return li;}));
  for (const [id, status] of [['simple-status', result.simple_status], ['gridshield-status', result.status]]) {
    text($(id), LABEL[status]); $(id).className = `text-${CLASS[status]}`;
  }
  text($('request-detail'), `Lab identity: ${result.command.actor} · Request: ${result.command.device} demand → ${result.command.value_mw} MW. These are simulation fixtures, not authenticated utility identities.`);
  text($('freshness'), `Measurement age: ${result.telemetry.age_seconds} s · Topology: ${result.telemetry.topology_version}`);
  $('measurements').replaceChildren(...result.telemetry.measurements.map(m => {
    const row = document.createElement('tr');
    for (const val of [m.bus, format(m.observed_pu), format(m.model_pu), format(m.residual_pu)]) {const td = document.createElement('td'); td.textContent = val; row.append(td);}
    return row;
  }));
  $('download').disabled = false;
  drawNetwork();
}
async function run() {
  if (busy) return;
  setBusy(true); error(''); text($('run'), 'Calculating…');
  try {
    const body = {scenario_id: selected};
    if (selected === 'custom') body.load_mw = Number($('load').value);
    result = await api('/api/evaluate', body); proposed = true; showAssessment(); await loadHistory();
  } catch (e) {error(e.message);} finally {setBusy(false); text($('run'), 'Run assessment →');}
}
function download(data, name) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob), anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function benchmark() {
  if (busy) return;
  setBusy(true); error(''); text($('benchmark'), 'Checking 30 cases…');
  const container = $('benchmark-result'); text(container, 'Running the same checks against each declared example…');
  try {
    const report = await api('/api/benchmark', {}), s = report.summary;
    container.replaceChildren();
    const metrics = document.createElement('div'); metrics.className = 'benchmark-stats';
    [[`${s.gridshield.matches}/${s.total}`, 'GridShield matches expected labels'], [`${s.simple_rules.matches}/${s.total}`, 'Simple checks match expected labels'], [`${s.median_ms} ms`, 'Median assessment time in this run']].forEach(([value, label]) => {
      const box = document.createElement('div'), strong = document.createElement('strong'), span = document.createElement('span');
      strong.textContent = value; span.textContent = label; box.append(strong, span); metrics.append(box);
    });
    const note = document.createElement('p'); note.textContent = report.method;
    const details = document.createElement('details'), summary = document.createElement('summary'); summary.textContent = 'Inspect all results';
    const table = document.createElement('table'), head = document.createElement('thead'), headRow = document.createElement('tr');
    ['Scenario', 'Expected', 'GridShield', 'Simple checks'].forEach(label => {const th = document.createElement('th'); th.textContent = label; headRow.append(th);});
    head.append(headRow); table.append(head);
    const tbody = document.createElement('tbody');
    report.cases.forEach(c => {const tr = document.createElement('tr'); [c.title, LABEL[c.expected], LABEL[c.gridshield], LABEL[c.simple_rules]].forEach(v => {const td = document.createElement('td'); td.textContent = v; tr.append(td);}); tbody.append(tr);});
    table.append(tbody); details.append(summary, table);
    const button = document.createElement('button'); button.className = 'button secondary'; button.textContent = 'Export comparison'; button.addEventListener('click', () => download(report, 'gridshield-comparison.json'));
    container.append(metrics, note, button, details); await loadHistory();
  } catch (e) {text(container, 'The comparison did not finish.'); error(e.message);} finally {setBusy(false); text($('benchmark'), 'Run all 30 cases →');}
}
$('run').addEventListener('click', run);
$('benchmark').addEventListener('click', benchmark);
$('load').addEventListener('input', () => {text($('load-value'), `${Number($('load').value).toFixed(1)} MW`); text($('run'), 'Assess new demand →');});
$('view-current').addEventListener('click', () => {proposed = false; drawNetwork();});
$('view-proposed').addEventListener('click', () => {proposed = true; drawNetwork();});
$('download').addEventListener('click', () => {if (result) download(result, `gridshield-${result.scenario_id}.json`);});
async function loadHistory() {
  try {
    const data = await api('/api/runs');
    $('run-history').replaceChildren(...data.runs.map(run => {
      const row = document.createElement('tr');
      for (const value of [run.title, new Date(run.created_at).toLocaleString(), LABEL[run.outcome] || run.outcome]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      const cell = document.createElement('td'), button = document.createElement('button');
      button.className = 'history-open'; button.textContent = run.kind === 'benchmark' ? 'Export' : 'Open';
      button.setAttribute('aria-label', `${button.textContent} saved ${run.title}`);
      button.addEventListener('click', async () => {
        if (busy) return;
        setBusy(true); error('');
        try {
          const saved = await api(`/api/runs/${encodeURIComponent(run.id)}`);
          if (run.kind === 'benchmark') download(saved, 'gridshield-saved-comparison.json');
          else {result = saved; proposed = true; showAssessment(); $('assessment').scrollIntoView({block:'start', behavior:'auto'});}
        } catch (e) {error(e.message);} finally {setBusy(false);}
      });
      cell.append(button); row.append(cell); return row;
    }));
    text($('history-message'), data.runs.length ? `${data.runs.length} recent runs` : 'No saved runs yet. Run an assessment to begin.');
  } catch (e) {text($('history-message'), `Could not load saved runs: ${e.message}`);}
}
$('refresh-history').addEventListener('click', loadHistory);
$('case-file').addEventListener('change', () => {$('replay').disabled = busy || !$('case-file').files.length;});
$('template').addEventListener('click', async () => {
  if (busy) return;
  setBusy(true); error('');
  try {
    const sample = await api('/api/evaluate', {scenario_id:'routine'});
    download({format_version:1,name:'Reviewer example',initial_load_mw:0.8,proposed_load_mw:0.9,
      identity_fixture:'operator',measurement_age_seconds:0.2,topology_version:'demo-v1',
      voltages_pu:sample.baseline.buses.map(b=>b.voltage_pu),expected_status:'NO_ISSUE_DETECTED'},'gridshield-case-template.json');
    await loadHistory();
  } catch (e) {error(e.message);} finally {setBusy(false);}
});
$('replay').addEventListener('click', async () => {
  if (busy) return;
  const file = $('case-file').files[0];
  if (!file) return;
  setBusy(true); error(''); text($('replay-message'), 'Assessing the imported synthetic case…');
  try {
    if (file.size > 4096) throw new Error('Choose a case smaller than 4 KB.');
    const input = JSON.parse(await file.text());
    result = await api('/api/replay', input); proposed = true; showAssessment();
    const comparison = result.expected_match === null ? 'No expected label supplied.' : result.expected_match ? 'Matches the supplied development label.' : 'Differs from the supplied development label.';
    text($('replay-message'), `${result.title}: ${LABEL[result.status]}. ${comparison}`);
    await loadHistory(); $('assessment').scrollIntoView({block:'start',behavior:'auto'});
  } catch (e) {text($('replay-message'), `The case was not assessed: ${e.message}`);}
  finally {setBusy(false);}
});
(async function init() {
  try {
    catalog = await api('/api/catalog');
    let group;
    catalog.scenarios.forEach(s => {
      if (group !== s.category) {group = s.category; const label = document.createElement('p'); label.className = 'group-label'; label.textContent = group; $('scenario-list').append(label);}
      const button = document.createElement('button'); button.className = 'scenario-button'; button.dataset.id = s.id; button.textContent = s.title; button.setAttribute('aria-pressed', 'false');
      const arrow = document.createElement('span'); arrow.textContent = '↗'; arrow.setAttribute('aria-hidden', 'true'); button.append(arrow);
      button.addEventListener('click', () => {selectScenario(s.id); run();}); $('scenario-list').append(button);
    });
    text($('scenario-count'), String(catalog.scenarios.length)); selectScenario('routine'); await run();
  } catch (e) {error(`Could not load the local simulator. ${e.message}`);}
})();
