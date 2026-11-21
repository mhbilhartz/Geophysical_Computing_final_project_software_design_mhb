# Survey upgrade, Step 3: receivers and apparent resistivity

**Step 7 update:** the [live Panel interface](LIVE_APP.md) now calls this backend.
The milestone report below records its original implementation and checks.

**Current status:** the subsequent [Step 4 notebook](../verification_2p5d.ipynb)
and [verification guide](VERIFICATION_2P5D.md) now verify this receiver/backend
pipeline. The Step 3 report below records its original checks and limitations.

The separate [receivers.py](../tunnel_resistivity/receivers.py) module samples
surface receivers from the **existing Step 2 2.5D solution**. It calculates one
four-electrode datum, using Step 1 geometry. It contains no second PDE solver,
Panel code, survey generator, inversion, or geophysical simulation package.

The original fixed-voltage application, both numerical solvers, existing tests,
and `verification.ipynb` are preserved. The default Panel application now uses
this receiver pipeline; `legacy_app.py` retains the original model. The separate
[2.5D verification notebook](../verification_2p5d.ipynb) is complete.

## Voltage polarity, geometric factor, and units

A injects +I amperes, B withdraws I. The measured voltage is always

$$\Delta V=V_M-V_N,\qquad R=\Delta V/I.$$

For point electrodes on a flat homogeneous half-space with resistivity ρ₀,

$$
V(x,0,0)=\frac{\rho_0 I}{2\pi}
\left(\frac1{|x-x_A|}-\frac1{|x-x_B|}\right).
$$

Define the **signed** geometric factor and apparent resistivity by

$$
D=\frac1{AM}-\frac1{BM}-\frac1{AN}+\frac1{BN},\qquad
K=\frac{2\pi}{D},\qquad \rho_a=K\frac{\Delta V}{I}.
$$

The four distances are positive separations in meters. K is meters, ΔV volts,
R ohms, and ρₐ **Ω·m**, not Ω/m. This normalization recovers ρ₀ in homogeneous
earth. In heterogeneous earth, ρₐ is an array-dependent response, not the true
resistivity of a cell or of the tunnel.

The general four-distance expression is implemented explicitly; tests compare
it against these independently derived array-specific formulas:

| Array and label order | Spacing convention | Signed K |
| --- | --- | --- |
| Wenner, A–M–N–B | Adjacent spacing a | 2πa |
| Schlumberger, A–M–N–B | AB/2=L, MN/2=l | π(L²−l²)/(2l) |
| Dipole–dipole, A–B–M–N | AB=MN=a, B-to-M=n·a | −πan(n+1)(n+2) |

With this dipole–dipole ordering, homogeneous ΔV and K are both negative,
so ρₐ is positive. Taking an absolute voltage while retaining signed K would
introduce a sign error. The code takes **no absolute values of voltage or K**.
A modeled negative apparent resistivity is retained for investigation; it is
not silently clipped. Material conductivity must still be positive and finite.

Distances are scaled before summation and `math.fsum` reduces cancellation.
If the four-term denominator cannot be resolved relative to floating-point
roundoff, or K is nonfinite, `geometric_factor` raises `ValueError`. Very weak
transfer signals at extreme separations need higher-precision or specialized
treatment; increasing mesh resolution alone will not fix factor cancellation.

## Sampling a surface from cell-centered results

Receivers sit at z=0, whereas the first solution row is at z=dz/2. Interpolating
the **total** potential from cell centers would smear the analytical point-source
field and bias even a homogeneous measurement. Instead:

1. Evaluate the exact primary at each receiver's continuous surface coordinate.
2. Reconstruct only the smooth secondary correction at z=0. Where the first
   two rows are background material, fit an even quadratic through their values:

   ```text
   Vs(x,0) ≈ [9 Vs(x,dz/2) − Vs(x,3dz/2)] / 8
   ```

   Its derivative at the surface is zero, matching Step 2's secondary Neumann
   boundary. Where the second row differs from the background, use the first-row
   zero-gradient estimate instead: do not extrapolate a smooth quadratic through
   a material interface. Shallow contrasts still require mesh refinement.
