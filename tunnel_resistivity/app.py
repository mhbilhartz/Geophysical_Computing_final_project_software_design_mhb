"""Panel UI and per-session factory. Launch from the root: panel serve app.py."""

import logging

import numpy as np
import panel as pn

from tunnel_resistivity.plotting import build_figure
from tunnel_resistivity.simulation import (
    GEOMETRY_MARGIN, GRID_CHOICES, HEIGHT, PRESETS, WIDTH,
    SimulationParameters, run_simulation,
)

pn.extension()


def describe(result):
    p = result.parameters
    return (f"Center ({p.center_x:g}, {p.depth:g}) m · radius {p.radius:g} m · "
            f"host {p.host_resistivity:g} Ω·m · tunnel {p.tunnel_resistivity:g} Ω·m · "
            f"grid {p.nx} × {p.nx // 2}")


def diagnostic_text(result, previous=None):
    """Readable comparison of the most recent two successful runs."""
    def values(r):
        d = r.diagnostics
        reference_current = float(r.reference.jx[:, 0].sum() * r.reference.dz)
        return (
            f"{d['entering_current_A_per_m']:.7g}",
            f"{d['leaving_current_A_per_m']:.7g}",
            f"{reference_current:.7g}",
            f"{d['relative_boundary_current_imbalance']:.2e}",
            f"{d['max_cell_imbalance_over_max_face_current']:.2e}",
            f"{d['residual_inf_A_per_m']:.2e}",
            f"{d['potential_min_V']:.5f} to {d['potential_max_V']:.5f}",
            f"{d['max_abs_potential_anomaly_V']:.5g}",
            f"{d['max_abs_surface_anomaly_V']:.5g}",
        )
    labels = ("Entering current (A/m thickness)", "Leaving current (A/m thickness)",
              "Homogeneous reference current (A/m thickness)",
              "Relative boundary current imbalance", "Max cell imbalance / max face current",
              "Matrix residual, infinity norm (A/m)", "Potential range (V)",
              "Peak absolute ΔV in domain (V)", "Peak absolute surface ΔV (V)")
    old = values(previous) if previous else ("—",) * len(labels)
    rows = ["| Diagnostic | Latest | Previous |", "| --- | ---: | ---: |"]
    rows += [f"| {label} | {new} | {prior} |" for label, new, prior in zip(labels, values(result), old)]
    return (f"**Latest:** {describe(result)}  \n"
            f"Cell size {result.model.dx:.3g} × {result.model.dz:.3g} m; "
            f"{result.parameters.radius / max(result.model.dx, result.model.dz):.1f} cells per radius. "
            f"Two solves completed in {result.elapsed_seconds:.3f} s (plot rendering excluded).\n\n"
            + "\n".join(rows))


