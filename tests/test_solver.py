"""Analytical and physical checks of the actual sparse solver."""

import unittest

import numpy as np

from tunnel_resistivity import solve_homogeneous


class HomogeneousSolverTests(unittest.TestCase):
    def test_analytical_potential_and_current_on_rectangular_grids(self):
        for nx, nz in ((2, 2), (13, 7), (40, 25)):
            with self.subTest(nx=nx, nz=nz):
                m = solve_homogeneous(width=73, height=29, nx=nx, nz=nz,
                                      conductivity=0.03, left_potential=2, right_potential=-1)
                exact = np.broadcast_to(2 - 3 * m.x / 73, m.potential.shape)
                np.testing.assert_allclose(m.potential, exact, atol=2e-12, rtol=0)
                np.testing.assert_allclose(m.jx, 0.03 * 3 / 73, atol=2e-14, rtol=0)
                np.testing.assert_allclose(m.jz, 0, atol=2e-14, rtol=0)
                self.assertGreaterEqual(m.potential.min(), -1)
                self.assertLessEqual(m.potential.max(), 2)
                self.assertLess(m.residual_inf, 1e-12)

    def test_local_and_global_current_conservation(self):
        m = solve_homogeneous(nx=31, nz=17)
        net = np.diff(m.jx, axis=1) * m.dz + np.diff(m.jz, axis=0) * m.dx
        np.testing.assert_allclose(net, 0, atol=1e-14, rtol=0)
        np.testing.assert_array_equal(m.jz[[0, -1]], 0)
        entering = np.sum(m.jx[:, 0]) * m.dz
        leaving = np.sum(m.jx[:, -1]) * m.dz
        self.assertAlmostEqual(entering, leaving, places=13)
        self.assertGreater(entering, 0)

    def test_equal_boundary_potentials_give_no_current(self):
        m = solve_homogeneous(nx=15, nz=9, left_potential=3, right_potential=3)
        np.testing.assert_allclose(m.potential, 3, atol=1e-12, rtol=0)
        np.testing.assert_allclose(m.jx, 0, atol=1e-14, rtol=0)
        np.testing.assert_allclose(m.jz, 0, atol=1e-14, rtol=0)

    def test_conductivity_scales_current_but_not_potential(self):
        a = solve_homogeneous(nx=11, nz=8, conductivity=0.01)
        b = solve_homogeneous(nx=11, nz=8, conductivity=0.1)
        np.testing.assert_allclose(b.potential, a.potential, atol=1e-12, rtol=0)
        np.testing.assert_allclose(b.jx, 10 * a.jx, atol=1e-14, rtol=0)

    def test_reversing_voltage_reverses_current(self):
        m = solve_homogeneous(nx=11, nz=8, left_potential=0, right_potential=1)
        self.assertTrue(np.all(m.jx < 0))
        np.testing.assert_allclose(m.potential, np.broadcast_to(m.x / 100, (8, 11)),
                                   atol=1e-12, rtol=0)

    def test_invalid_inputs(self):
        for kwargs in ({"nx": 1}, {"nz": 2.5}, {"nx": True}, {"width": 0},
                       {"height": -1}, {"conductivity": 0}, {"conductivity": np.nan},
                       {"left_potential": np.inf}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                solve_homogeneous(**kwargs)


if __name__ == "__main__":
    unittest.main()
