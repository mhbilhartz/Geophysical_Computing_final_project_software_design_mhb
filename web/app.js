const $ = id => document.getElementById(id);
const form = $('controls');
const numericKeys = ['electrode_count','electrode_spacing_m','line_start_x_m','max_level','receiver_spacing_steps','dipole_spacing_steps','current_a','depth_m','radius_m','center_x_m','host_resistivity','tunnel_resistivity','max_cell_size_m','padding_factor','x_min_m','x_max_m','height_m','nx','nz'];
const integerKeys = new Set(['electrode_count','max_level','receiver_spacing_steps','dipole_spacing_steps','nx','nz']);
const fallback = {array_type:'wenner',electrode_count:7,electrode_spacing_m:5,line_start_x_m:30,max_level:2,receiver_spacing_steps:1,dipole_spacing_steps:1,current_a:.1,depth_m:15,radius_m:5,center_x_m:50,host_resistivity:100,tunnel_resistivity:1e8,grid_mode:'Automatic',max_cell_size_m:1.25,padding_factor:2,x_min_m:-30,x_max_m:130,height_m:80,nx:128,nz:64};
let defaults = {...fallback};
let worker, epoch = 0, ready = false, active = null, desired = null, due = false, timer, serial = 0;
let snapshots = [], selectedId = null, currentField = null;
const format = value => Number(value).toLocaleString(undefined, {maximumSignificantDigits:6});