class SimulatorApp:
    """Per-session controls and two result snapshots; no global mutable app state."""

    def __init__(self, *, initial_run=True):
        self.latest = None
        self.previous = None
        self.run_number = 0
        self.radius = pn.widgets.FloatSlider(label="Tunnel radius (m)", start=2, end=10, step=0.5, value=5)
        self.depth = pn.widgets.FloatSlider(label="Tunnel center depth (m)", start=5.5, end=44.5, step=0.5, value=15)
        self.center_x = pn.widgets.FloatSlider(label="Horizontal center position (m)", start=5.5, end=94.5, step=0.5, value=50)
        self.host = pn.widgets.FloatInput(label="Background rock resistivity (Ω·m)", start=10, end=1e4, value=100, step=10)
        self.material = pn.widgets.Select(label="Tunnel material", options=[*PRESETS, "Custom"], value="Air-filled")
        self.tunnel = pn.widgets.FloatInput(label="Tunnel resistivity (Ω·m)", start=1, end=1e8, value=1e8, step=1, disabled=True)
        self.grid = pn.widgets.Select(label="Grid resolution", options=GRID_CHOICES, value=160)
        self.run_button = pn.widgets.Button(label="Run Simulation", color="primary", width=280)
        self.reset_button = pn.widgets.Button(label="Reset to Defaults", width=280)
        self.status = pn.pane.Alert("Choose parameters and click Run Simulation.", alert_type="info")
        self.warning = pn.pane.Alert("", alert_type="warning", visible=False)
        self.latest_view = pn.Column("No simulation yet.", sizing_mode="stretch_width")
        self.previous_view = pn.Column("Run a second scenario to retain the first here.", sizing_mode="stretch_width")
        self.tabs = pn.Tabs(("Latest run", self.latest_view), ("Previous run", self.previous_view),
                            dynamic=True, sizing_mode="stretch_width")
        self.info = pn.pane.Markdown("", sizing_mode="stretch_width")
        controls = pn.Column(
            "### Tunnel and host", self.material, self.tunnel, self.host,
            self.depth, self.radius, self.center_x, self.grid,
            "Depth is measured to the tunnel **center**. Position limits adjust with radius, "
            "keeping the circle at least 0.5 m inside the domain.",
            self.run_button, self.reset_button,
            "Air: 10⁸ Ω·m; water: 5 Ω·m. Presets are illustrative. Select Custom to edit tunnel resistivity.",
            width=300,
        )
        self.view = pn.Column(
            "# 2D Electrical Resistivity Forward Modeling Simulator",
            "Explore a circular tunnel in a **100 × 50 m** host. "
            "Left boundary: **1 V**; right: **0 V**; top/bottom: **zero normal current**. "
            "This is idealized 2D DC conduction, with no inversion or ERT electrode arrays.",
            pn.Row(controls, pn.Column(self.status, self.warning, self.tabs, self.info,
                                      sizing_mode="stretch_width", min_width=600), sizing_mode="stretch_width"),
            "**Reading the plots:** dashed outline = intended circle; colors show cell values. "
            "Current arrows show direction and magnitude; see the arrow key. "
            "ΔV = tunnel model − homogeneous model on the same grid. "
            "Resistivity, current, and ΔV color limits adapt to each run; compare color bars. "
            "The Latest/Previous tabs retain the two most recent successful scenarios. "
            "A small residual verifies the linear solve, not geometric accuracy.",
            sizing_mode="stretch_width",
        )
        self.radius.param.watch(self._geometry_changed, "value")
        self.material.param.watch(self._material_changed, "value")
        for widget in (self.radius, self.depth, self.center_x, self.host, self.material, self.tunnel, self.grid):
            widget.param.watch(self._mark_pending, "value")
        self.run_button.on_click(self.run)
        self.reset_button.on_click(self.reset)
        if initial_run:
            self.run()

    def _geometry_changed(self, event):
        clearance = event.new + GEOMETRY_MARGIN
        for widget, extent in ((self.depth, HEIGHT), (self.center_x, WIDTH)):
            widget.param.update(start=clearance, end=extent - clearance,
                                value=float(np.clip(widget.value, clearance, extent - clearance)))

    def _material_changed(self, event):
        self.tunnel.disabled = event.new != "Custom"
        if event.new in PRESETS:
            self.tunnel.value = PRESETS[event.new]

    def _mark_pending(self, event):
        self.status.alert_type = "info"
        self.status.object = "Parameters changed. Click Run Simulation; displayed results still describe the last successful run."

    def parameters(self):
        return SimulationParameters(depth=self.depth.value, radius=self.radius.value,
                                    center_x=self.center_x.value, host_resistivity=self.host.value,
                                    tunnel_resistivity=self.tunnel.value, nx=self.grid.value)

    def run(self, event=None):
        self.run_button.disabled = self.reset_button.disabled = True
        self.run_button.loading = True
        try:
            result = run_simulation(self.parameters())
            p = result.parameters
            fig = build_figure(result.model, result.reference, center_x=p.center_x,
                               depth=p.depth, radius=p.radius, title=describe(result))
            pane = pn.pane.Matplotlib(fig, format="png", dpi=120, tight=False,
                                      sizing_mode="stretch_width")
            if self.latest is not None:
                self.previous_view.objects = list(self.latest_view.objects)
            self.previous, self.latest = self.latest, result
            self.run_number += 1
            self.latest_view.objects = [pn.pane.Markdown(f"### Run {self.run_number}\n{describe(result)}"), pane]
            self.info.object = diagnostic_text(result, self.previous)
            self.warning.object = "\n\n".join(result.warnings)
            self.warning.visible = bool(result.warnings)
            self.tabs.active = 0
            self.status.alert_type = "success"
            self.status.object = f"Run {self.run_number} complete. Plots and diagnostics match the parameters recorded below."
        except (ValueError, RuntimeError) as exc:
            self.status.alert_type = "danger"
            self.status.object = f"Simulation was not updated: {exc}. Previous successful results are retained."
        except Exception:
            logging.getLogger(__name__).exception("Unexpected simulation or rendering error")
            self.status.alert_type = "danger"
            self.status.object = "Simulation was not updated. Check the server log; previous results are retained."
        finally:
            self.run_button.loading = False
            self.run_button.disabled = self.reset_button.disabled = False

    def reset(self, event=None):
        defaults = SimulationParameters()
        self.radius.value = defaults.radius
        self.depth.value = defaults.depth
        self.center_x.value = defaults.center_x
        self.host.value = defaults.host_resistivity
        self.material.value = "Air-filled"
        self.tunnel.value = defaults.tunnel_resistivity
        self.tunnel.disabled = True
        self.grid.value = defaults.nx
        self.run()


def create_app():
    """Factory: every browser session gets independent controls and results."""
    return SimulatorApp().view
