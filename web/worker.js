/* All Python, sparse solves and Matplotlib rendering run in this Web Worker. */
let runtime;
let config;
const send = (type, payload = {}) => self.postMessage({type, ...payload});

async function initialize() {
  config = await (await fetch(new URL('runtime-config.json', self.location.href))).json();
  const base = new URL(config.runtimeBase, self.location.href).href;
  send('loading', {text: 'Loading Python. The first visit downloads the scientific runtime; later visits use your browser cache.'});
  importScripts(`${base}pyodide.js`);
  runtime = await loadPyodide({indexURL: base});
  runtime.runPython("import os\nos.environ['MPLBACKEND']='Agg'\nos.environ['MPLCONFIGDIR']='/tmp/matplotlib'");
  await runtime.loadPackage(['numpy', 'scipy', 'matplotlib'], {
    messageCallback: text => send('loading', {text}),
    errorCallback: text => send('loading', {text})
  });
  const response = await fetch(new URL('python.zip', self.location.href));
  if (!response.ok) throw new Error(`Python source download failed: ${response.status}`);
  const source = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', source)), x => x.toString(16).padStart(2, '0')).join('');
  if (digest !== config.pythonZipSha256) throw new Error('Python source checksum mismatch. Reload this page.');
  runtime.unpackArchive(source, 'zip', {extractDir: '/project'});
  runtime.runPython("import sys, json\nsys.path.insert(0, '/project')\nfrom tunnel_resistivity.browser import BrowserEngine, DEFAULT_PARAMETERS\nfrom dataclasses import asdict\n_browser_engine=BrowserEngine()");
  send('ready', {defaults: JSON.parse(runtime.runPython('json.dumps(asdict(DEFAULT_PARAMETERS))')),
    runtimeVersion: config.pyodideVersion, sourceHashes: config.sourceHashes});
}

const initialized = initialize().catch(error => {
  send('fatal', {error: String(error.message || error)});
  throw error;
});

self.onmessage = async ({data: request}) => {
  try {
    await initialized;
    runtime.globals.set('_browser_request_json', JSON.stringify(request));
    // This JS callback is invoked during synchronous Python work; the main UI stays responsive.
    const progress = data => send('progress', {id: request.id, detail: JSON.parse(data)});
    runtime.globals.set('_browser_notify', progress);
    const result = runtime.runPython("json.dumps(_browser_engine.handle(json.loads(_browser_request_json), lambda value: _browser_notify(json.dumps(value))), allow_nan=False)");
    if (request.kind !== 'retain') send('result', {id: request.id, kind: request.kind, result: JSON.parse(result)});
  } catch (error) {
    if (request.kind !== 'retain') send('error', {id: request.id, error: String(error.message || error)});
  } finally {
    if (runtime) {
      runtime.globals.delete('_browser_request_json');
      runtime.globals.delete('_browser_notify');
    }
  }
};
