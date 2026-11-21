"""Build a static Pages artifact, optionally vendoring the pinned Pyodide runtime.

python scripts/build_pages.py --output-dir outputs/site --vendor-runtime
Only allowlisted solver sources and web assets are published, never the checkout.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VERSION = '0.27.7'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/'
MODULES = ('__init__', 'solver', 'geometry', 'electrodes', 'solver_2p5d', 'receivers',
           'survey', 'grid', 'survey_simulation', 'fields', 'survey_plotting', 'browser')


def fetch(url, destination, digest=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and digest and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
        return
    try:
        with urllib.request.urlopen(url, timeout=120) as response:data=response.read()
    except Exception as exc:
        raise RuntimeError('Download failed for '+destination.name+': '+str(exc)) from exc
    if digest and hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Checksum mismatch for '+destination.name)
    temporary = destination.with_name(destination.name+'.part')
    temporary.write_bytes(data);temporary.replace(destination)


def vendor(directory, cache):
    cache.mkdir(parents=True, exist_ok=True)
    fetch(CDN+'pyodide-lock.json', cache/'pyodide-lock.json')
    lock = json.loads((cache/'pyodide-lock.json').read_text())
    assert lock['info']['version'] == PYODIDE_VERSION
    pending=['numpy','scipy','matplotlib'];needed=set()
    while pending:
        name=pending.pop()
        if name in needed:continue
        needed.add(name);pending.extend(lock['packages'][name]['depends'])
    jobs=[(name,None) for name in ('pyodide.js','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip')]
    jobs.extend((lock['packages'][name]['file_name'],lock['packages'][name]['sha256']) for name in sorted(needed))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda job:fetch(CDN+job[0],cache/job[0],job[1]),jobs))
    fetch(f'https://cdn.jsdelivr.net/gh/pyodide/pyodide@{PYODIDE_VERSION}/LICENSE', cache/'LICENSE')
    directory.mkdir(parents=True, exist_ok=True)
    for name in ['pyodide-lock.json','LICENSE']+[job[0] for job in jobs]:shutil.copyfile(cache/name,directory/name)
    return {'version':PYODIDE_VERSION,'packages':{name:lock['packages'][name]['version'] for name in sorted(needed)},
            'bytes':sum(p.stat().st_size for p in directory.iterdir())}


def build(output, vendor_runtime=False, cache=None):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output.parts[len(ROOT.parts)] not in ('outputs','site'):
        raise ValueError('Use an output directory under outputs/ or site/, or outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    # Clear only the generated artifact's own known files; do not delete user directories.
    for name in ('index.html','app.js','worker.js','styles.css'):
        shutil.copyfile(ROOT/'web'/name,output/name)
    (output/'.nojekyll').write_text('')
    hashes={}
    with zipfile.ZipFile(output/'python.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for module in MODULES:
            path=ROOT/'tunnel_resistivity'/f'{module}.py';relative=path.relative_to(ROOT)
            archive.write(path,str(relative));hashes[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    runtime={'version':PYODIDE_VERSION}
    if vendor_runtime:runtime=vendor(output/'pyodide',cache or ROOT/'outputs/pyodide-cache'/PYODIDE_VERSION)
    config={'pyodideVersion':PYODIDE_VERSION,'runtimeBase':'./pyodide/' if vendor_runtime else CDN,
            'pythonZipSha256':hashlib.sha256((output/'python.zip').read_bytes()).hexdigest(),
            'sourceHashes':hashes,'runtime':runtime}
    (output/'runtime-config.json').write_text(json.dumps(config,indent=2)+'\n')
    print(f'Built static browser site in {output}; vendored runtime={vendor_runtime}',flush=True)
    if vendor_runtime:print(f'Runtime download: {runtime["bytes"]/1024**2:.1f} MiB; packages: '+', '.join(runtime['packages']),flush=True)
    return config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/site')
    parser.add_argument('--vendor-runtime',action='store_true')
    parser.add_argument('--cache-dir',type=Path)
    args=parser.parse_args();build(args.output_dir,args.vendor_runtime,args.cache_dir)

if __name__=='__main__':main()
