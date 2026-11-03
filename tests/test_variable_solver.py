"""Variable-conductivity, interface-flux, and tunnel regression checks."""

import unittest
import warnings

import numpy as np

from tunnel_resistivity import circular_tunnel, solve_conductivity, solve_homogeneous


class VariableSolverTests(unittest.TestCase):
    def assert_conserved(self, m):
        net = np.diff(m.jx, axis=1) * m.dz + np.diff(m.jz, axis=0) * m.dx
        scale = max(np.max(np.abs(m.jx)) * m.dz, np.max(np.abs(m.jz)) * m.dx)
        self.assertLess(np.max(np.abs(net)) / scale, 1e-10)
        entering = m.jx[:, 0].sum() * m.dz
        leaving = m.jx[:, -1].sum() * m.dz
        self.assertLess(abs(entering - leaving) / abs(entering), 1e-10)
        np.testing.assert_array_equal(m.jz[[0, -1]], 0)

    def test_layered_series_resistance_analytical_solution(self):
        # Interface aligned with cell faces: exact 1D series-resistor solution.
        # Arithmetic averaging fails this check at the conductivity jump.
        rho = np.array([100.] * 8 + [1e5] * 12)
        dx = 2.0
        current = 1 / np.sum(rho * dx)
        exact = 1 - current * (np.cumsum(rho * dx) - 0.5 * rho * dx)
        m = solve_conductivity(np.tile(1 / rho, (7, 1)), width=40, height=21)
        np.testing.assert_allclose(m.potential, np.broadcast_to(exact, (7, 20)), atol=2e-12)
        np.testing.assert_allclose(m.jx, current, rtol=1e-9, atol=1e-16)
        self.assert_conserved(m)

    def test_transposed_layers_have_linear_potential(self):
        # A depth-varying conductivity must not create vertical flux.
        sigma = np.repeat(np.geomspace(1e-4, 1, 9)[:, None], 17, axis=1)
        m = solve_conductivity(sigma, width=34, height=18)
        np.testing.assert_allclose(m.potential, np.broadcast_to(1 - m.x / 34, sigma.shape),
                                   atol=2e-12, rtol=0)
        np.testing.assert_allclose(m.jx, np.repeat(sigma[:, :1] / 34, 18, axis=1),
                                   atol=1e-13, rtol=1e-10)
        self.assert_conserved(m)

    def test_irregular_conductivity_conserves_current(self):
        sigma = 10 ** np.random.default_rng(436).uniform(-4, 0, size=(13, 21))
        m = solve_conductivity(sigma)
        self.assertTrue(np.all(np.isfinite(m.potential)))
        self.assertGreaterEqual(m.potential.min(), -1e-10)
        self.assertLessEqual(m.potential.max(), 1 + 1e-10)
        self.assert_conserved(m)

    def test_tunnel_extreme_contrasts_and_physical_response(self):
        settings = dict(nx=100, nz=60, center_x=43, depth=16, radius=7)
        reference = solve_homogeneous(nx=100, nz=60)
        reference_current = reference.jx[:, 0].sum() * reference.dz
        for rho in (1e8, 5):
            with self.subTest(tunnel_resistivity=rho):
                sigma, mask = circular_tunnel(**settings, tunnel_resistivity=rho)
                m = solve_conductivity(sigma)
                self.assertTrue(np.all(np.isfinite(m.potential)))
                self.assertTrue(np.all(np.isfinite(m.jx)))
                self.assertTrue(np.all(np.isfinite(m.jz)))
                self.assertGreaterEqual(m.potential.min(), -1e-9)
                self.assertLessEqual(m.potential.max(), 1 + 1e-9)
                self.assert_conserved(m)
                self.assertGreater(np.max(np.abs(m.potential - reference.potential)), 1e-3)
                current = m.jx[:, 0].sum() * m.dz
                jx_center = (m.jx[:, :-1] + m.jx[:, 1:]) / 2
                if rho > 100:
                    self.assertLess(current, reference_current)
                    self.assertLess(np.mean(np.abs(jx_center[mask])), 1e-7)
                else:
                    self.assertGreater(current, reference_current)
                    self.assertGreater(np.mean(jx_center[mask]), 1e-4)

    def test_equal_resistivities_recover_homogeneous_solution(self):
        sigma, _ = circular_tunnel(nx=80, nz=40, tunnel_resistivity=100)
        m = solve_conductivity(sigma)
        ref = solve_homogeneous()
        np.testing.assert_allclose(m.potential, ref.potential, atol=1e-13, rtol=0)
        np.testing.assert_allclose(m.jx, ref.jx, atol=1e-14, rtol=0)
        np.testing.assert_allclose(m.jz, ref.jz, atol=1e-14, rtol=0)

    def test_invalid_conductivities(self):
        for value in (0, -1, np.inf, np.nan):
            sigma = np.ones((5, 7))
            sigma[2, 3] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                solve_conductivity(sigma)
        for sigma in (np.ones(7), np.ones((1, 7)), np.ones((0, 0))):
            with self.assertRaises(ValueError):
                solve_conductivity(sigma)


class GeometryTests(unittest.TestCase):
    def test_off_center_circle_and_material_assignment(self):
        sigma, mask = circular_tunnel(nx=120, nz=80, center_x=32, depth=18,
                                      radius=6, host_resistivity=200, tunnel_resistivity=5)
        x = (np.arange(120) + 0.5) * 100 / 120
        z = (np.arange(80) + 0.5) * 50 / 80
        expected = (x[None, :] - 32)**2 + (z[:, None] - 18)**2 <= 36
        np.testing.assert_array_equal(mask, expected)
        np.testing.assert_array_equal(sigma[mask], 1 / 5)
        np.testing.assert_array_equal(sigma[~mask], 1 / 200)
        area = mask.sum() * (100 / 120) * (50 / 80)
        self.assertLess(abs(area / (np.pi * 6**2) - 1), 0.05)
        _, moved = circular_tunnel(nx=120, nz=80, center_x=65, depth=30, radius=6)
        self.assertFalse(np.array_equal(mask, moved))

    def test_invalid_geometry_and_resistivity(self):
        for kw in ({"radius": 0}, {"depth": 5}, {"center_x": 99}, {"radius": np.nan},
                   {"host_resistivity": 0}, {"tunnel_resistivity": np.inf},
                   {"tunnel_resistivity": -1}, {"host_resistivity": 1e-320},
                   {"nx": 10, "nz": 10, "radius": 0.01, "center_x": 50, "depth": 25}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                circular_tunnel(**kw)

    def test_underresolved_circle_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            circular_tunnel(nx=20, nz=10, radius=3, center_x=52.5, depth=17.5)
        self.assertTrue(any("four cells" in str(w.message) for w in caught))


if __name__ == "__main__":
    unittest.main()
