"""Circular, cell-center conductivity geometry; no solving or plotting."""

import warnings

import numpy as np

from .solver import cell_centers


def circular_tunnel(
    *, width=100.0, height=50.0, nx=160, nz=80,
    center_x=50.0, depth=15.0, radius=5.0,
    host_resistivity=100.0, tunnel_resistivity=1e8,
):
    """Return (conductivity, tunnel_mask), shaped (nz, nx).

    Distances are meters, resistivities ohm m. Depth locates the circle's center,
    measured downward from the top surface. The circle must be strictly inside
    the domain. A center on the circle is included. Finite high resistivity
    approximates air; zero conductivity and infinite resistivity are forbidden.
    """
    x, z, dx, dz = cell_centers(width, height, nx, nz)
    for name, value in (("center_x", center_x), ("depth", depth),
                        ("radius", radius), ("host_resistivity", host_resistivity),
                        ("tunnel_resistivity", tunnel_resistivity)):
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if radius <= 0 or host_resistivity <= 0 or tunnel_resistivity <= 0:
        raise ValueError("Radius and resistivities must be positive")
    if not (radius < center_x < width - radius and radius < depth < height - radius):
        raise ValueError("The circle must lie strictly inside the domain")
    with np.errstate(over="ignore", under="ignore", divide="ignore"):
        conductivities = 1.0 / np.array([host_resistivity, tunnel_resistivity])
    if not np.all(np.isfinite(conductivities)) or np.any(conductivities <= 0):
        raise ValueError("Resistivity reciprocals must be finite and positive")
    mask = np.hypot(x[None, :] - center_x, z[:, None] - depth) <= radius
    if not np.any(mask):
        raise ValueError("Tunnel occupies no cell centers; refine the grid")
    if radius / max(dx, dz) < 4:
        warnings.warn("Tunnel has fewer than four cells per radius; refine the grid",
                      UserWarning, stacklevel=2)
    sigma = np.full((nz, nx), conductivities[0])
    sigma[mask] = conductivities[1]
    return sigma, mask
