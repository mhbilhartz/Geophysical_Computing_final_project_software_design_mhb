"""Check plotted quantities, coordinates, arrows, and color labels."""

import unittest

from matplotlib.quiver import Quiver
import numpy as np

from tunnel_resistivity.plotting import build_figure
from tunnel_resistivity.simulation import SimulationParameters, run_simulation


class PlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = SimulationParameters(nx=80, center_x=35, depth=20, radius=7, tunnel_resistivity=5)
        cls.r = run_simulation(cls.p)
        cls.fig = build_figure(cls.r.model, cls.r.reference, center_x=35, depth=20, radius=7, title='Plot checks')

    def test_units_axis_orientation_and_circle(self):
        axes = self.fig.axes
        self.assertEqual(len(axes), 8)
        for ax in axes[:4]:
            self.assertEqual(ax.get_xlabel(), 'Horizontal distance x (m)')
            self.assertEqual(ax.get_ylabel(), 'Depth z (m)')
            self.assertEqual(ax.get_xlim(), (0, 100))
            self.assertEqual(ax.get_ylim(), (50, 0))
            self.assertEqual(ax.patches[0].center, (35, 20))
            self.assertEqual(ax.patches[0].radius, 7)
        self.assertEqual([ax.get_ylabel() for ax in axes[4:]],
                         ['Resistivity (Ω m)', 'Electrical potential (V)',
                          'Current density magnitude (A/m²)', 'Tunnel − homogeneous potential (V)'])

    def test_plotted_fields_and_current_arrows(self):
        m, ref = self.r.model, self.r.reference
        jx = (m.jx[:, :-1] + m.jx[:, 1:]) / 2
        jz = (m.jz[:-1, :] + m.jz[1:, :]) / 2
        fields = (1/m.conductivity, m.potential, np.hypot(jx,jz), m.potential-ref.potential)
        for ax, field in zip(self.fig.axes[:4], fields):
            np.testing.assert_allclose(ax.collections[0].get_array(), field)
        quiver = next(c for c in self.fig.axes[2].collections if isinstance(c, Quiver))
        stride = max(1,len(m.x)//25)
        np.testing.assert_allclose(quiver.U, jx[::stride,::stride].ravel())
        np.testing.assert_allclose(quiver.V, jz[::stride,::stride].ravel())
        self.assertEqual(quiver.angles, 'xy')
        self.assertEqual(quiver.scale_units, 'xy')

    def test_uniform_current_colors_do_not_amplify_roundoff(self):
        r = run_simulation(SimulationParameters(tunnel_resistivity=100))
        fig = build_figure(r.model, r.reference, center_x=50, depth=15, radius=5, title='Uniform current')
        field = fig.axes[2].collections[0]
        norm = field.norm
        self.assertGreater(norm.vmax / norm.vmin, 1.01)
        # The raw current remains untouched, but tiny roundoff must not fill
        # the entire colormap and look like heterogeneous current flow.
        self.assertLess(np.ptp(norm(field.get_array())), 1e-6)


if __name__ == '__main__':
    unittest.main()
