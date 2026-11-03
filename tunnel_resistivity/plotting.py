"""Matplotlib views shared by the static examples and Panel interface."""

from matplotlib.colors import LogNorm, Normalize
from matplotlib.figure import Figure
from matplotlib.patches import Circle
import numpy as np


def _log_norm(values):
    low = max(float(np.min(values)), 1e-30)
    high = max(float(np.max(values)), low)
    # A homogeneous solve contains tiny floating-point flux differences.
    # Do not stretch those differences across the full colormap.
    if high / low - 1 <= 1e-10:
        low, high = low / 1.1, high * 1.1
    return LogNorm(vmin=low, vmax=high)


def build_figure(model, reference, *, center_x, depth, radius, title):
    """Plot cell fields; use shared-face currents averaged only for display."""
    delta = model.potential - reference.potential
    jx = 0.5 * (model.jx[:, :-1] + model.jx[:, 1:])
    jz = 0.5 * (model.jz[:-1, :] + model.jz[1:, :])
    magnitude = np.hypot(jx, jz)
    width, height = model.dx * len(model.x), model.dz * len(model.z)
    xedges = np.linspace(0, width, len(model.x) + 1)
    zedges = np.linspace(0, height, len(model.z) + 1)
    limit = max(float(np.max(np.abs(delta))), 1e-12)
    fig = Figure(figsize=(12, 8), layout="constrained")
    axes = fig.subplots(2, 2)
    fig.suptitle(title + "\nLeft 1 V; right 0 V; top/bottom insulating")
    panels = (
        (1 / model.conductivity, "Resistivity (Ω m)", "viridis", _log_norm(1 / model.conductivity)),
        (model.potential, "Electrical potential (V)", "viridis", Normalize(0, 1)),
        (np.maximum(magnitude, 1e-30), "Current density magnitude (A/m²)", "magma", _log_norm(magnitude)),
        (delta, "Tunnel − homogeneous potential (V)", "RdBu_r", Normalize(-limit, limit)),
    )
    for ax, (field, label, cmap, norm) in zip(axes.flat, panels):
        image = ax.pcolormesh(xedges, zedges, field, cmap=cmap, norm=norm, shading="flat")
        # Dashed outline is the intended circle; the material grid is stair-stepped.
        ax.add_patch(Circle((center_x, depth), radius, fill=False,
                            edgecolor="gray", linestyle="--", linewidth=1))
        ax.set(xlabel="Horizontal distance x (m)", ylabel="Depth z (m)",
               xlim=(0, width), ylim=(height, 0))
        ax.set_aspect("equal")
        fig.colorbar(image, ax=ax, label=label)
    stride = max(1, len(model.x) // 25)
    subset = (slice(None, None, stride), slice(None, None, stride))
    xx, zz = np.meshgrid(model.x, model.z)
    # Same arrow scale for both scenarios; arrows show magnitude and direction.
    reference_j = float(np.mean(np.abs(reference.jx)))
    quiver = axes[1, 0].quiver(xx[subset], zz[subset], jx[subset], jz[subset],
                              angles="xy", scale_units="xy", scale=reference_j / 2,
                              color="cyan", width=0.003)
    axes[1, 0].quiverkey(quiver, 0.78, 1.04, reference_j, f"{reference_j:.1e} A/m²", labelpos="E")
    return fig
