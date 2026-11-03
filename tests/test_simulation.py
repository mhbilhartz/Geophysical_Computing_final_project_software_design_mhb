"""Interface-to-solver mapping, limits, and matching reference models."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from tunnel_resistivity.simulation import SimulationParameters, run_simulation


class SimulationTests(unittest.TestCase):
    def test_geometry_materials_and_matching_reference(self):
        p = SimulationParameters(nx=80, center_x=35, depth=20, radius=7,
                                 host_resistivity=200, tunnel_resistivity=5)
        r = run_simulation(p)
        np.testing.assert_array_equal(r.model.x, r.reference.x)
        np.testing.assert_array_equal(r.model.z, r.reference.z)
        self.assertEqual(r.model.potential.shape, (40, 80))
        for m in (r.model, r.reference):
            self.assertEqual((m.left_potential, m.right_potential), (1, 0))
        mask = np.hypot(r.model.x[None, :] - 35, r.model.z[:, None] - 20) <= 7
        np.testing.assert_array_equal(r.model.conductivity[mask], 1 / 5)
        np.testing.assert_array_equal(r.model.conductivity[~mask], 1 / 200)
        self.assertEqual(r.reference.conductivity, 1 / 200)
        self.assertLess(r.diagnostics['relative_boundary_current_imbalance'], 1e-10)

    def test_matching_materials_give_zero_anomaly(self):
        r = run_simulation(SimulationParameters(nx=80, tunnel_resistivity=100))
        np.testing.assert_allclose(r.model.potential, r.reference.potential, atol=1e-13, rtol=0)

    def test_invalid_parameters_never_reach_solver(self):
        for change in ({'depth': 5}, {'radius': 0}, {'radius': 11}, {'center_x': 99},
                       {'host_resistivity': 0}, {'tunnel_resistivity': -1},
                       {'tunnel_resistivity': np.inf}, {'depth': np.nan},
                       {'nx': 10000}, {'nx': True}, {'host_resistivity': 1e10}):
            with self.subTest(change=change), patch('tunnel_resistivity.simulation.solve_conductivity') as solver:
                with self.assertRaises(ValueError):
                    run_simulation(replace(SimulationParameters(), **change))
                solver.assert_not_called()

    def test_resolution_warning_is_returned(self):
        r = run_simulation(SimulationParameters(nx=80, radius=2, tunnel_resistivity=5))
        self.assertTrue(any('four cells' in w for w in r.warnings))

    def test_high_contrast_range_is_finite(self):
        r = run_simulation(SimulationParameters(nx=80, host_resistivity=10, tunnel_resistivity=1e8))
        self.assertTrue(np.all(np.isfinite(r.model.potential)))
        self.assertTrue(np.all(np.isfinite(r.model.jx)))
        self.assertTrue(any('High conductivity contrast' in w for w in r.warnings))


if __name__ == '__main__':
    unittest.main()