function status(text, state='busy') {
  $('status').textContent = text;
  $('status').dataset.state = state;
}
function downloads(enabled) {
  $('csv').disabled = !enabled;
  $('png').disabled = !enabled || !currentField;
  $('snapshot').disabled = !enabled || !snapshots.length;
  $('measurement').disabled = !enabled || !snapshots.length;
}
function syncControls() {
  const material = $('material').value;
  $('tunnel_resistivity').disabled = material !== 'Custom';
  if (material !== 'Custom') $('tunnel_resistivity').value = material === 'Air-filled' ? 1e8 : 5;
  $('depth_m').min = Number($('radius_m').value) + .5;
  if (Number($('depth_m').value) < Number($('depth_m').min)) $('depth_m').value = $('depth_m').min;
  const count = Number($('electrode_count').value), kind = $('array_type').value;
  const rmax = Math.min(4,count-3), dmax = Math.min(3,Math.floor((count-1)/3));
  for (const [key,max] of [['receiver_spacing_steps',rmax],['dipole_spacing_steps',dmax]]) {
    $(key).max = max;
    $(key).value = Math.min(Number($(key).value), max);
  }
  $('receiver_control').hidden = kind !== 'schlumberger';
  $('dipole_control').hidden = kind !== 'dipole-dipole';
  $('receiver_spacing_steps').disabled = kind !== 'schlumberger' || rmax === 1;
  $('dipole_spacing_steps').disabled = kind !== 'dipole-dipole' || dmax === 1;
  const maximum = kind === 'wenner' ? Math.floor((count-1)/3) : kind === 'schlumberger' ? Math.floor((count-1-Number($('receiver_spacing_steps').value))/2) : Math.floor((count-1)/Number($('dipole_spacing_steps').value))-2;
  $('max_level').max = Math.max(1,Math.min(4,maximum));
  $('max_level').value = Math.min(Number($('max_level').value),Number($('max_level').max));
  $('max_level').disabled = maximum === 1;
  const manual = $('grid_mode').value === 'Manual';
  $('manual_grid').hidden = !manual; $('automatic_grid').hidden = manual;
  for (const key of ['x_min_m','x_max_m','height_m','nx','nz']) $(key).disabled = !manual;
  for (const key of ['max_cell_size_m','padding_factor']) $(key).disabled = manual;
  for (const element of form.querySelectorAll('input[type=range]')) {
    const out = $(element.id+'_value');
    if (out) out.textContent = format(element.value) + (['radius_m','depth_m','center_x_m','electrode_spacing_m'].includes(element.id) ? ' m' : '');
  }
}
function parameters() {
  if (!form.checkValidity()) throw new Error('Please correct the highlighted input. Resistivity, current, spacing and dimensions must be positive.');
  const p = {array_type:$('array_type').value,grid_mode:$('grid_mode').value};
  for (const key of numericKeys) {
    const input = $(key);
    const value = input.disabled && ['x_min_m','x_max_m','height_m','nx','nz','max_cell_size_m','padding_factor'].includes(key) ? defaults[key] : Number(input.value);
    if (!Number.isFinite(value) || (integerKeys.has(key) && !Number.isInteger(value))) throw new Error(`Invalid ${key.replaceAll('_',' ')}.`);
    p[key] = value;
  }
  if (p.array_type !== 'schlumberger') p.receiver_spacing_steps = 1;
  if (p.array_type !== 'dipole-dipole') p.dipole_spacing_steps = 1;
  return p;
}
function keepSnapshots() {
  if (ready) worker.postMessage({kind:'retain', identifiers:snapshots.map(s=>s.identifier)});
}
function queue(request, delay=400) {
  desired = {...request,id:++serial}; due = false;
  clearTimeout(timer);
  downloads(false);
  $('field_content').hidden = true;
  currentField = null;
  status(ready ? 'Changes queued. Any scenario shown below retains its completed settings.' : 'Changes queued while Python loads.');
  timer = setTimeout(()=>{due=true;pump();},delay);
}
function scheduleSurvey(delay=400) {
  syncControls();
  try {
    const p = parameters();
    $('plan').textContent = `Requested: ${p.array_type}, ${p.electrode_count} electrodes at ${p.electrode_spacing_m} m pitch; tunnel center (${p.center_x_m}, ${p.depth_m}) m, radius ${p.radius_m} m. Validating grid in the worker…`;
    queue({kind:'survey',parameters:p,material:$('material').value},delay);
  } catch (error) {
    ++serial;desired=null;due=false;clearTimeout(timer);downloads(false);currentField=null;$('field_content').hidden=true;
    status(error.message,'error');
  }
}
function pump() {
  if (!ready || active || !desired || !due) return;
  active = desired;
  $('stop').disabled = false;
  document.body.dataset.busy = 'true';
  status(active.kind === 'field' ? 'Computing the selected source field…' : 'Computing the requested survey. Controls remain available.');
  worker.postMessage(active);
}
function currentSnapshot() {return snapshots.find(s=>s.identifier===selectedId);}
function enlarge(link,src,caption) {
  link.href=src;
  link.onclick=event=>{
    event.preventDefault();$('figure_detail').src=src;$('figure_detail').alt=caption;
    $('figure_caption').textContent=caption;$('figure_detail').classList.remove('actual_size');
    $('figure_zoom').textContent='Actual size';$('figure_dialog').showModal();
  };
}
function image(id,src) {$(id).src=src;enlarge($(id+'_link'),src,$(id).alt);}
function renderField(field) {
  const snapshot = currentSnapshot();
  if (!snapshot || field.identifier !== snapshot.identifier || Number($('measurement').value) !== field.index) return;
  snapshot.field=field;snapshot.selected=field.index;currentField=field;
  const e=field.electrodes;
  $('field_info').textContent = `Measurement ${field.index+1}: A=${e.A}, B=${e.B}, M=${e.M}, N=${e.N} m · ρa=${format(field.apparent_resistivity_ohm_m)} Ω·m · VM−VN=${format(field.voltage_v)} V · secondary receiver voltage=${format(field.secondary_voltage_v)} V`;
  const grid=$('field_plots');grid.replaceChildren();
  const names=['Subsurface resistivity (Ω·m)','Electrical potential (V)','Current density (A/m²) and flow direction','Tunnel − homogeneous potential (V)'];
  field.panels.forEach((src,i)=>{
    const figure=document.createElement('figure'),caption=document.createElement('figcaption'),link=document.createElement('a'),img=document.createElement('img');
    caption.textContent=names[i];img.src=src;img.alt=names[i];enlarge(link,src,names[i]);link.append(img);figure.append(caption,link);grid.append(figure);
  });
  image('surface',field.surface);image('map',field.survey_map);
  $('field_content').hidden=false;
}
function renderSnapshot(snapshot) {
  selectedId=snapshot.identifier;
  const m=snapshot.metadata,p=m.parameters,g=m.grid;
  $('result_content').hidden=false;
  $('scenario_title').textContent=`Completed scenario #${snapshot.identifier}`;
  $('scenario_info').textContent=`${p.array_type} · ${p.electrode_count} electrodes, ${p.electrode_spacing_m} m pitch, levels 1–${p.max_level}, I=${p.current_a} A. Tunnel center (${p.center_x_m}, ${p.depth_m}) m; radius ${p.radius_m} m; host/tunnel ${format(p.host_resistivity)}/${format(p.tunnel_resistivity)} Ω·m. Grid ${g.nx}×${g.nz}, x=${format(g.x_min_m)}…${format(g.x_max_m)} m, bottom ${format(g.height_m)} m.`;
  $('diagnostics').textContent=`${m.measurements} measurements · ${m.sources} source solves · ${format(m.seconds)} s solving the survey · max relative mode residual ${m.max_mode_residual.toExponential(2)} · mode balance ${m.max_mode_balance.toExponential(2)}. Small residuals do not certify grid or boundary accuracy.`;
  $('warnings').hidden=!m.warnings.length;$('warnings').textContent=m.warnings.join(' ');
  $('runtime_note').textContent=`Python ${m.versions.python} · Pyodide ${window.pyodideVersion} · NumPy ${m.versions.numpy} · SciPy ${m.versions.scipy} · Matplotlib ${m.versions.matplotlib}. All calculations run locally in the worker.`;
  image('profile',snapshot.profile);
  const select=$('measurement');select.replaceChildren();
  snapshot.records.forEach((r,i)=>{
    const option=new Option(`#${i+1} · level ${r.level} · A ${r.a_x_m}, B ${r.b_x_m}, M ${r.m_x_m}, N ${r.n_x_m} m`,i);select.add(option);
  });
  select.value=snapshot.selected;
  const tbody=$('measurements').tBodies[0];tbody.replaceChildren();
  for (const row of snapshot.records) {
    const tr=document.createElement('tr');
    for (const key of ['measurement_id','level','a_x_m','b_x_m','m_x_m','n_x_m','voltage_v','geometric_factor_m','apparent_resistivity_ohm_m']) {
      const td=document.createElement('td');td.textContent=format(row[key]);tr.append(td);
    }
    tbody.append(tr);
  }
  renderField(snapshot.field);
}
function publishSurvey(result) {
  snapshots=[result,...snapshots.filter(s=>s.identifier!==result.identifier)].slice(0,2);
  const select=$('snapshot');select.replaceChildren();
  snapshots.forEach((snapshot,i)=>select.add(new Option(`${i===0?'Latest':'Previous'} · ${snapshot.metadata.parameters.array_type} · tunnel ${format(snapshot.metadata.parameters.tunnel_resistivity)} Ω·m`,snapshot.identifier)));
  select.value=result.identifier;renderSnapshot(result);
}
function startWorker() {
  const generation=++epoch;
  ready=false;active=null;
  const workerUrl=new URL('worker.js',import.meta.url);
  workerUrl.search=new URL(import.meta.url).search;
  worker=new Worker(workerUrl);
  $('reload').hidden=true;
  worker.onmessage=({data})=>{
    if (generation!==epoch) return;
    if (data.type==='loading') {if(!ready)status(data.text);return;}
    if (data.type==='ready') {
      ready=true;defaults=data.defaults;window.pyodideVersion=data.runtimeVersion;
      if (!desired && $('automatic').checked) scheduleSurvey(0);
      else if (!desired) status('Python is ready. Automatic updates are paused; choose Update simulation to run.','ready');
      pump();return;
    }
    if (data.type==='fatal') {fatal(data.error);return;}
    if (data.type==='progress') {
      const d=data.detail;
      if (data.id!==desired?.id) {
        if (desired && active?.id===data.id && d.phase==='survey') {
          status(`New settings queued. Finishing the current survey: ${d.done}/${d.total} source solves. Stop calculation cancels immediately.`);
        }
        return;
      }
      if (d.phase==='plan') {
        $('plan').textContent=`Validated plan: ${d.measurements} measurements, ${d.sources} source solves × 64 Fourier modes; grid ${d.grid.nx}×${d.grid.nz} (${(d.grid.nx*d.grid.nz).toLocaleString()} cells), x=${format(d.grid.x_min_m)}…${format(d.grid.x_max_m)} m, bottom=${format(d.grid.height_m)} m.`;
      } else if (d.phase==='survey') status(`Survey source solves: ${d.done}/${d.total}. Calculating in your browser; controls remain available.`);
      else if (d.phase==='field') status(`Rendering fields for measurement ${d.measurement}…`);
      return;
    }
    if (!active || data.id!==active.id) return;
    active=null;document.body.dataset.busy='false';$('stop').disabled=true;
    if (data.id===desired?.id) {
      desired=null;due=false;
      if (data.type==='result') {
        if (data.kind==='survey') publishSurvey(data.result);else renderField(data.result);
        downloads(true);
        status('Simulation complete. Displayed settings describe this completed scenario.','ready');
        $('status').dataset.resultId=data.id;
      } else {
        downloads(false);$('field_content').hidden=true;
        const lines=data.error.trim().split('\n');status(`Simulation not updated: ${lines.at(-1)} Previous completed data, if shown, keep their original labels.`,'error');
      }
    }
    keepSnapshots();pump();
  };
  worker.onerror=event=>{if(generation===epoch){event.preventDefault();fatal(event.message||'Python worker stopped unexpectedly.');}};
}
function fatal(message) {
  ready=false;active=null;document.body.dataset.busy='false';$('stop').disabled=true;downloads(false);
  status(`Python could not run: ${message}. Reload Python to retry. If this device runs out of memory, use a smaller grid or fewer electrodes.`,'error');
  $('reload').hidden=false;
}
function restart(run) {
  worker?.terminate();++epoch;clearTimeout(timer);desired=null;due=false;active=null;
  snapshots=[];selectedId=null;currentField=null;$('result_content').hidden=true;
  $('snapshot').replaceChildren(new Option('No completed scenarios yet',''));
  downloads(false);$('stop').disabled=true;document.body.dataset.busy='false';
  startWorker();
  if(run) scheduleSurvey(0);
}
function save(blob,filename) {
  const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=filename;
  document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
form.querySelectorAll('input[type=number]').forEach(input=>{input.required=true;});
form.addEventListener('input',event=>{
  if(event.target.id==='automatic'){if($('automatic').checked)scheduleSurvey();return;}
  syncControls();
  if($('automatic').checked)scheduleSurvey();
  else {++serial;desired=null;due=false;clearTimeout(timer);downloads(false);$('field_content').hidden=true;status('Parameters changed. Automatic updates are paused; choose Update simulation.','ready');}
});
form.addEventListener('submit',event=>{event.preventDefault();scheduleSurvey(0);});
$('reset').addEventListener('click',()=>{
  $('max_level').max=4;$('receiver_spacing_steps').max=4;$('dipole_spacing_steps').max=3;
  for(const [key,value] of Object.entries(defaults)) $(key).value=value;
  $('material').value='Air-filled';$('automatic').checked=true;syncControls();scheduleSurvey(0);
});
$('stop').addEventListener('click',()=>{
  $('automatic').checked=false;restart(false);
  status('Calculation stopped. Python is reloading; automatic updates are paused and comparison history was cleared.');
});
$('reload').addEventListener('click',()=>restart(true));
$('snapshot').addEventListener('change',()=>{
  ++serial;desired=null;due=false;clearTimeout(timer);
  renderSnapshot(snapshots.find(s=>s.identifier===Number($('snapshot').value)));downloads(true);
  status('Showing the selected completed scenario. Its labels and exports use its saved settings.','ready');
});
$('measurement').addEventListener('change',()=>queue({kind:'field',identifier:selectedId,index:Number($('measurement').value)},150));
$('csv').addEventListener('click',()=>{
  const s=currentSnapshot();if(s&&!$('csv').disabled)save(new Blob([s.csv],{type:'text/csv;charset=utf-8'}),`survey_${s.identifier}_${s.metadata.parameters.array_type}.csv`);
});
$('png').addEventListener('click',async()=>{
  if(!currentField||$('png').disabled)return;
  const field=currentField;const response=await fetch(field.png);
  save(await response.blob(),`fields_scenario_${field.identifier}_measurement_${field.index+1}.png`);
});
window.addEventListener('pagehide',()=>worker?.terminate());
$('figure_close').addEventListener('click',()=>$('figure_dialog').close());
$('figure_dialog').addEventListener('close',()=>$('figure_detail').removeAttribute('src'));
$('figure_dialog').addEventListener('click',event=>{if(event.target===$('figure_dialog'))$('figure_dialog').close();});
$('figure_zoom').addEventListener('click',()=>{
  const actual=$('figure_detail').classList.toggle('actual_size');
  $('figure_zoom').textContent=actual?'Fit to screen':'Actual size';
});
syncControls();startWorker();