3. Interpolate the reconstructed secondary linearly in x. Explicit zero values
   at the side faces honor Step 2's secondary boundary condition and support the
   two half-cell strips outside the first/last centers.
4. Add analytical primary and reconstructed secondary at M and N.

Source positions are singular and rejected. Receivers must be strictly inside
the artificial side faces; out-of-domain samples raise an error, rather than
being silently clamped by interpolation. Numeric scalar and nonempty 1D position
arrays are supported. Invalid coordinates, incompatible grids, and the original
fixed-voltage `Solution` are rejected.

The analytical homogeneous reference is the primary field already used by
Step 2, with the **same A/B, current, σ₀, and boundary convention**. No separate
numerical reference solve is necessary: the homogeneous correction is exactly
zero. Store primary and secondary voltage differences separately, so the anomaly
can be evaluated as K·ΔVs/I without subtracting nearly equal total resistivities.
Homogeneous recovery is exact by construction and is not alone an independent
test of the nonzero numerical correction.

## Use from Python or Jupyter

Run from the repository root in the environment with the project requirements:

```python
from tunnel_resistivity.electrodes import wenner
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.solver_2p5d import solve_source_pair
from tunnel_resistivity.receivers import measure_receivers, sample_surface_potential

sigma, mask = circular_tunnel(
    width=200, height=100, nx=160, nz=80,
    center_x=100, depth=15, radius=5,
    host_resistivity=100, tunnel_resistivity=1e8,
)
array = wenner(center_x_m=100, spacing_m=10, current_a=1)
solution = solve_source_pair(sigma, array, width=200, height=100)
datum = measure_receivers(solution)
print(datum.potential_m_v, datum.potential_n_v)  # V
print(datum.voltage_v)                         # V_M - V_N, V
print(datum.geometric_factor_m)                # signed K, m
print(datum.apparent_resistivity_ohm_m)         # about 105.79 Ω·m
print(100 * datum.relative_apparent_resistivity_anomaly)  # percent

# Other nonsingular surface locations in the same source field:
print(sample_surface_potential(solution, [90.5, 95.3, 105.2]))
```

`measure_receivers(solution, electrodes=another_array)` may reuse a field with
new M/N positions **only if A, B, and current match exactly**. This supports, for
example, changing Schlumberger MN separation without another source solve.
A different source position or current is rejected: rerun `solve_source_pair`.
Changing conductivity also requires a new source solve. The frozen measurement
record retains the geometry used for that measurement.

## Static reproducible comparison

```bash
python -m tunnel_resistivity.receiver_demo
```

Windows PowerShell uses the existing environment's interpreter:

```powershell
.\.venv\Scripts\python.exe -m tunnel_resistivity.receiver_demo
```

Outputs are regenerable and ignored by Git:

- `outputs/receivers_2p5d/measurements.csv`
- `outputs/receivers_2p5d/measurements.json`
- `outputs/receivers_2p5d/apparent_resistivity_comparison.png`

Use `--output-dir PATH` to choose another directory. The CSV/JSON include model,
grid, electrode/current parameters, signed voltages/factors, apparent resistivity,
anomalies, mode diagnostics, quadrature settings and solve time. This is nine
**single-measurement examples**, not an automatically generated full survey.

Executed settings: 200×100 m, 160×80 cells, tunnel center (100,15) m, radius 5 m,
host 100 Ω·m, I=1 A. Air=1e8 Ω·m; water=5 Ω·m. Wenner a=10 m; Schlumberger
L=20 m, l=2 m; dipole–dipole a=5 m, n=2.

