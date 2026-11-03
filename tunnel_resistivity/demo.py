"""Run with: MPLBACKEND=Agg python -m tunnel_resistivity.demo."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .solver import solve_homogeneous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/homogeneous_potential.png"))
    args = parser.parse_args()
    model = solve_homogeneous()
    width, height = model.dx * model.x.size, model.dz * model.z.size
    exact = model.left_potential + (model.right_potential - model.left_potential) * model.x / width
    error = np.max(np.abs(model.potential - exact[None, :]))
    current_in = np.sum(model.jx[:, 0]) * model.dz
    current_out = np.sum(model.jx[:, -1]) * model.dz

    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    image = ax.pcolormesh(
        np.linspace(0, width, model.x.size + 1),
        np.linspace(0, height, model.z.size + 1), model.potential,
        shading="flat", cmap="viridis", vmin=0, vmax=1,
    )
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set(xlabel="Horizontal distance x (m)", ylabel="Depth z (m)",
           title="Homogeneous host: σ = 0.01 S/m (ρ = 100 Ω m)\n"
                 "Left: 1 V | Right: 0 V | Top/bottom: insulating")
    fig.colorbar(image, ax=ax, label="Electrical potential (V)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)
    print(f"Maximum analytical potential error: {error:.3e} V")
    print(f"Current entering/leaving per unit thickness: {current_in:.8g} / {current_out:.8g} A/m")
    print(f"Matrix residual infinity norm: {model.residual_inf:.3e} A/m")
    print(f"Plot saved to {args.output}")


if __name__ == "__main__":
    main()
