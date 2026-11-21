# Survey upgrade, Step 2: a 2.5D source-pair solver

**Step 7 update:** the [live Panel interface](LIVE_APP.md) now calls this backend.
The milestone report below records its original implementation and checks.

**Current status:** [Step 3](RECEIVER_MEASUREMENTS.md) now samples surface M/N
and calculates signed apparent resistivity from this backend. This page records
the Step 2 numerical method and its executed checks; the source solver itself
is unchanged by Step 3. The default Panel app now uses this source-pair backend;
`legacy_app.py` retains the fixed-voltage model.

The new [solver_2p5d.py](../tunnel_resistivity/solver_2p5d.py) accepts positive,
finite conductivity and the electrode geometry from Step 1. It returns electrical
potential and current-density fields in the electrode plane. Only A/B excite the
model; M/N are retained for geometry validation. Receiver voltages, geometric
factors, apparent resistivity, survey generation, a new verification notebook,
and Panel integration were added in subsequent steps; see the
[current review](../FINAL_REVIEW.md).

The original `solver.py`, Panel modules, existing tests, and executed
`verification.ipynb` are preserved. That notebook's verification and the original
analysis results apply to the fixed-voltage solver, not this new backend.

## Coordinates, sources, and physical equation

Conductivity is isotropic and invariant along cross-line y: σ=σ(x,z). Electrodes
are **point sources in 3D**, at y=z=0, with A injecting +I A and B withdrawing I A.
Depth z increases downward. A circular anomaly in the x/z plane therefore
represents an infinitely long cylindrical tunnel along y. Finite tunnel ends,
topography, contact impedance, anisotropy and inversion are not modeled.

In the conducting interior, away from sources,

$$
\nabla\cdot(\sigma\nabla V)=0,\qquad \mathbf J=-\sigma\nabla V.
$$

Surface injection is a boundary flux: J_z(x,y,0) equals
I[δ(x−x_A)−δ(x−x_B)]δ(y). The rest of the flat surface is insulating. There is
no imposed 1 V/0 V side drop in this backend. Conductivity is S/m, V is volts,
and physical J is A/m²; I is amperes, rather than A/m for a 2D line source.

## Why Fourier modes make this 2.5D

Use the full Fourier transform

$$
\widehat V(x,k,z)=\int_{-\infty}^{\infty}V(x,y,z)e^{-iky}\,dy.
$$

Conductivity's independence from y gives the interior mode operator

$$
A_\sigma(k)\widehat V=
-\partial_x(\sigma\partial_x\widehat V)
-\partial_z(\sigma\partial_z\widehat V)+k^2\sigma\widehat V.
$$

Each k has its own sparse 2D solve. Reflection symmetry about y=0 gives

$$
V(x,0,z)=\frac1\pi\int_0^\infty\widehat V(x,k,z)\,dk.
$$

The k² term allows current to spread in y. Simply adding point sources to the
old 2D equation would represent line sources and give the wrong geometric decay.

## Primary/secondary treatment of electrode singularities

A point electrode has singular potential. We avoid replacing it with a
mesh-dependent finite source cell by separating out the exact homogeneous
half-space solution, using background conductivity σ₀:

$$
V_p=\frac{I}{2\pi\sigma_0}\left(\frac1{r_A}-\frac1{r_B}\right),\quad
\widehat V_p=\frac{I}{\pi\sigma_0}[K_0(kr_A)-K_0(kr_B)],
$$

where r_Q=√[(x−x_Q)²+z²] and K₀ is SciPy's modified Bessel function. The physical
1/r primary is added **analytically**, without quadrature. The numerical modes
solve only the secondary correction caused by conductivity contrast.

In the continuous interior, the primary satisfies ΔV̂_p=k²V̂_p. Consequently,

$$
A_\sigma(k)\widehat V_s=\nabla\sigma\cdot\nabla\widehat V_p.
$$

We integrate the primary's Helmholtz identity over each constant-conductivity
cell to cancel its bulk flux/mass terms **before discretizing**. The interface
forcing is then approximated as

```text
rhs_P = sum_faces (sigma_face - sigma_P) * (d Vp_hat/dn)_face * face_length
```

Primary derivatives at internal faces are analytical (using K₁); harmonic
face conductivity is shared with the secondary operator. The outward normal
changes sign for the other cell. Outer faces have sigma_face=sigma_P and
contribute no contrast forcing; top source cells have sigma_P=sigma₀. The
forcing is exactly zero inside any uniform material, including the air region.
This approximates interface polarization without introducing spurious bulk
sources. The final field is V_p+∫V̂_s dk/π.