| Array | Homogeneous ρₐ (Ω·m) | Air ρₐ (Ω·m) | Water ρₐ (Ω·m) |
| --- | ---: | ---: | ---: |
| Wenner | 100.000000 | 105.788047 | 95.161434 |
| Schlumberger | 100.000000 | 110.596652 | 91.140804 |
| Dipole–dipole | 100.000000 | 105.227400 | 94.013301 |

The arrays have different spreads and sensitivity patterns: these numbers do
not establish that one array is universally better at detecting a tunnel. A
resistive inclusion does not produce 1e8 Ω·m apparent resistivity because the
measurement includes the surrounding host and the geometry of current flow.

## Executed tests and numerical limits

Before implementation, all **73 existing tests passed**. The new module adds
19 tests in [test_receivers.py](../tests/test_receivers.py). The final full run
**passed all 92 tests in 31.226 seconds**. Hash checks confirm that all 22
previously existing Python source/test files and the verification notebook are
unchanged from the start of this step. Run:

```bash
python -m unittest discover -s tests -p test_receivers.py -v
python -m unittest discover -s tests -v
```

Tests cover closed-form geometric factors, sign conventions, translations and
length scaling; exact surface primary sampling; manufactured secondary surface
reconstruction at off-grid positions; side half-cell strips; shallow material
interfaces; invalid inputs and rejection of the old solver; homogeneous recovery
for three arrays, three resistivities and two meshes; nonzero air/water data;
actual forward solves with changed current and absolute material resistivity;
source-compatible receiver reuse; and preservation of negative synthetic data.

A **nonzero layered-earth benchmark** independently checks the complete source
solve plus receiver calculation. Upper ρ₁=100 Ω·m, lower ρ₂=200 Ω·m, layer thickness
h=10 m, Wenner a=10 m, I=1 A. For each source and receiver at surface separation r,
the analytical potential is

$$
\frac{\rho_1 I}{2\pi}\left[\frac1r+
2\sum_{n=1}^{\infty}\frac{\kappa^n}{\sqrt{r^2+(2nh)^2}}\right],\quad
\kappa=\frac{\rho_2-\rho_1}{\rho_2+\rho_1}=\frac13.
$$

Subtract B's contribution from A's and then subtract receiver N from M. Using
79 image pairs gives **ΔV=1.805438647386 V**, **ρₐ=113.439055823 Ω·m**. The
automated benchmark uses 480×320 m and 192×128 cells; its correction-voltage error
is about **0.02147%**, and its apparent-resistivity error about **0.002543%**.
This is independent of the homogeneous primary recovery test.

Additional executed receiver studies, with 64 Fourier nodes:

| Domain (m) | Grid | dx=dz (m) | Numerical ρₐ (Ω·m) | Relative ρₐ error (%) |
| --- | --- | ---: | ---: | ---: |
| 480×320 | 96×64 | 5.00 | 113.442802 | 0.003302 |
| 480×320 | 192×128 | 2.50 | 113.436171 | 0.002543 |
| 480×320 | 384×256 | 1.25 | 113.429157 | 0.008726 |
| 960×640 | 384×256 | 2.50 | 113.447199 | 0.007178 |

**Errors are nonmonotonic.** Doubling the domain at fixed 2.5 m spacing changes
ρₐ by about 0.01103 Ω·m, demonstrating boundary sensitivity. Mesh, surface
interpolation and finite-boundary errors can partly cancel, making a coarse
result appear more accurate. These runs do not establish a second-order rate
for the complete receiver calculation. The separate smooth-mode test from
Step 2 demonstrates that rate for its spatial operator; the upcoming notebook
must distinguish these sources of error rather than force a convergence result.

All Step 2 assumptions remain: a flat homogeneous surface row, conductivity
independent of cross-line y, positive finite material values, infinitely long
tunnel geometry, and approximate primary-valued outer walls. Near-source samples,
weak transfer signals, shallow interfaces and stair-stepped circles require care.
No contact impedance, electrode noise, topography, finite tunnel ends, inversion,
or site-calibrated detectability is included. Neither a small residual nor these
benchmarks establishes field validation.
