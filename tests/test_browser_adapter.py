"""Production-backed worker adapter and static artifact contract checks."""
import base64
import csv
from dataclasses import asdict
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tunnel_resistivity.browser import BrowserEngine, DEFAULT_PARAMETERS, browser_plan
from tunnel_resistivity.survey_simulation import run_survey_plan


class BrowserPlanTests(unittest.TestCase):
    def test_presets_are_authoritative_and_geometry_is_validated(self):
        p=asdict(DEFAULT_PARAMETERS);p['tunnel_resistivity']=5
        self.assertEqual(browser_plan(p,'Air-filled').parameters.tunnel_resistivity,1e8)
        p['tunnel_resistivity']=100
        self.assertEqual(browser_plan(p,'Custom').parameters.tunnel_resistivity,100)
        for key,value in [('host_resistivity',0),('tunnel_resistivity',float('inf')),('depth_m',1)]:
            bad={**p,key:value}
            with self.subTest(key=key),self.assertRaises((ValueError,TypeError)):browser_plan(bad,'Custom')
        with self.assertRaises(ValueError):browser_plan(p,'unknown')

    def test_browser_grid_budget_rejects_without_coarsening(self):
        p=asdict(DEFAULT_PARAMETERS)
        p.update(grid_mode='Manual',nx=257,nz=128)
        with self.assertRaisesRegex(ValueError,'32,768'):browser_plan(p,'Air-filled')

    def test_browser_source_budget_rejects_broad_survey(self):
        p=asdict(DEFAULT_PARAMETERS);p.update(electrode_count=13,max_level=3)
        with self.assertRaisesRegex(ValueError,'source solves'):browser_plan(p,'Air-filled')


class BrowserEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=BrowserEngine()
        cls.parameters=asdict(DEFAULT_PARAMETERS)
        cls.parameters.update(electrode_count=4,max_level=1,tunnel_resistivity=100)
        cls.result=cls.engine.survey(1,cls.parameters,'Custom')

    def test_worker_payload_matches_production_and_contains_real_plots(self):
        result=self.result
        native=run_survey_plan(browser_plan(self.parameters,'Custom'))
        self.assertAlmostEqual(result['records'][0]['voltage_v'],native.data.measurements[0].voltage_v,places=12)
        self.assertAlmostEqual(result['records'][0]['apparent_resistivity_ohm_m'],100,places=11)
        field=result['field']
        self.assertEqual(field['secondary_voltage_v'],0.)
        self.assertEqual(len(field['panels']),4)
        for image in [result['profile'],*field['panels'],field['png'],field['surface'],field['survey_map']]:
            self.assertTrue(base64.b64decode(image.split(',',1)[1]).startswith(b'\x89PNG\r\n\x1a\n'))
        rows=list(csv.DictReader(io.StringIO(result['csv'])))
        self.assertEqual(float(rows[0]['tunnel_resistivity_ohm_m']),100)
        self.assertIn('scipy_version',rows[0])

    def test_progress_and_retention_preserve_only_completed_owners(self):
        events=[];engine=BrowserEngine()
        engine.results[2]=self.engine.results[1]
        field=engine.field(2,0,progress=events.append)
        self.assertEqual(field['identifier'],2)
        self.assertTrue(events)
        engine.retain([])
        self.assertFalse(engine.results)
        self.assertEqual(len(engine.fields),0)
        with self.assertRaises(ValueError):engine.field(2,0)
        with self.assertRaises(ValueError):engine.handle({'kind':'unknown'})


class StaticBuildTests(unittest.TestCase):
    def test_artifact_has_only_allowlisted_python_and_relative_assets(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('build_pages',root/'scripts/build_pages.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'site';config=builder.build(output)
            with zipfile.ZipFile(output/'python.zip') as archive:
                self.assertEqual(len(archive.namelist()),len(builder.MODULES))
                self.assertNotIn('tunnel_resistivity/survey_app.py',archive.namelist())
                for name in archive.namelist():self.assertEqual(archive.read(name),(root/name).read_bytes())
            self.assertEqual(config['pythonZipSha256'],hashlib.sha256((output/'python.zip').read_bytes()).hexdigest())
            self.assertTrue((output/'.nojekyll').exists())
            self.assertIn('worker.js',(output/'app.js').read_text())
            self.assertEqual(json.loads((output/'runtime-config.json').read_text())['pyodideVersion'],'0.27.7')

    def test_build_refuses_checkout_root(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('build_pages',root/'scripts/build_pages.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with self.assertRaises(ValueError):builder.build(root)