An initial implementation used `(A_background−A_sigma)*sampled_primary` directly.
Its truncation residual inside air was amplified by σ₀/σ_air, producing a peak
correction of about 24 V in the demonstration despite tiny matrix residuals.
The interface formulation reduced it to about 0.275 V and recovered saturation
as tunnel resistivity increases. A dedicated bounded-potential/saturation
regression test now guards against this defect. That initial implementation
was corrected before completing this milestone.

**Boundary conditions:**

- Top: zero secondary normal derivative. The analytical primary supplies the
  A/B point-source flux and is insulating elsewhere. The entire top cell row
  must equal σ₀; surface conductivity anomalies are rejected in this version.
- Sides and bottom: secondary potential zero at the **faces**, half a cell from
  adjacent centers. Thus total potential there equals the analytical primary.
  This is a finite-domain approximation, not an exact open boundary condition.
- The primary reference and these wall values set the potential datum. A
  balanced A/B pair has potential tending to zero at infinity.

Unknowns are at cell centers, so no returned field samples the singular surface
source positions. Source coordinates stay continuous; they are not snapped to
cell centers.

## Conservative finite differences and numerical integration

Each shared interior face uses

```text
sigma_face = harmonic mean(sigma_P, sigma_neighbor)
T_x = sigma_face * dz/dx
T_z = sigma_face * dx/dz
sum_faces T * (Vs_P - Vs_neighbor) + k²*sigma_P*dx*dz*Vs_P = rhs_P
```

One shared face conductance appears with equal and opposite signs in the two
neighboring balances. This represents resistances in series and preserves
current continuity across grid-aligned jumps. Side/bottom Dirichlet conductances
use the half-cell distance; missing top neighbors add no secondary flux.
Visible Python loops assemble the sparse matrix; SciPy `spsolve` solves it.
No existing geophysical simulation package or dense matrix inverse is used.

Gauss–Legendre quadrature is applied in log(k), including the Jacobian dk=k dlog(k).
Positive nodes avoid K₀'s singular value at k=0. Defaults are 64 nodes,
k_min=10⁻⁶/max(width,height) and k_max=20/min(dx,dz). These are **heuristics**.
Node count, lower cutoff, upper cutoff, mesh, and domain size all require
sensitivity checks; a small matrix residual does not certify any of them.

Returned `jx`/`jz` are cell-center A/m², using the **actual local conductivity**
times analytical primary gradients plus finite-difference secondary gradients.
The latter use ghost values consistent with the secondary boundaries. These
pointwise currents are approximate near abrupt interfaces and are not the
original solver's conservative face-current arrays. Both have shape `(nz,nx)`.
Jy=0 in the y=0 symmetry plane, but ∂Jy/∂y generally is not zero. Consequently,
checking only ∂Jx/∂x+∂Jz/∂z=0 would be an incorrect conservation test here.

For each Fourier correction, diagnostics report the infinity-norm relative
matrix residual and integrated balance: outward secondary wall flux plus the
k²σ mass term equals the integrated contrast right-hand side. Local equation
residuals include the k² term. The global balance is for the **secondary mode**,
not a separate direct measurement of total A/B injection. Summing its conservative
shared faces cancels internal fluxes.

## Use it independently of Panel

Run from the repository root, using the same environment as the original app:

```python
from tunnel_resistivity.electrodes import wenner
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.solver_2p5d import solve_source_pair

sigma, mask = circular_tunnel(
    width=200, height=100, nx=160, nz=80,
    center_x=100, depth=15, radius=5,
    host_resistivity=100, tunnel_resistivity=5,
)
electrodes = wenner(center_x_m=100, spacing_m=10, current_a=1)
solution = solve_source_pair(sigma, electrodes, width=200, height=100)
print(solution.max_relative_mode_residual)
# solution.potential, solution.secondary_potential: volts, shape (80,160)
# solution.jx, solution.jz: A/m² at cell centers, shape (80,160)
```

The geometry helper also works with this backend for positive finite air
resistivity, e.g. 1e8 Ω·m. For a translated domain, `x_origin_m` sets its left edge;
electrode coordinates must use that same coordinate system. Supply
`background_conductivity` explicitly if desired; otherwise the first top cell
sets σ₀. All electrodes must lie strictly inside the side walls. This placement
check alone does not establish adequate padding.

```bash
python -m unittest discover -s tests -p test_solver_2p5d.py -v
python -m unittest discover -s tests -v
python -m tunnel_resistivity.demo_2p5d
```

The demonstration writes `outputs/source_pair_2p5d/source_pair_comparison.png`
and `diagnostics.json`. Resistivity, total potential, secondary potential and
current magnitude share scales between air and water panels. Cyan unit arrows
show direction only; current magnitude uses the color bar. Depth increases down.
This demonstration does not change the running Panel application.

