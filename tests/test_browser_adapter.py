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

from tunnel_resistivity.browser import (BrowserEngine, DEFAULT_PARAMETERS, MAX_BROWSER_ELECTRODES,
                                      MAX_BROWSER_SOURCES, MAX_BROWSER_MEASUREMENTS, browser_plan)
from tunnel_resistivity.survey import generate_survey
from tunnel_resistivity.survey_simulation import SurveyParameters, plan_simulation, run_survey_plan


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

    def test_browser_rejects_more_than_64_physical_electrodes(self):
        p=asdict(DEFAULT_PARAMETERS);p.update(electrode_count=65)
        with self.assertRaisesRegex(ValueError,'64 physical electrodes'):browser_plan(p,'Air-filled')

    def test_sixty_four_electrodes_plan_for_all_arrays_without_truncation(self):
        expected={'wenner':119,'schlumberger':120,'dipole-dipole':121}
        for kind,count in expected.items():
            p=asdict(DEFAULT_PARAMETERS);p.update(electrode_count=64,array_type=kind)
            with self.subTest(array=kind):
                plan=browser_plan(p,'Water-filled')
                self.assertEqual(len(plan.survey.electrode_positions_x_m),64)
                self.assertEqual(plan.survey.electrode_positions_x_m[-1],345)
                self.assertEqual(len(plan.survey.measurements),count)
                self.assertLessEqual(plan.grid.cell_count,32768)
                self.assertGreater(plan.grid.x_max_m,345)

    def test_browser_measurement_budget_does_not_change_desktop_default(self):
        p=asdict(DEFAULT_PARAMETERS);p.update(electrode_count=64,array_type='dipole-dipole')
        with self.assertRaisesRegex(ValueError,'120 measurements'):plan_simulation(SurveyParameters(**p))
        self.assertEqual(len(browser_plan(p,'Custom').survey.measurements),121)
        with self.assertRaises(ValueError):plan_simulation(SurveyParameters(),max_measurements=0)

    def test_four_level_64_electrode_survey_preserves_all_measurements(self):
        p=asdict(DEFAULT_PARAMETERS)
        p.update(electrode_count=64,array_type='schlumberger',max_level=4,
                 grid_mode='Manual',x_min_m=-30,x_max_m=400,nx=128,nz=64)
        plan=browser_plan(p,'Water-filled')
        self.assertEqual(len(plan.survey.measurements),232)
        self.assertEqual(plan.survey.unique_source_pair_count,232)

    def test_reported_twelve_electrode_survey_keeps_requested_geometry(self):
        p=asdict(DEFAULT_PARAMETERS);p.update(electrode_count=12,electrode_spacing_m=6,max_level=2)
        plan=browser_plan(p,'Water-filled')
        self.assertEqual(plan.survey.unique_source_pair_count,15)
        self.assertEqual(len(plan.survey.measurements),15)
        self.assertEqual(plan.parameters.electrode_count,12)
        self.assertEqual(plan.parameters.electrode_spacing_m,6)
        self.assertEqual(plan.parameters.max_level,2)
        self.assertEqual(plan.parameters.tunnel_resistivity,5)

    def test_source_budget_covers_every_offered_array_spacing_combination(self):
        largest=0
        for count in range(4,MAX_BROWSER_ELECTRODES+1):
            for kind in ('wenner','schlumberger','dipole-dipole'):
                for receiver in (range(1,min(4,count-3)+1) if kind=='schlumberger' else (1,)):
                    for dipole in (range(1,min(3,(count-1)//3)+1) if kind=='dipole-dipole' else (1,)):
                        for level in range(1,5):
                            try:
                                survey=generate_survey(kind,electrode_count=count,levels=range(1,level+1),
                                    receiver_spacing_steps=receiver,dipole_spacing_steps=dipole)
                            except ValueError:continue  # Geometrically impossible combinations are hidden by the UI.
                            largest=max(largest,survey.unique_source_pair_count)
                            self.assertLessEqual(survey.unique_source_pair_count,MAX_BROWSER_SOURCES)
                            self.assertLessEqual(len(survey.measurements),MAX_BROWSER_MEASUREMENTS)
        self.assertEqual(largest,232)


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
            self.assertIn('app.js?v='+config['assetVersion'],(output/'index.html').read_text())

    def test_build_refuses_checkout_root(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('build_pages',root/'scripts/build_pages.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with self.assertRaises(ValueError):builder.build(root)
