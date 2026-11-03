"""Validated interface parameters and orchestration; no UI or second solver."""

from dataclasses import dataclass
from numbers import Integral
from time import perf_counter
import warnings

import numpy as np

from .diagnostics import diagnostics
from .geometry import circular_tunnel
from .solver import Solution, solve_conductivity, solve_homogeneous

WIDTH, HEIGHT = 100.0, 50.0
GRID_CHOICES = {"Coarse: 80 × 40": 80, "Medium: 160 × 80": 160, "Fine: 240 × 120": 240}
PRESETS = {"Air-filled": 1e8, "Water-filled": 5.0}
GEOMETRY_MARGIN = 0.5


@dataclass(frozen=True)
class SimulationParameters:
    depth: float = 15.0
    radius: float = 5.0
    center_x: float = 50.0
    host_resistivity: float = 100.0
    tunnel_resistivity: float = 1e8
    nx: int = 160

    def validate(self):
        for name, low, high in (("depth", 0, HEIGHT), ("radius", 2, 10),
                                ("center_x", 0, WIDTH), ("host_resistivity", 10, 1e4),
                                ("tunnel_resistivity", 1, 1e8)):
            value = getattr(self, name)
            if not np.isscalar(value) or not np.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be finite and between {low:g} and {high:g}")
        if isinstance(self.nx, bool) or not isinstance(self.nx, Integral) or self.nx not in GRID_CHOICES.values():
            raise ValueError("Choose one of the three supported grid resolutions")
        clearance = self.radius + GEOMETRY_MARGIN
        if not (clearance <= self.depth <= HEIGHT - clearance and
                clearance <= self.center_x <= WIDTH - clearance):
            raise ValueError("Keep the tunnel at least 0.5 m inside every domain boundary")


@dataclass(frozen=True)
class SimulationResult:
    parameters: SimulationParameters
    model: Solution
    reference: Solution
    diagnostics: dict
    warnings: tuple[str, ...]
    elapsed_seconds: float


def run_simulation(parameters: SimulationParameters) -> SimulationResult:
    """Make tunnel and reference models on identical grids and boundaries."""
    parameters.validate()
    start = perf_counter()
    grid = dict(width=WIDTH, height=HEIGHT, nx=parameters.nx, nz=parameters.nx // 2)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UserWarning)
        sigma, _ = circular_tunnel(
            **grid, center_x=parameters.center_x, depth=parameters.depth,
            radius=parameters.radius, host_resistivity=parameters.host_resistivity,
            tunnel_resistivity=parameters.tunnel_resistivity,
        )
    boundaries = dict(left_potential=1.0, right_potential=0.0)
    model = solve_conductivity(sigma, width=WIDTH, height=HEIGHT, **boundaries)
    reference = solve_homogeneous(**grid, conductivity=1 / parameters.host_resistivity, **boundaries)
    messages = [str(w.message) for w in caught]
    info = diagnostics(model, reference)
    if (info["relative_boundary_current_imbalance"] > 1e-8 or
            info["max_cell_imbalance_over_max_face_current"] > 1e-8 or
            info["potential_min_V"] < -1e-8 or info["potential_max_V"] > 1 + 1e-8):
        messages.append("Numerical checks exceeded tolerance; inspect the diagnostics and reduce contrast.")
    if max(parameters.host_resistivity / parameters.tunnel_resistivity,
           parameters.tunnel_resistivity / parameters.host_resistivity) >= 1e6:
        messages.append("High conductivity contrast: check grid and contrast sensitivity before interpreting results.")
    return SimulationResult(parameters, model, reference, info, tuple(messages), perf_counter() - start)
