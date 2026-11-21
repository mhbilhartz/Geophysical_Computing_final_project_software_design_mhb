"""Survey geometry, actual forward data, per-run reuse, and scalar exports."""
from dataclasses import FrozenInstanceError, replace
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tunnel_resistivity.electrodes import ElectrodeArray, schlumberger, dipole_dipole
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.receivers import measure_receivers
from tunnel_resistivity.solver_2p5d import solve_source_pair
from tunnel_resistivity.survey import Survey, SurveyMeasurement, generate_survey, forward_survey, export_survey_csv

KINDS=('wenner','schlumberger','dipole-dipole')


class SurveyGeometryTests(unittest.TestCase):
    def test_wenner_all_valid_translations_and_independent_counts(self):
        plan=generate_survey('wenner',electrode_count=10,levels=(1,2,3))
        self.assertEqual(len(plan.measurements),(10-3)+(10-6)+(10-9))
        for level in (1,2,3):
            selected=[m for m in plan.measurements if m.level==level]
            self.assertEqual([m.electrode_indices for m in selected],
                             [(i,i+3*level,i+level,i+2*level) for i in range(10-3*level)])
            for m in selected:
                self.assertEqual(np.diff(sorted(m.electrodes.positions_x_m.values())).tolist(),[level*5]*3)

    def test_schlumberger_receiver_spacing_and_expanding_sources(self):
        plan=generate_survey('schlumberger',electrode_count=10,levels=(1,2,3),receiver_spacing_steps=2)
        self.assertEqual(len(plan.measurements),sum(10-(2*level+2) for level in (1,2,3)))
        for m in plan.measurements:
            e=m.electrodes
            self.assertEqual(e.n_x_m-e.m_x_m,10)
            self.assertEqual(e.m_x_m-e.a_x_m,m.level*5)
            self.assertEqual(e.b_x_m-e.n_x_m,m.level*5)
            self.assertEqual((e.a_x_m+e.b_x_m)/2,(e.m_x_m+e.n_x_m)/2)

    def test_dipole_dipole_n_and_independent_dipole_spacing(self):
        plan=generate_survey('dipole-dipole',electrode_count=12,levels=(1,2,3),dipole_spacing_steps=2)
        self.assertEqual(len(plan.measurements),sum(12-(n+2)*2 for n in (1,2,3)))
        for m in plan.measurements:
            e=m.electrodes
            self.assertEqual(e.b_x_m-e.a_x_m,10)
            self.assertEqual(e.n_x_m-e.m_x_m,10)
            self.assertEqual(e.m_x_m-e.b_x_m,m.level*10)
        self.assertEqual(plan.unique_source_pair_count,6)

    def test_requested_order_and_decimal_coordinates_are_preserved(self):
        plan=generate_survey('dipole-dipole',line_start_x_m=-10.123,electrode_spacing_m=.3,levels=(2,1))
        self.assertEqual([m.level for m in plan.measurements],[2]*5+[1]*6)
        for m in plan.measurements:
            for index,x in zip(m.electrode_indices,m.electrodes.positions_x_m.values()):
                self.assertEqual(x,plan.electrode_positions_x_m[index])
        self.assertEqual(plan.unique_source_pair_count,6)
        shifted=generate_survey('dipole-dipole',line_start_x_m=9.877,electrode_spacing_m=.3,levels=(2,1))
        np.testing.assert_allclose(np.array(shifted.electrode_positions_x_m)-plan.electrode_positions_x_m,20)

    def test_invalid_common_parameters(self):
        for name,values in (('electrode_count',(3,1002,9.,True,None)),
                            ('electrode_spacing_m',(0,-1,np.nan,np.inf,True,'5')),
                            ('current_a',(0,-1,np.inf,True)),('line_start_x_m',(np.nan,np.inf,True))):
            for value in values:
                with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                    generate_survey('wenner',**{name:value})
        with self.assertRaises(ValueError):generate_survey('other')
        with self.assertRaises(ValueError):generate_survey('wenner',line_start_x_m=1e20,electrode_spacing_m=1e-6)
        with self.assertRaises(ValueError):generate_survey('wenner',electrode_spacing_m=1e308)

    def test_invalid_levels_and_irrelevant_spacing_controls(self):
        for levels in ((),(1,1),(0,),(-1,),(1.,),(True,),None,1):
            with self.subTest(levels=levels),self.assertRaises(ValueError):generate_survey('wenner',levels=levels)
        for kind,kwargs in (('wenner',{'receiver_spacing_steps':2}),
                            ('wenner',{'dipole_spacing_steps':2}),
                            ('schlumberger',{'receiver_spacing_steps':0}),
                            ('dipole-dipole',{'dipole_spacing_steps':1.5})):
            with self.subTest(kind=kind,kwargs=kwargs),self.assertRaises(ValueError):generate_survey(kind,**kwargs)

    def test_oversized_levels_are_rejected_instead_of_silently_omitted(self):
        for kind in KINDS:
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'requires'):
                generate_survey(kind,electrode_count=4,levels=(1,2))
            self.assertEqual(len(generate_survey(kind,electrode_count=4,levels=(1,)).measurements),1)

    def test_physical_line_and_padding_domain_validation(self):
        plan=generate_survey('wenner')
        plan.validate_domain(0,100,boundary_padding_m=30)
        for bounds in ((30,100,0),(0,70,0),(0,100,31),(100,0,0),(0,np.inf,0),(0,100,-1)):
            with self.subTest(bounds=bounds),self.assertRaises(ValueError):
                plan.validate_domain(bounds[0],bounds[1],boundary_padding_m=bounds[2])

    def test_malformed_plan_indices_and_coordinates_rejected(self):
        plan=generate_survey('wenner');entry=plan.measurements[0]
        for indices in ((0,0,1,2),(0,3,1),(-1,3,1,2)):
            with self.assertRaises(ValueError):SurveyMeasurement(1,indices,entry.electrodes)
        for positions,measurements in ((plan.electrode_positions_x_m,()),
                                       ((0,0,1,2),(entry,)),
                                       (plan.electrode_positions_x_m,(None,)),
                                       (plan.electrode_positions_x_m,(replace(entry,electrode_indices=(0,99,1,2)),)),
                                       (tuple(x+1 for x in plan.electrode_positions_x_m),(entry,))):
            with self.assertRaises(ValueError):Survey(positions,measurements)

    def test_plans_are_immutable(self):
        plan=generate_survey('wenner')
        with self.assertRaises(FrozenInstanceError):plan.measurements=()
        with self.assertRaises(FrozenInstanceError):plan.measurements[0].level=3
        self.assertIsInstance(plan.measurements,tuple)
        self.assertIsInstance(plan.electrode_positions_x_m,tuple)


class SurveyForwardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans={kind:generate_survey(kind,electrode_count=7,line_start_x_m=35,levels=(1,2)) for kind in KINDS}
        cls.sigma={};cls.results={}
        for material,rho in (('air',1e8),('water',5.)):
            sigma,_=circular_tunnel(nx=80,nz=40,host_resistivity=100,tunnel_resistivity=rho)
            cls.sigma[material]=sigma
            for kind,plan in cls.plans.items():cls.results[material,kind]=forward_survey(sigma,plan)

    def test_homogeneous_all_arrays_and_resistivities(self):
        for rho in (10.,100.,1000.):
            for kind,plan in self.plans.items():
                with self.subTest(rho=rho,kind=kind):
                    result=forward_survey(np.full((10,20),1/rho),plan,n_wavenumbers=8)
                    np.testing.assert_allclose([m.apparent_resistivity_ohm_m for m in result.measurements],rho,rtol=1e-12)
                    self.assertTrue(all(m.secondary_voltage_v==0 for m in result.measurements))
                    if kind=='dipole-dipole':
                        self.assertTrue(all(m.voltage_v<0 and m.geometric_factor_m<0 for m in result.measurements))

    def test_actual_air_water_models_finite_and_conserved(self):
        for (material,kind),result in self.results.items():
            with self.subTest(material=material,kind=kind):
                self.assertEqual(len(result.measurements),len(result.survey.measurements))
                self.assertEqual(result.solve_count,result.survey.unique_source_pair_count)
                self.assertEqual(sum(s.measurement_count for s in result.source_diagnostics),len(result.measurements))
                self.assertLess(result.max_relative_mode_residual,1e-9)
                self.assertLess(result.max_relative_mode_balance_error,1e-9)
                self.assertTrue(all(np.isfinite(m.apparent_resistivity_ohm_m) for m in result.measurements))
        # The central level-2 Wenner case has A=35,B=65,M=45,N=55.
        self.assertGreater(self.results['air','wenner'].measurements[-1].apparent_resistivity_ohm_m,100)
        self.assertLess(self.results['water','wenner'].measurements[-1].apparent_resistivity_ohm_m,100)

    def test_matches_independent_single_measurement_calls_at_each_level(self):
        for kind,plan in self.plans.items():
            for level in (1,2):
                index=next(i for i,m in enumerate(plan.measurements) if m.level==level)
                array=plan.measurements[index].electrodes
                direct=measure_receivers(solve_source_pair(self.sigma['water'],array))
                grouped=self.results['water',kind].measurements[index]
                for name in ('potential_m_v','potential_n_v','voltage_v','secondary_voltage_v',
                             'geometric_factor_m','apparent_resistivity_ohm_m'):
                    with self.subTest(kind=kind,level=level,quantity=name):
                        self.assertAlmostEqual(getattr(grouped,name),getattr(direct,name),places=11)

    def test_actual_source_reuse_and_requested_output_order(self):
        plan=generate_survey('dipole-dipole',electrode_count=7,line_start_x_m=35,levels=(2,1))
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as wrapped:
            result=forward_survey(self.sigma['water'],plan)
        self.assertEqual(wrapped.call_count,4)
        self.assertEqual(len(result.measurements),7)
        self.assertEqual(result.solve_count,4)
        for planned,datum in zip(plan.measurements,result.measurements):self.assertEqual(planned.electrodes,datum.electrodes)
        self.assertEqual([r['level'] for r in result.records()],[2]*3+[1]*4)

    def test_no_stale_fields_when_conductivity_changes_between_runs(self):
        plan=self.plans['dipole-dipole'];sigma=np.full((10,20),.01)
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as wrapped:
            first=forward_survey(sigma,plan,n_wavenumbers=8)
            sigma[:]=.02
            second=forward_survey(sigma,plan,n_wavenumbers=8)
        self.assertEqual(wrapped.call_count,2*plan.unique_source_pair_count)
        self.assertNotEqual(first.conductivity_sha256,second.conductivity_sha256)
        np.testing.assert_allclose([m.apparent_resistivity_ohm_m for m in first.measurements],100)
        np.testing.assert_allclose([m.apparent_resistivity_ohm_m for m in second.measurements],50)

    def test_current_is_part_of_reuse_key_and_schlumberger_receivers_can_share_sources(self):
        line=tuple(float(x) for x in range(35,66,5))
        first=schlumberger(center_x_m=50,ab_half_spacing_m=15,mn_half_spacing_m=5,current_a=.5)
        second=schlumberger(center_x_m=50,ab_half_spacing_m=15,mn_half_spacing_m=10,current_a=.5)
        plan=Survey(line,(SurveyMeasurement(1,(0,6,2,4),first),SurveyMeasurement(1,(0,6,1,5),second),
                          SurveyMeasurement(1,(0,6,2,4),replace(first,current_a=1.))))
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as wrapped:
            result=forward_survey(self.sigma['water'],plan)
        self.assertEqual(wrapped.call_count,2)
        a,b,c=result.measurements
        self.assertAlmostEqual(c.voltage_v,2*a.voltage_v)
        self.assertAlmostEqual(c.apparent_resistivity_ohm_m,a.apparent_resistivity_ohm_m)
        self.assertNotAlmostEqual(a.voltage_v,b.voltage_v)

    def test_geometry_and_factors_preflight_before_any_source_solve(self):
        plan=self.plans['wenner']
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as wrapped:
            for kwargs in ({'width':65},{'boundary_padding_m':36},{'x_origin_m':100}):
                with self.assertRaises(ValueError):forward_survey(self.sigma['water'],plan,**kwargs)
            distant=dipole_dipole(center_x_m=50000001,spacing_m=1,separation_n=10**8)
            positions=tuple(sorted(distant.positions_x_m.values()))
            unresolved=Survey(positions,(SurveyMeasurement(1,(0,1,2,3),distant),))
            with self.assertRaisesRegex(ValueError,'degenerate'):
                forward_survey(self.sigma['water'],unresolved,width=2e8,x_origin_m=-1)
        self.assertEqual(wrapped.call_count,0)

    def test_invalid_model_or_solver_parameters(self):
        plan=self.plans['wenner']
        for sigma in (np.ones(4),np.zeros((4,4)),np.full((4,4),np.nan),np.full((4,4),np.inf),np.full((4,4),1j)):
            with self.subTest(shape=np.shape(sigma)),self.assertRaises(ValueError):forward_survey(sigma,plan)
        for kwargs in ({'width':0},{'height':0},{'x_origin_m':np.nan},{'background_conductivity':0},
                       {'n_wavenumbers':7},{'k_min':0},{'k_max':np.inf}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):forward_survey(self.sigma['water'],plan,**kwargs)
        with self.assertRaises(ValueError):forward_survey(self.sigma['water'],None)

    def test_translated_domain_preserves_data_and_explicit_spectral_settings(self):
        original=self.results['water','dipole-dipole']
        shifted_plan=generate_survey('dipole-dipole',electrode_count=7,line_start_x_m=-65,levels=(1,2))
        result=forward_survey(self.sigma['water'],shifted_plan,x_origin_m=-100,n_wavenumbers=64,k_min=1e-8,k_max=16.)
        np.testing.assert_allclose([m.voltage_v for m in result.measurements],
                                   [m.voltage_v for m in original.measurements],rtol=1e-12,atol=1e-12)
        self.assertEqual((result.k_min_per_m,result.k_max_per_m,result.n_wavenumbers),(1e-8,16.,64))
        self.assertEqual(result.x_origin_m,-100)

    def test_csv_has_complete_ordered_signed_data_and_provenance(self):
        result=self.results['water','dipole-dipole']
        with tempfile.TemporaryDirectory() as directory:
            path=export_survey_csv(result,Path(directory)/'nested/survey.csv')
            with path.open() as handle:rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),len(result.measurements))
        for i,(row,planned,datum) in enumerate(zip(rows,result.survey.measurements,result.measurements),1):
            self.assertEqual(int(row['measurement_id']),i)
            self.assertEqual(float(row['a_x_m']),planned.electrodes.a_x_m)
            self.assertEqual(float(row['m_x_m']),planned.electrodes.m_x_m)
            self.assertEqual(int(row['level']),planned.level)
            self.assertAlmostEqual(float(row['apparent_resistivity_ohm_m']),datum.apparent_resistivity_ohm_m)
            self.assertLess(float(row['geometric_factor_m']),0)
            self.assertLess(float(row['voltage_v']),0)
            self.assertEqual(row['conductivity_sha256'],result.conductivity_sha256)
        json.dumps(result.records())  # Standard-library serializable scalars.
        with self.assertRaises(ValueError):export_survey_csv(None,'unused.csv')


if __name__=='__main__':unittest.main()
