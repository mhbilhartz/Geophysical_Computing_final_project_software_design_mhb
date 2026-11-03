"""Executed A–F physics regressions; no new analytical verification notebook."""

from dataclasses import asdict, replace
import unittest

import numpy as np

from tunnel_resistivity.simulation import SimulationParameters, run_simulation


class PhysicsScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = SimulationParameters()
        cases = {'homogeneous': replace(base, tunnel_resistivity=100), 'air': base,
                 'water': replace(base, tunnel_resistivity=5)}
        for name, rho in (('air', 1e8), ('water', 5)):
            for depth in (10, 20, 30):
                cases[f'{name}_depth_{depth}'] = replace(base, tunnel_resistivity=rho, depth=depth)
            for radius in (3, 7):
                cases[f'{name}_radius_{radius}'] = replace(base, tunnel_resistivity=rho, radius=radius)
            for nx in (80, 240):
                cases[f'{name}_grid_{nx}'] = replace(base, tunnel_resistivity=rho, nx=nx)
        cases['air_host_200'] = replace(base, host_resistivity=200)
        cases['air_x_35'] = replace(base, center_x=35)
        cases['air_x_65'] = replace(base, center_x=65)
        cases['air_depth_35'] = replace(base, depth=35)
        cls.results = {name: run_simulation(p) for name, p in cases.items()}
        cls.metrics = {}
        for name, r in cls.results.items():
            m, p = r.model, r.parameters
            mask = np.hypot(m.x[None, :] - p.center_x, m.z[:, None] - p.depth) <= p.radius
            jx = (m.jx[:, :-1] + m.jx[:, 1:]) / 2
            jz = (m.jz[:-1, :] + m.jz[1:, :]) / 2
            cls.metrics[name] = {
                'parameters': asdict(p), **r.diagnostics,
                'mean_tunnel_current_density_A_m2': float(np.hypot(jx, jz)[mask].mean()),
                'rasterized_area_m2': float(mask.sum() * m.dx * m.dz),
                'homogeneous_current_A_m': float(r.reference.jx[:, 0].sum() * m.dz),
            }

    def test_A_homogeneous(self):
        r = self.results['homogeneous']
        m = r.model
        exact = np.broadcast_to(1 - m.x / 100, m.potential.shape)
        np.testing.assert_allclose(m.potential, exact, atol=1e-12, rtol=0)
        np.testing.assert_allclose(m.potential, r.reference.potential, atol=1e-13, rtol=0)
        np.testing.assert_allclose(m.jx, 1e-4, atol=1e-14, rtol=0)
        np.testing.assert_allclose(m.jz, 0, atol=1e-14, rtol=0)

    def test_B_resistive_tunnel_diverts_current(self):
        d = self.metrics['air']
        self.assertLess(d['mean_tunnel_current_density_A_m2'], 1e-3 * 1e-4)
        self.assertLess(d['entering_current_A_per_m'], d['homogeneous_current_A_m'])
        m = self.results['air'].model
        # Lateral current deflection must exist, rather than a 1D linear field.
        self.assertGreater(np.max(np.abs(m.jz)), 1e-5)

    def test_C_conductive_tunnel_concentrates_current(self):
        d = self.metrics['water']
        self.assertGreater(d['mean_tunnel_current_density_A_m2'], 1e-4)
        self.assertGreater(d['entering_current_A_per_m'], d['homogeneous_current_A_m'])
        self.assertGreater(np.max(np.abs(self.results['water'].model.jz)), 1e-5)

    def test_D_depth_sensitivity(self):
        for material in ('air', 'water'):
            signal = [self.metrics[f'{material}_depth_{z}']['max_abs_surface_anomaly_V'] for z in (10, 20, 30)]
            self.assertGreater(signal[0], signal[1])
            self.assertGreater(signal[1], signal[2])
        # Insulating top/bottom imply exact vertical-reflection symmetry.
        np.testing.assert_allclose(self.results['air'].model.potential[::-1],
                                   self.results['air_depth_35'].model.potential, atol=1e-11, rtol=0)

    def test_E_size_sensitivity(self):
        for material in ('air', 'water'):
            small, big = (self.metrics[f'{material}_radius_{r}'] for r in (3, 7))
            self.assertGreater(big['max_abs_surface_anomaly_V'], small['max_abs_surface_anomaly_V'])
            if material == 'air':
                self.assertLess(big['entering_current_A_per_m'], small['entering_current_A_per_m'])
            else:
                self.assertGreater(big['entering_current_A_per_m'], small['entering_current_A_per_m'])

    def test_F_grid_sensitivity_not_convergence_order(self):
        for material in ('air', 'water'):
            coarse, medium, fine = (self.metrics[name] for name in
                                    (f'{material}_grid_80', material, f'{material}_grid_240'))
            for d in (coarse, medium, fine):
                self.assertLess(abs(d['rasterized_area_m2'] / (np.pi * 25) - 1), 0.05)
            # Gross consistency bounds, not a formal accuracy/convergence claim.
            self.assertLess(abs(fine['entering_current_A_per_m'] / medium['entering_current_A_per_m'] - 1), 0.01)
            self.assertLess(abs(fine['max_abs_surface_anomaly_V'] / medium['max_abs_surface_anomaly_V'] - 1), 0.10)

    def test_all_cases_flux_law_boundaries_conservation_and_residual(self):
        for name, r in self.results.items():
            with self.subTest(name=name):
                m, d = r.model, r.diagnostics
                sigma = m.conductivity
                self.assertTrue(np.all(np.isfinite(sigma)) and np.all(sigma > 0))
                self.assertTrue(np.all(np.isfinite(m.potential)))
                self.assertGreaterEqual(m.potential.min(), -1e-10)
                self.assertLessEqual(m.potential.max(), 1 + 1e-10)
                # Independent two-half-cell resistance calculation, in both axes.
                expected_x = -np.diff(m.potential, axis=1) / (m.dx / (2*sigma[:, :-1]) + m.dx / (2*sigma[:, 1:]))
                expected_z = -np.diff(m.potential, axis=0) / (m.dz / (2*sigma[:-1, :]) + m.dz / (2*sigma[1:, :]))
                np.testing.assert_allclose(m.jx[:, 1:-1], expected_x, rtol=1e-12, atol=1e-18)
                np.testing.assert_allclose(m.jz[1:-1, :], expected_z, rtol=1e-12, atol=1e-18)
                np.testing.assert_allclose(m.potential[:, 0] + m.jx[:, 0] * m.dx / (2*sigma[:, 0]), 1, atol=1e-14)
                np.testing.assert_allclose(m.potential[:, -1] - m.jx[:, -1] * m.dx / (2*sigma[:, -1]), 0, atol=1e-14)
                np.testing.assert_array_equal(m.jz[[0, -1]], 0)
                self.assertLess(d['relative_boundary_current_imbalance'], 1e-9)
                self.assertLess(d['max_cell_imbalance_over_max_face_current'], 1e-9)
                self.assertLess(m.residual_inf, 1e-12)
                np.testing.assert_array_equal(m.x, r.reference.x)
                np.testing.assert_array_equal(m.z, r.reference.z)
                self.assertEqual((m.left_potential,m.right_potential),
                                 (r.reference.left_potential,r.reference.right_potential))

    def test_position_symmetry_and_host_resistivity_response(self):
        left = self.results['air_x_35'].model
        right = self.results['air_x_65'].model
        np.testing.assert_allclose(left.potential[:, ::-1], 1-right.potential, atol=1e-11, rtol=0)
        self.assertLess(self.metrics['air_host_200']['entering_current_A_per_m'],
                        self.metrics['air']['entering_current_A_per_m'])


if __name__ == '__main__':
    unittest.main()
