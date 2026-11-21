"""Exercise Panel callbacks without a browser; solver tests remain independent."""

import unittest
from unittest.mock import patch

from bokeh.document import Document
import numpy as np
import panel as pn

from tunnel_resistivity.app import SimulatorApp
from tunnel_resistivity.simulation import SimulationParameters


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = SimulatorApp(initial_run=False)
        self.app.grid.value = 80

    def test_presets_and_custom_values(self):
        app = self.app
        self.assertTrue(app.tunnel.disabled)
        app.material.value = 'Water-filled'
        self.assertEqual(app.parameters().tunnel_resistivity, 5)
        app.material.value = 'Custom'
        self.assertFalse(app.tunnel.disabled)
        app.tunnel.value = 1234
        self.assertEqual(app.parameters().tunnel_resistivity, 1234)
        app.material.value = 'Air-filled'
        self.assertEqual(app.parameters().tunnel_resistivity, 1e8)
        self.assertTrue(app.tunnel.disabled)

    def test_selected_preset_overrides_stale_numeric_widget(self):
        app = self.app
        app.material.value = 'Water-filled'
        app.tunnel.value = 1e8
        app.run()
        self.assertEqual(app.status.alert_type, 'success')
        self.assertEqual(app.latest.parameters.tunnel_resistivity, 5)
        app.material.value = 'Air-filled'
        app.tunnel.value = 5
        self.assertEqual(app.parameters().tunnel_resistivity, 1e8)
        app.material.value = 'Custom'
        self.assertEqual(app.parameters().tunnel_resistivity, 5)

    def test_radius_updates_position_limits_and_clamps_geometry(self):
        app = self.app
        app.depth.value = 5.5
        app.center_x.value = 5.5
        app.radius.value = 10
        self.assertEqual(app.depth.start, 10.5)
        self.assertEqual(app.center_x.end, 89.5)
        self.assertEqual(app.depth.value, 10.5)
        self.assertEqual(app.center_x.value, 10.5)
        app.parameters().validate()

    def test_runs_comparison_and_document_rendering(self):
        app = self.app
        app.run_button.clicks += 1
        self.assertEqual(app.run_number, 1)
        first = app.latest
        self.assertIsNotNone(first)
        app.material.value = 'Water-filled'
        self.assertIn('Parameters changed', app.status.object)
        self.assertIs(app.latest, first)
        app.run_button.clicks += 1
        self.assertEqual(app.run_number, 2)
        self.assertIs(app.previous, first)
        self.assertEqual(app.latest.parameters.tunnel_resistivity, 5)
        self.assertEqual(app.status.alert_type, 'success')
        self.assertIn('Previous', app.info.object)
        latest_plot = app.latest_view[1]
        self.assertIsInstance(latest_plot, pn.pane.Matplotlib)
        self.assertEqual(len(latest_plot.object.axes), 8)  # Four plots, four color bars.
        document = app.view.server_doc(Document())
        self.assertTrue(document.roots)
        self.assertTrue(all(np.isfinite(app.latest.model.potential.flat)))

    def test_invalid_run_retains_success_and_reenables_buttons(self):
        app = self.app
        app.run()
        first = app.latest
        with patch.object(app, 'parameters', return_value=SimulationParameters(depth=0)):
            app.run_button.clicks += 1
        self.assertIs(app.latest, first)
        self.assertEqual(app.run_number, 1)
        self.assertEqual(app.status.alert_type, 'danger')
        self.assertFalse(app.run_button.disabled)
        self.assertFalse(app.reset_button.disabled)

    def test_reset_restores_controls_and_reruns(self):
        app = self.app
        app.material.value = 'Custom'
        app.tunnel.value = 500
        app.radius.value = 9
        app.depth.value = 22
        app.center_x.value = 70
        app.host.value = 300
        app.reset_button.clicks += 1
        self.assertEqual(app.parameters(), SimulationParameters())
        self.assertEqual(app.latest.parameters, SimulationParameters())
        self.assertEqual(app.material.value, 'Air-filled')
        self.assertTrue(app.tunnel.disabled)
        self.assertEqual(app.status.alert_type, 'success')

    def test_sessions_have_independent_controls_and_results(self):
        other = SimulatorApp(initial_run=False)
        self.app.material.value = 'Water-filled'
        self.assertEqual(other.material.value, 'Air-filled')
        self.assertIsNot(other.latest_view, self.app.latest_view)
        self.assertIsNone(other.latest)

    def test_every_control_reaches_the_existing_solver(self):
        app = self.app
        app.material.value = 'Custom'
        app.tunnel.value = 5
        app.run()
        cases = ((app.depth, 20, 'depth'), (app.radius, 7, 'radius'),
                 (app.center_x, 35, 'center_x'), (app.host, 200, 'host_resistivity'),
                 (app.tunnel, 20, 'tunnel_resistivity'), (app.grid, 240, 'nx'))
        for widget, value, attribute in cases:
            with self.subTest(parameter=attribute):
                prior = app.latest
                widget.value = value
                app.run_button.clicks += 1
                self.assertEqual(app.status.alert_type, 'success')
                self.assertEqual(getattr(app.latest.parameters, attribute), value)
                self.assertIs(app.previous, prior)
                self.assertEqual(app.latest.model.potential.shape,
                                 (app.latest.parameters.nx // 2, app.latest.parameters.nx))
                sigma = app.latest.model.conductivity
                self.assertTrue(np.all(np.isfinite(sigma)) and np.all(sigma > 0))

    def test_bad_numeric_fields_do_not_replace_previous_results(self):
        app = self.app
        app.material.value = 'Custom'
        app.run()
        prior = app.latest
        for widget, bad, good in ((app.host, 0, 100), (app.tunnel, -1, 5),
                                  (app.tunnel, float('nan'), 5), (app.tunnel, None, 5)):
            with self.subTest(bad=bad):
                widget.value = bad
                app.run_button.clicks += 1
                self.assertIs(app.latest, prior)
                self.assertEqual(app.status.alert_type, 'danger')
                self.assertFalse(app.run_button.disabled)
                widget.value = good


if __name__ == '__main__':
    unittest.main()
