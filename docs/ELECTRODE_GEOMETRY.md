# Electrode-array geometry — survey upgrade, Step 1

**Current status:** this geometry is used by the 2.5D source, receiver and survey
modules, the [live app](LIVE_APP.md), and [field explorer](VISUALIZATIONS.md).
The following describes the original Step 1 milestone; its geometry-only test
counts and deferred-work statements are historical. Current checks are in
[FINAL_REVIEW.md](../FINAL_REVIEW.md).

This module defines **one four-electrode measurement**, not a full survey or a
forward solution. The existing fixed-side-voltage application and analytical
verification notebook remain unchanged. At that milestone the electrode configuration was not yet connected to the
solver or Panel controls; the subsequent stages completed those connections.

## Common conventions

- All positions are in **meters** along the horizontal x direction. Electrodes
  lie on a flat surface, at cross-line y=0 and depth z=0.
- **A** injects **+I amperes**; **B** withdraws **I**. `current_a` is a finite,
  strictly positive amplitude, so the source/return pair balances exactly.
- **M** and **N** are voltage receivers, with the voltage convention
  **V_M − V_N**. No receiver voltage is calculated at this stage.
- `center_x_m` means the **midpoint of the entire electrode spread** for all
  three arrays, including dipole–dipole. It is not the tunnel center or the
  midpoint of the source dipole in a dipole–dipole configuration.
- Coordinates remain continuous and are not rounded to the existing grid.
  Electrode source treatment/interpolation belongs to the subsequent solver work.
- `positions_x_m` returns a dictionary in **label order A, B, M, N**, which differs
  from the left-to-right order for Wenner and Schlumberger.

## Geometry definitions

| Array | Left-to-right order | Inputs | Full spread |
| --- | --- | --- | --- |
| Wenner (alpha arrangement) | A — M — N — B | Equal adjacent spacing a > 0 | 3a |
| Schlumberger | A — M — N — B | AB/2 = L; MN/2 = l; 0 < l < L | 2L |
| Dipole–dipole | A — B — M — N | AB = MN = a; B-to-M gap = n·a; integer n ≥ 1 | (n+2)a |

The Schlumberger receiver separation is usually small relative to source
separation, but no extra arbitrary minimum AB/MN ratio is enforced here.
For dipole–dipole, **n=1 means one dipole length between B and M**, not zero gap
or center-to-center distance. Its dipole-center separation is (n+1)a.

With A as positive source and receiver voltage V_M−V_N, the standard left-to-right
dipole–dipole geometry can have **negative voltage in a uniform half-space**.
This is a polarity convention, not negative physical resistivity. Later geometric
factors must use that same polarity; we must not silently take absolute voltages
or reuse a positive factor with incompatible labels. Geometric factors and
apparent resistivities are deferred to the receiver-calculation stage.

## Examples (no new packages required)

Run from the repository root in the existing Python environment:

```python
from tunnel_resistivity.electrodes import wenner, schlumberger, dipole_dipole

w = wenner(center_x_m=50, spacing_m=5, current_a=0.1)
s = schlumberger(center_x_m=50, ab_half_spacing_m=20,
                 mn_half_spacing_m=2, current_a=0.1)
d = dipole_dipole(center_x_m=50, spacing_m=5,
                  separation_n=2, current_a=0.1)

for config in (w, s, d):
    config.validate_domain(0, 100, boundary_padding_m=5)
    print(config.array_type, config.positions_x_m, config.source_currents_a)
```

Expected label-ordered positions:

```text
wenner        A=42.5  B=57.5  M=47.5  N=52.5
schlumberger  A=30.0  B=70.0  M=48.0  N=52.0
dipole-dipole A=40.0  B=45.0  M=55.0  N=60.0
```

For each example A injects +0.1 A and B withdraws 0.1 A.

## Validation and limits

Factories validate finite real inputs, positive spacing/current, integer n,
and Schlumberger separation. The immutable `ElectrodeArray` record also checks
distinct electrodes, finite spread, correct ordering, and the selected array's
spacing relationships. Invalid values raise `ValueError`. Coordinates too close
to distinguish at floating-point precision are rejected rather than merged.

`validate_domain(x_min_m, x_max_m, boundary_padding_m=...)` requires electrodes
strictly inside artificial side boundaries and honors the requested minimum
padding. It does **not** establish that this padding is physically adequate.
Domain sensitivity must be assessed with the new electrode solver. Array geometry
alone does not choose a mesh, inject current into the PDE, or establish electrode
resolution.

## Tests and next stage

```bash
python -m unittest discover -s tests -p test_electrodes.py -v
python -m unittest discover -s tests -v
```

Geometry tests check exact positions/distances, balanced source currents,
translations, off-grid positions, ordering, invalid inputs, bounds/padding,
immutability and numerical limits. They verify **geometry only**. The next stage
is the 2.5D electrode solver and its homogeneous half-space verification—not
applying ordinary point-electrode ERT factors to the old 2D fixed-voltage solver.

No commit, GitHub push, or cloud-environment publication is performed by Step 1.
