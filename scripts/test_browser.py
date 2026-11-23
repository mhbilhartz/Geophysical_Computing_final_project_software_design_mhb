"""Execute the real Pyodide worker in Chromium; no simulated Python responses.

Uses a temporary static HTTP server only for local/CI tests. The deployed site
needs no Python server. --url can check an already deployed Pages URL instead.
"""
import argparse
import csv
from dataclasses import asdict
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
import numpy as np

# Allow invocation as python scripts/test_browser.py from the checkout root.
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tunnel_resistivity.browser import DEFAULT_PARAMETERS, browser_plan
from tunnel_resistivity.survey_simulation import run_survey_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir',type=Path,default=ROOT/'outputs/site')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/browser-tests')
    parser.add_argument('--url')
    parser.add_argument('--chromium')
    args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    server=None
    if args.url:url=args.url
    else:
        site=args.site_dir.resolve()
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self,*unused):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(site.parent)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        # Test under a path prefix, as on project GitHub Pages, not only at /.
        url=f'http://127.0.0.1:{server.server_port}/{site.name}/'
    checks=[];errors=[];requests=[];timings={}
    def passed(name):checks.append(name);print('PASS:',name,flush=True)
    expected=run_survey_plan(browser_plan(asdict(DEFAULT_PARAMETERS),'Air-filled')).data.records()
    started=time.perf_counter()
    try:
      with sync_playwright() as playwright:
        executable=args.chromium or (None if os.environ.get('CI') else shutil.which('chromium'))
        browser=playwright.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000},locale='en-US',accept_downloads=True)
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda request:requests.append({'url':request.url,'method':request.method,'resource':request.resource_type}))
        page.on('websocket',lambda socket:errors.append('Unexpected backend WebSocket: '+socket.url))
        def ready():
            page.wait_for_function("document.querySelector('#status').dataset.state==='error' || (document.querySelector('#status').dataset.state==='ready' && document.querySelector('#status').textContent.startsWith('Simulation complete'))",timeout=300000)
            assert page.locator('#status').get_attribute('data-state')=='ready',page.locator('#status').inner_text()
        def rows():
            with page.expect_download(timeout=30000) as d:page.locator('#csv').click()
            dest=out/d.value.suggested_filename;d.value.save_as(str(dest))
            return list(csv.DictReader(io.StringIO(dest.read_text())))
        def number(key,value):page.locator('#'+key).fill(str(value))
        def range_value(key,value):
            page.locator('#'+key).evaluate('(element,value)=>{element.value=value;element.dispatchEvent(new Event("input",{bubbles:true}));}',str(value))
        try:
            response=page.goto(url,wait_until='domcontentloaded');assert response.status==200
            ready();timings['cold_initial_survey_seconds']=time.perf_counter()-started
            assert len(page.workers)==1 and urlparse(page.workers[0].url).path.endswith('/worker.js')
            assert urlparse(page.workers[0].url).query.startswith('v=')
            assert page.locator('#field_plots img').count()==4
            for actual,wanted in zip(rows(),expected):
                for key in ('voltage_v','apparent_resistivity_ohm_m'):
                    assert np.isclose(float(actual[key]),wanted[key],rtol=1e-7,atol=1e-10),(key,actual[key],wanted[key])
            assert len(rows())==len(expected)==5
            passed('Real WebAssembly worker solves nonzero air survey and matches native production results')
            # Reuse three original independent numerical tests inside Pyodide.
            source=(ROOT/'tests/test_solver_2p5d.py').read_text()
            result=page.workers[0].evaluate('''source => {
                runtime.globals.set('_original_tests',source);
                return JSON.parse(runtime.runPython(`
import unittest, io
_wasm_namespace={'__name__':'wasm_original_numerical_tests'}
exec(_original_tests, _wasm_namespace)
_wasm_names=['test_fourier_normalization_against_known_bessel_integral','test_forced_fourier_mode_second_order_spatial_convergence','test_piecewise_conductivity_harmonic_flux_and_boundaries']
_wasm_suite=unittest.TestSuite([_wasm_namespace['IndependentNumericalChecks'](name) for name in _wasm_names])
_wasm_stream=io.StringIO()
_wasm_result=unittest.TextTestRunner(stream=_wasm_stream,verbosity=2).run(_wasm_suite)
json.dumps({'run':_wasm_result.testsRun,'passed':_wasm_result.wasSuccessful(),'log':_wasm_stream.getvalue()})
`));
            }''',source)
            assert result['passed'] and result['run']==3,result
            (out/'wasm_numerical_tests.json').write_text(json.dumps(result,indent=2)+'\n')
            passed('Original Fourier identity, manufactured convergence and harmonic-interface tests pass inside WebAssembly')
            page.locator('#field_plots').scroll_into_view_if_needed();page.screenshot(path=str(out/'desktop.png'))
            with page.expect_download(timeout=30000) as d:page.locator('#png').click()
            image=out/d.value.suggested_filename;d.value.save_as(str(image));assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            passed('Four field maps and downloadable PNG are real Matplotlib output')
            page.locator('#profile').scroll_into_view_if_needed()
            page.wait_for_function("document.querySelector('#profile').complete && document.querySelector('#profile').naturalWidth>0")
            profile_width=page.locator('#profile').bounding_box()['width']
            field_width=page.locator('#field_plots img').first.bounding_box()['width']
            assert abs(profile_width-field_width)<4,(profile_width,field_width)
            page.screenshot(path=str(out/'compact_profile.png'))
            page.locator('#profile_link').click();assert page.locator('#figure_dialog').is_visible()
            page.locator('#figure_close').click()
            passed('Apparent-resistivity profile matches a field-map width and still enlarges on tap')
            page.locator('#field_plots a').first.click()
            assert page.locator('#figure_dialog').is_visible()
            page.locator('#figure_zoom').click()
            assert 'actual_size' in page.locator('#figure_detail').get_attribute('class')
            page.locator('#figure_close').click()
            assert not page.locator('#figure_dialog').is_visible()
            passed('Figure dialog opens, enlarges labels and closes without blocked data-URL navigation')
            page.locator('#electrode_count').focus();page.locator('#electrode_count').press('Home');ready()
            page.locator('#material').select_option('Water-filled');ready()
            water=rows();assert float(water[0]['tunnel_resistivity_ohm_m'])==5
            assert any(abs(float(r['apparent_resistivity_ohm_m'])-100)>1e-6 for r in water)
            passed('Water preset computes a different nonzero response')
            page.locator('#snapshot').select_option(index=1)
            assert float(rows()[0]['tunnel_resistivity_ohm_m'])==1e8
            page.locator('#snapshot').select_option(index=0)
            assert float(rows()[0]['tunnel_resistivity_ohm_m'])==5
            passed('Latest/Previous snapshots retain correct fields and CSV settings')
            page.locator('#material').select_option('Custom');number('tunnel_resistivity',100);ready()
            assert all(abs(float(r['apparent_resistivity_ohm_m'])-100)<1e-9 for r in rows())
            assert 'secondary receiver voltage=0 V' in page.locator('#field_info').inner_text()
            passed('Custom homogeneous model recovers host resistivity and zero secondary voltage')
            page.locator('#material').select_option('Water-filled')
            page.wait_for_function("document.body.dataset.busy==='true'",timeout=30000)
            ticks=page.evaluate('''()=>new Promise(resolve=>{let ticks=0;const end=performance.now()+600;function tick(){ticks++;if(performance.now()<end)requestAnimationFrame(tick);else resolve(ticks);}requestAnimationFrame(tick);})''')
            assert ticks>=3,ticks
            range_value('depth_m',22);range_value('radius_m',5.5);number('host_resistivity',200)
            ready();latest=rows()[0]
            assert float(latest['tunnel_depth_m'])==22 and float(latest['tunnel_radius_m'])==5.5 and float(latest['host_resistivity_ohm_m'])==200
            passed('Main UI remains responsive during Python work; rapid edits publish only latest settings')
            range_value('electrode_count',7);page.locator('#array_type').select_option('schlumberger');range_value('receiver_spacing_steps',2);ready()
            assert all(int(r['receiver_spacing_steps'])==2 for r in rows())
            passed('Schlumberger spacing reaches the same numerical backend')
            page.locator('#array_type').select_option('dipole-dipole');range_value('dipole_spacing_steps',2);ready()
            before=rows();assert all(float(r['geometric_factor_m'])<0 for r in before)
            number('current_a',.2);ready();after=rows()
            for a,b in zip(before,after):
                assert np.isclose(float(b['voltage_v']),2*float(a['voltage_v']),rtol=1e-7)
                assert np.isclose(float(b['apparent_resistivity_ohm_m']),float(a['apparent_resistivity_ohm_m']),rtol=1e-7)
            passed('Dipole spacing, signed factors and current/voltage scaling work in WebAssembly')
            page.locator('summary',has_text='Grid & domain').click();page.locator('#grid_mode').select_option('Manual');number('x_max_m',-40)
            page.wait_for_function("document.querySelector('#status').dataset.state==='error'",timeout=30000)
            assert page.locator('#csv').is_disabled() and page.locator('#png').is_disabled()
            passed('Invalid grid is rejected and stale exports are disabled')
            page.locator('#reset').click();ready()
            assert page.locator('#electrode_count').input_value()=='7'
            page.locator('#measurement').select_option(index=0);ready()
            assert 'Measurement 1:' in page.locator('#field_info').inner_text()
            passed('Reset and measurement selection update the fields correctly')
            # Reproduce the reported live-site failure: 12 electrodes, 6 m pitch,
            # two Wenner levels, then edit the material again after completion.
            page.locator('#automatic').uncheck()
            range_value('electrode_count',12);range_value('electrode_spacing_m',6);range_value('max_level',2)
            page.locator('#material').select_option('Water-filled')
            page.locator('#automatic').check();ready()
            large=rows()
            assert len(large)==15 and len({r['source_pair_id'] for r in large})==15
            assert all(float(r['tunnel_resistivity_ohm_m'])==5 for r in large)
            assert '12 electrodes, 6 m pitch, levels 1–2' in page.locator('#scenario_info').inner_text()
            page.screenshot(path=str(out/'twelve_electrode_water.png'))
            page.locator('#material').select_option('Custom');number('tunnel_resistivity',100);ready()
            assert all(abs(float(r['apparent_resistivity_ohm_m'])-100)<1e-9 for r in rows())
            passed('Reported 15-source survey runs without changing requested geometry and remains editable')
            # Exercise the actual slider maximum and all 64 electrodes. A coarse
            # explicit manual grid keeps this scale/interaction test fast; it is
            # not an accuracy benchmark for that grid. Existing tests cover the PDE.
            page.locator('#automatic').uncheck()
            page.locator('#array_type').select_option('wenner')
            page.locator('#electrode_count').focus();page.locator('#electrode_count').press('End')
            assert page.locator('#electrode_count').input_value()=='64'
            range_value('electrode_spacing_m',5);range_value('max_level',1)
            page.locator('#grid_mode').select_option('Manual')
            number('x_min_m',-30);number('x_max_m',405);number('height_m',80);number('nx',64);number('nz',24)
            page.locator('#material').select_option('Water-filled')
            page.locator('#automatic').check();ready()
            sixty_four=rows()
            assert len(sixty_four)==61
            assert all(int(r['physical_electrode_count'])==64 for r in sixty_four)
            assert max(int(r[key]) for r in sixty_four for key in ('a_index','b_index','m_index','n_index'))==63
            assert any(abs(float(r['apparent_resistivity_ohm_m'])-100)>1e-6 for r in sixty_four)
            page.screenshot(path=str(out/'sixty_four_electrodes.png'))
            page.locator('#material').select_option('Custom');number('tunnel_resistivity',100)
            page.locator('#array_type').select_option('dipole-dipole');range_value('max_level',2);ready()
            full=rows()
            assert len(full)==121
            assert all(abs(float(r['apparent_resistivity_ohm_m'])-100)<1e-9 for r in full)
            passed('64-electrode slider runs a nonzero survey and preserves all 121 two-level dipole data')
            # A real stop terminates the worker; no SharedArrayBuffer/COOP headers are required.
            range_value('depth_m',20);page.wait_for_function("document.body.dataset.busy==='true'",timeout=30000)
            page.locator('#stop').click()
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Python is ready.')",timeout=180000)
            assert not page.locator('#automatic').is_checked()
            assert page.locator('#result_content').is_hidden()
            passed('Stop terminates computation, reloads Python and pauses automatic work')
            context.close()
            # A fresh phone-sized context also loads Python and runs a calculation.
            mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,locale='en-US')
            page=mobile.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url,wait_until='domcontentloaded')
            range_value('electrode_count',4)
            ready()
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            assert page.locator('#field_plots img').count()==4
            page.locator('#profile').scroll_into_view_if_needed()
            page.wait_for_function("document.querySelector('#profile').complete && document.querySelector('#profile').naturalWidth>0")
            assert abs(page.locator('#profile').bounding_box()['width']-page.locator('#field_plots img').first.bounding_box()['width'])<4
            page.locator('#field_plots').scroll_into_view_if_needed();page.screenshot(path=str(out/'phone.png'))
            passed('Fresh 390px phone context computes in a worker with no page overflow')
            mobile.close();browser.close()
        except:
            if not page.is_closed():
                print('FAILED STATUS:',page.locator('#status').inner_text(),flush=True)
                page.screenshot(path=str(out/'failure.png'))
            raise
        assert not errors,errors
        assert not any(r['method']!='GET' for r in requests),requests
        assert all(r['url'].startswith(url) or r['url'].startswith(('data:','blob:')) for r in requests),requests
        passed('No backend requests, WebSockets, remote runtime dependency or JavaScript errors')
    finally:
        if server:server.shutdown();server.server_close()
        (out/'report.json').write_text(json.dumps({'url':url,'checks':checks,'errors':errors,'timings':timings,'requests':requests},indent=2)+'\n')
    print('Completed',len(checks),'browser checks',flush=True)


if __name__=='__main__':main()
