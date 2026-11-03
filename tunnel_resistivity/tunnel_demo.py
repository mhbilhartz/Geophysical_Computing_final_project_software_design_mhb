"""Static tunnel comparisons: python -m tunnel_resistivity.tunnel_demo --help."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .diagnostics import diagnostics
from .plotting import build_figure
from .geometry import circular_tunnel
from .solver import solve_conductivity, solve_homogeneous


def plot_case(model, reference, *, center_x, depth, radius, title, output):
    """Save the shared four-panel figure (keeps the static example API)."""
    fig = build_figure(model, reference, center_x=center_x, depth=depth,
                       radius=radius, title=title)
    fig.savefig(output, dpi=160)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    for name, default in (("width", 100.), ("height", 50.), ("center-x", 50.),
                          ("depth", 15.), ("radius", 5.), ("host-resistivity", 100.),
                          ("air-resistivity", 1e8), ("water-resistivity", 5.)):
        parser.add_argument("--" + name, type=float, default=default)
    parser.add_argument("--nx", type=int, default=160)
    parser.add_argument("--nz", type=int, default=80)
    args = parser.parse_args()
    grid = dict(width=args.width, height=args.height, nx=args.nx, nz=args.nz)
    geometry = dict(center_x=args.center_x, depth=args.depth, radius=args.radius)
    # Validate both material models before solving or producing files.
    cases = [(name, rho, circular_tunnel(**grid, **geometry,
                host_resistivity=args.host_resistivity, tunnel_resistivity=rho)[0])
             for name, rho in (("air", args.air_resistivity), ("water", args.water_resistivity))]
    reference = solve_homogeneous(**grid, conductivity=1 / args.host_resistivity)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"grid": grid, "geometry": geometry, "host_resistivity_ohm_m": args.host_resistivity,
              "reference_current_A_per_m": float(reference.jx[:, 0].sum() * reference.dz), "cases": {}}
    surface_fig, surface_ax = plt.subplots(figsize=(9, 4), layout="constrained")
    for name, rho, sigma in cases:
        model = solve_conductivity(sigma, width=args.width, height=args.height)
        output = args.output_dir / f"tunnel_{name}.png"
        plot_case(model, reference, **geometry,
                  title=f"{name.capitalize()} approximation: tunnel ρ = {rho:g} Ω m; host ρ = {args.host_resistivity:g} Ω m",
                  output=output)
        # Zero top-face derivative gives V_surface ≈ first-row cell potentials.
        surface_ax.plot(model.x, model.potential[0] - reference.potential[0], label=f"{name}: {rho:g} Ω m")
        report["cases"][name] = {"tunnel_resistivity_ohm_m": rho, **diagnostics(model, reference)}
        print(f"Saved {output}")
    surface_ax.axhline(0, color="gray", linewidth=0.8)
    surface_ax.set(xlabel="Horizontal distance x (m)", ylabel="Surface ΔV (V)",
                   title="Surface potential anomaly: tunnel − homogeneous reference")
    surface_ax.legend()
    surface_fig.savefig(args.output_dir / "surface_anomalies.png", dpi=160)
    plt.close(surface_fig)
    report_path = args.output_dir / "tunnel_diagnostics.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