## Executed verification evidence

The 57 pre-existing tests passed before changes. The new suite adds 16 tests;
the final complete run **passed all 73 tests in 22.269 s** on 2026-11-12.
The regenerated 200×100 m air/water demonstration had maximum relative mode
residual 6.29e-15 and maximum mode balance error 4.67e-15. These are algebraic
diagnostics, not error bounds on physical fields. Checks include:

- Homogeneous half-space V and J for all three electrode configurations.
  The correction is zero **by construction**, so this alone is not an independent
  numerical verification of the mode solver.
- Independent identity ∫₀∞ K₀(kr) dk=π/(2r), checking Fourier normalization and
  log-quadrature weights, including the factor 1/π.
- A nonzero manufactured Fourier mode with homogeneous conductivity,
  u=sin(πx/W)cos(πz/(2H)), and forcing σ[(π/W)²+(π/2H)²+k²]u. This matches zero
  side/bottom value and zero top derivative. With W=20 m, H=10 m, k=0.2 m⁻¹:

  | Grid | RMSE |
  | --- | ---: |
  | 16×8 | 8.8765782e-4 |
  | 32×16 | 2.2183316e-4 |
  | 64×32 | 5.5453204e-5 |

  Both measured orders are approximately 2.00. This verifies the smooth mode
  operator, not second-order convergence for stair-stepped circular interfaces.
- A grid-aligned, piecewise-conductivity analytical series-resistance solution,
  checking harmonic flux continuity and known face boundary values.
- An independent two-layer image-source solution, with ρ₁=100 Ω·m, ρ₂=200 Ω·m,
  and layer thickness h=10 m. In the upper layer each source's 1/r term is
  supplemented by Σₙ₌₁∞ κⁿ(1/rₙ⁺+1/rₙ⁻), where κ=(ρ₂−ρ₁)/(ρ₂+ρ₁)=1/3 and
  image depths are ±2nh. The test uses 79 image pairs and compares z<5 m,
  |x−center|<10 m, excluding electrodes. This exercises a nonzero numerical
  correction, rather than recovering the primary alone.

  | Domain (m) | Grid | Potential RMSE (V) | Error / RMS exact correction |
  | --- | --- | ---: | ---: |
  | 240×160 | 96×64 | 1.79794e-4 | 0.1453% |
  | 480×320 | 192×128 | 6.04590e-4 | 0.4885% |
  | 480×320 | 384×256 | 6.92317e-5 | 0.05557% |

  The first two have the **same mesh spacing**. Boundary and discretization
  errors partly cancel in the smaller domain, so a smaller error there does not
  establish domain independence. The enlarged domain improves strongly on mesh
  refinement. The automated test uses the middle case with a 1% tolerance on
  the correction; the finer case was also executed as a separate numerical study.
- Water-tunnel quadrature study on 100×50 m, 80×40 cells, center (50,15) m,
  radius 5 m, host/tunnel 100/5 Ω·m, Wenner a=10 m, I=1 A: changing 24→48
  nodes changes the correction's L2 norm by 0.2206%; 48→72 changes it by
  0.00006564%. The 72-node peak correction is 0.2340874 V. Extending both
  cutoffs with 96 nodes is checked separately. These figures describe integration
  sensitivity for this case, not total accuracy.
- Air/water finite fields, reduced core current in air and enhanced core current
  in water; air-limit saturation and bounded internal potential; source-current
  scaling; conductivity scaling at fixed current;
  reflection/translation symmetry; residual and mode balance; domain extension
  using matching central cells at fixed dx=dz=1.25 m and fixed k cutoffs;
  rejection of invalid geometry, conductivity, surface anomalies and quadrature.

## Remaining limitations and next step

Primary-valued outer walls need adequate distance. Grid-aligned layers are easier
to represent than a stair-stepped tunnel; high contrasts can degrade conditioning,
and cell-center current estimates require care at material jumps. Positive
finite conductivity avoids a singular insulating material but does not guarantee
accuracy. Surface anomalies are unsupported. Repeated Fourier sparse solves are
more expensive than the original 2D model. The current [live app](LIVE_APP.md)
uses debouncing, cancellation and mesh budgets; its field explorer has a
bounded source cache. These controls manage cost rather than certify accuracy.

At the Step 2 milestone, the planned next stage was surface receiver sampling with the exact primary plus
interpolated secondary, consistent voltage polarity and geometric factors, then
homogeneous apparent-resistivity checks. The separate [2.5D notebook](../verification_2p5d.ipynb),
live interface and field explorer are now complete. These tests do not establish ERT survey accuracy, Onyx tunnel
visibility, or field validation.
