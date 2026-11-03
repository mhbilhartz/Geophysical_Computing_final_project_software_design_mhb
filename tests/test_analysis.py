"""Regression checks for analysis metrics and the domain-comparison controls."""

from dataclasses import replace
import unittest

import numpy as np

from analysis.run_experiments import Case, solve_case, summarize


class AnalysisTests(unittest.TestCase):
    def test_matched_material_has_no_meaningful_peak_location(self):
        case=Case(nx=80,nz=40,tunnel_resistivity_ohm_m=100)
        model,reference,mask=solve_case(case,{})
        record,surface=summarize(case,model,reference,mask)
        np.testing.assert_allclose(surface,0,atol=1e-13,rtol=0)
        self.assertIsNone(record['positive_peak_offset_m'])
        self.assertIsNone(record['negative_peak_offset_m'])
        self.assertIsNone(record['outer_half_amplitude_span_m'])

    def test_absolute_resistivity_scaling_preserves_potential_and_halves_current(self):
        case=Case(nx=80,nz=40,tunnel_resistivity_ohm_m=5)
        model,reference,mask=solve_case(case,{})
        scaled_case=replace(case,host_resistivity_ohm_m=200,tunnel_resistivity_ohm_m=10)
        scaled,scaled_reference,scaled_mask=solve_case(scaled_case,{})
        np.testing.assert_allclose(scaled.potential,model.potential,atol=1e-12,rtol=0)
        np.testing.assert_allclose(scaled.jx,model.jx/2,atol=1e-14,rtol=0)
        a,_=summarize(case,model,reference,mask)
        b,_=summarize(scaled_case,scaled,scaled_reference,scaled_mask)
        self.assertAlmostEqual(a['surface_abs_peak_V'],b['surface_abs_peak_V'],places=12)

    def test_domain_controls_keep_grid_spacing_and_reject_mismatched_reference(self):
        case=Case(nx=80,nz=40)
        wider=replace(case,width_m=200,nx=160,center_x_m=100)
        cache={}
        m,ref,mask=solve_case(case,cache)
        wide,wide_ref,wide_mask=solve_case(wider,cache)
        self.assertEqual(m.dx,wide.dx)
        self.assertEqual(m.dz,wide.dz)
        a,_=summarize(case,m,ref,mask)
        b,_=summarize(wider,wide,wide_ref,wide_mask)
        self.assertEqual(a['applied_gradient_V_m'],2*b['applied_gradient_V_m'])
        self.assertAlmostEqual(b['surface_peak_over_applied_gradient_m'],b['surface_abs_peak_V']/0.005)
        with self.assertRaises(ValueError):
            summarize(case,m,wide_ref,mask)


if __name__=='__main__':
    unittest.main()
