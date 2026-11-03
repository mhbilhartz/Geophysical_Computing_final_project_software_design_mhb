# Underground Tunnel Electrical Resistivity Simulator

**Molly Bilhartz · GPGN 436, Geophysical Computing · Fall 2026**

Motivated by our field investigation of the historic **Onyx mine in Steamboat
Springs, Colorado**, this project asks how tunnel depth, radius, and electrical
contrast affect potential and current flow near the surface. It is a Python
finite-difference **2D DC forward model**, with a circular tunnel in a uniform
host and a Panel interface. It is not an ERT electrode-array model or inversion.
No Onyx field data or instrument-detection threshold is used.

- [Numerical solver](tunnel_resistivity/solver.py) and [tunnel geometry](tunnel_resistivity/geometry.py)
- [Panel interface](tunnel_resistivity/app.py), launched through [app.py](app.py)
- [Executed analytical verification](verification.ipynb)
- [Geophysical analysis and interpretation](analysis/README.md)
- [Submission checklist](SUBMISSION_CHECKLIST.md) and [final reproducibility review](FINAL_REVIEW.md)
- [AI-use disclosure](AI_USE.md) and [references](REFERENCES.md)

## Install and launch

Use **Python 3.12**. Run all commands from the repository root after downloading
or cloning the complete project. No external dataset is needed.

### Linux/macOS (bash/zsh)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m panel serve app.py --show
```

### Windows PowerShell

These commands call the environment's Python directly, so PowerShell activation
and execution-policy changes are unnecessary:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m panel serve app.py --show
```

Panel opens the app in a local browser. Keep its terminal running; stop with
Ctrl+C. The initial air-filled simulation runs automatically. Python callbacks
require this live server; a static HTML export cannot rerun the solver. Remote
machines require their supported port-access mechanism; no public deployment is
configured here. Omit `--show` on a headless machine.

**Tested platforms:** the fresh-install review used Linux with Python 3.12.
The PowerShell instructions and equivalent macOS commands are provided, but
Windows and macOS execution have not been tested in this Linux environment.

For the cloud machine's read-only home directory, set writable cache/config
locations before the Linux commands. Ordinary desktop installations may omit this:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/tunnel-mpl
export XDG_CACHE_HOME=/tmp/tunnel-cache
export IPYTHONDIR=/tmp/tunnel-ipython
export JUPYTER_CONFIG_DIR=/tmp/tunnel-jupyter-config
export JUPYTER_RUNTIME_DIR=/tmp/tunnel-jupyter-runtime
```

## Use the controls and inspect results

| Control | Meaning and supported values |
| --- | --- |
| Tunnel center depth | Meters downward from the top, not depth to the tunnel roof |
| Radius | 2–10 m |
| Horizontal center | Meters from the left boundary |
| Background resistivity | 10–10,000 Ω·m |
| Tunnel resistivity | 1–100,000,000 Ω·m; editable under Custom |
| Preset | Air-filled: 1e8 Ω·m; water-filled: 5 Ω·m; Custom |
| Grid | 80×40, 160×80 (default), or 240×120 cells |

Position bounds adjust with radius to keep the intended circle at least 0.5 m
inside the 100×50 m UI domain. Presets are illustrative, not measured mine
properties. Conductivity is always positive and finite; air is represented by a
large **finite** resistivity, never zero conductivity.

Change controls, then click **Run Simulation**. Plots remain labeled with the
last successful run until the new run completes. **Reset to Defaults** restores
the controls and reruns the air case. The Latest/Previous tabs retain the last
two successful scenarios in that browser session. Invalid backend parameters
produce an error and retain previous results; browser numeric fields may reject
an out-of-range entry before it reaches Python. Results do not persist across
server/session restarts. Runs are synchronous; finer grids take longer.

Four plots show resistivity (Ω·m), potential (V), current-density magnitude
(A/m²) with flow arrows, and `V_tunnel − V_homogeneous` (V). Depth increases down;
dashed outlines show the intended circle. Resistivity/current color bars use log
scales. Their ranges and the symmetric anomaly range adapt to each run: compare
color bars and arrow keys rather than colors alone. Current vectors are face
currents averaged to cell centers for display, not the data used for conservation.

The diagnostic table reports boundary currents (A/m per unit out-of-plane
thickness), current imbalance, residual, potential range, surface anomaly, grid
spacing, and cells per radius. A small residual checks the algebraic solve;
it does not establish geometric accuracy.

**Working examples:**

1. Run defaults, then Water-filled. Current should bypass the resistive tunnel
   and concentrate through the conductive one; compare both result tabs.
2. Set Custom tunnel resistivity equal to the host. The anomaly should vanish
   and potential should decrease linearly with x, with no depth variation.
3. Change depth/radius and compare grids. Coarse-grid warnings are numerical
   cautions, not evidence that a refined result is exact.

At the default **160×80** UI grid, depth 15 m, radius 5 m, and host 100 Ω·m:

| Model | Total current (A/m) | Peak absolute surface anomaly (mV) |
| --- | ---: | ---: |
| Homogeneous | 0.00500000 | 0 |
| Air, 1e8 Ω·m | 0.00482530 | 16.190 |
| Water, 5 Ω·m | 0.00514558 | 13.478 |

## Governing equation and numerical method

Steady conduction satisfies

$$
\nabla\cdot(\sigma\nabla V)=0,\qquad \mathbf J=-\sigma\nabla V,
\qquad \sigma=1/\rho.
$$

Coordinates x and depth z are in meters, V in volts, conductivity σ in S/m,
resistivity ρ in Ω·m, and current density J in A/m². The model is steady elliptic:
there is **no initial condition and no time step**.

The rectangular boundary conditions are V=1 V at the left, V=0 V at the right,
and zero normal current at the top/bottom. Insulation blocks current; it does
not fix the top/bottom potential to zero. Side voltages remove the arbitrary
potential offset of an all-insulating problem.

The solver places one unknown at each cell center, indexed `[iz, ix]`. For
uniform conductivity its interior equation is the five-point finite difference

```text
sigma * [(V_E - 2*V_P + V_W)/dx² + (V_S - 2*V_P + V_N)/dz²] = 0.
```

For variable conductivity it assembles the conservative equivalent:

```text
sum over connected faces: T_face * (V_P - V_neighbor) = 0
T_face = sigma_face * face_length / center_distance
sigma_face = 2*sigma_P*sigma_N / (sigma_P + sigma_N)
```

Harmonic averaging represents two half-cell resistances in series. Each shared
face has one conductance, used by both neighbors and the flux calculation,
which conserves current discretely. The implementation evaluates the harmonic
mean without the product of the conductivities to reduce overflow risk.

At each fixed-voltage side the boundary is **dx/2** from the adjacent center,
so its conductance is `2*sigma_cell*dz/dx`. It adds to the diagonal and multiplies
the known boundary voltage on the right-hand side. Missing top/bottom neighbors
add no flux term. The first/last cell columns are inside the domain and should
not themselves be forced to 1/0 V.

Visible Python loops assemble a SciPy sparse matrix; `spsolve` solves `A V = b`.
There is no dense inverse or specialized geophysical simulation package. Face
currents use `J_face = -sigma_face*(V_neighbor-V_cell)/distance`. Returned `jx`
has shape `(nz,nx+1)` and `jz` `(nz+1,nx)`, positive rightward/downward.
`residual_inf` is `max(abs(A@V-b))`, in A/m per unit thickness.

The [geometry helper](tunnel_resistivity/geometry.py) labels cell centers inside
`(x-center_x)² + (z-depth)² <= radius²` as tunnel material; all other cells are
host. This produces a stair-stepped circle. Empty/invalid circles are rejected;
fewer than four cells per radius triggers a warning, not an accuracy guarantee.

## Run tests and static examples

Linux/macOS, activated environment:

```bash
python -m unittest discover -s tests -v
python -m tunnel_resistivity.demo
python -m tunnel_resistivity.tunnel_demo
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tunnel_resistivity.demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.tunnel_demo
```

There are **42 tests**, covering analytical/physical solver checks, harmonic
interfaces, geometry, current conservation, UI callbacks, plot data/axes,
analysis measures, and failure handling. They do not require a browser. Historical
checks are recorded in [TESTING_REPORT.md](TESTING_REPORT.md); the final clean
review is in [FINAL_REVIEW.md](FINAL_REVIEW.md).

Static examples write regenerable files under ignored `outputs/`. The homogeneous
example should have linear V, Jx=1e-4 A/m², Jz≈0 and total current 0.005 A/m.
The tunnel example writes air/water four-panel figures and surface profiles.
It supports `--help`, geometry/resistivity/grid arguments, and `--output-dir`.

## Reproduce analytical verification

[verification.ipynb](verification.ipynb) imports the **same production solver**
independently of Panel. It derives the exact logarithmic solution for
`σ(x)=0.01*(1+2*x/100)` S/m on a 100×50 m domain with the same boundaries.
The exact potential is `V(x)=1-log(1+2*x/100)/log(3)`, evaluated at cell centers.
Relative RMSE is `RMSE/abs(V_left-V_right)`, not division by local V near zero.

| Grid | dx=dz (m) | Max error (V) | RMSE (V) | Observed RMSE order |
| --- | ---: | ---: | ---: | ---: |
| 20×10 | 5 | 1.05140696e-3 | 5.04468369e-4 | — |
| 40×20 | 2.5 | 2.73357464e-4 | 1.26338251e-4 | 1.997472 |
| 80×40 | 1.25 | 6.97069251e-5 | 3.15984775e-5 | 1.999365 |
| 160×80 | 0.625 | 1.76012134e-5 | 7.90049055e-6 | 1.999841 |

The observed orders approach two; they were not imposed. Finest relative RMSE is
0.000790% of the voltage span. The notebook includes current-density, boundary,
and local/global conservation checks, ten executed code cells, four embedded
figures, and a checklist against the professor's numerical-verification rules.
Smooth-case verification does not prove second-order tunnel-interface accuracy
and is **not validation against field measurements**.

Jupyter is optional development tooling; the app only needs `requirements.txt`.
Install it and register the same environment's kernel:

```bash
python -m pip install -r requirements-notebook.txt
python -m ipykernel install --prefix .venv --name tunnel-resistivity --display-name "Python (tunnel-resistivity)"
python -m jupyterlab verification.ipynb
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name tunnel-resistivity --display-name "Python (tunnel-resistivity)"
.\.venv\Scripts\python.exe -m jupyterlab verification.ipynb
```

Choose **Python (tunnel-resistivity)** and **Restart Kernel and Run All Cells**.
Save outputs when intentionally updating the submission notebook. To reexecute
without overwriting its completed outputs, write a separate ignored copy:

```bash
python -m nbconvert --to notebook --execute verification.ipynb --output verification.reexecuted --output-dir outputs/verification --ExecutePreprocessor.timeout=180 --ExecutePreprocessor.kernel_name=tunnel-resistivity
```

Windows uses the same arguments after `.\.venv\Scripts\python.exe -m nbconvert`.
Local Jupyter kernels require loopback sockets; the cloud command sandbox needs
its normal execution-tool permission for them. No checks should be bypassed.

## Reproduce geophysical experiments

```bash
python -m analysis.run_experiments
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m analysis.run_experiments
```

This recreates 53 records from 45 unique tunnel solves and 7 references in
[analysis/results/](analysis/results/): [summary.csv](analysis/results/summary.csv),
[surface_profiles.csv](analysis/results/surface_profiles.csv),
[trend_statistics.csv](analysis/results/trend_statistics.csv), provenance and five
PNG/PDF figures. These are tracked submission artifacts, not ignored temporary
outputs. Reruns replace them; use a separate repository copy when preserving the
submission results. Exact parameters and metric definitions are in the
[analysis report](analysis/README.md).

Main results on the **240×120** analysis grid (different from the default UI):

| Experiment | Measured finding |
| --- | --- |
| Depth 7.5 → 35 m | Air peak 38.31 → 4.25 mV; water 26.01 → 3.61 mV |
| Radius 2 → 9 m | Air 2.71 → 52.15 mV; water 2.21 → 40.45 mV; approximately quadratic growth |
| Contrast | Matched host/tunnel gives zero anomaly; air/water reverse the signed pattern; resistive response saturates |
| Medium → fine grid | Peak changes −5.45% (air), −4.23% (water); water is nonmonotonic across all three grids |
| Width 100 → 200 m | Gradient-normalized peak increases **17.62% (air), 14.15% (water)** |

Across the 53 analysis records, the maximum matrix residual is 1.11e-15 A/m
and relative boundary-current imbalance is at most 5.41e-12. These algebraic
checks do not bound the mesh/domain errors measured above.

The larger domain also has a weaker imposed gradient because the 1 V drop spans
more distance. Dividing A by E0=1 V/W distinguishes that forcing change from
boundary effects. A/E0 has units of meters and is **not apparent resistivity**.
Side boundaries significantly influence these predictions; even width 150→200 m
changes the normalized peaks by 5.39%/4.36%. Moving the bottom from 50→100 m at
width 200 m changes peaks by −5.08%/−3.98%. Domain independence is not established.

Changing both resistivities by the same factor leaves fixed-voltage potential
unchanged while scaling current inversely. The executed scaling control doubled
both resistivities and halved current with identical V. Potential alone therefore
does not determine absolute resistivity scale; geometry/contrast tradeoffs also
limit interpretation. See the [contrast and profile figure](analysis/results/03_contrast_and_profiles.png)
and [grid/domain figure](analysis/results/05_grid_domain_sensitivity.png).

## Assumptions, limitations, and field relevance

- Isotropic DC conduction and a uniform host, with simplified constant material properties.
- A circular 2D cross-section represents a tunnel infinitely long perpendicular
  to the model plane; finite ends, irregular geology, topography and electrode
  contact effects are omitted.
- Fixed side voltages are idealized and do not represent an actual ERT array.
- Stair-stepped circles change area/interface shape with resolution; surface
  values are first-row zero-gradient reconstructions. Small residuals and good
  conservation do not establish geometric accuracy.
- Large contrasts affect conditioning; air is a finite-resistivity approximation.
- Surface potential differences are not measured apparent-resistivity anomalies.
  No instrument noise, electrode spacing or site calibration is modeled.
- The experiments explain electrical physics relevant to underground voids but
  **do not establish actual Onyx mine tunnel detectability**.

## Repository map

```text
app.py                         Panel launch entry point
tunnel_resistivity/
  solver.py                    Visible numerical assembly and sparse solve
  geometry.py                  Circular conductivity array
  simulation.py                UI parameter validation and orchestration
  app.py                       Panel controls and comparison views
  plotting.py, diagnostics.py  Shared plots and face-current diagnostics
  demo.py, tunnel_demo.py      Static working examples
tests/                         42 automated tests
verification.ipynb             Executed analytical verification (saved outputs)
analysis/run_experiments.py     Reproducible controlled experiments
analysis/README.md             Scientific interpretation
analysis/results/              Tracked CSV, PNG, PDF and provenance files
requirements*.txt              Runtime and optional notebook dependencies
AI_USE.md, REFERENCES.md        Assistance disclosure and references
SUBMISSION_CHECKLIST.md         PDF requirements and remaining student actions
FINAL_REVIEW.md                 Fresh-install evidence, file list and Git status
```

No external numerical code or specialized simulator was incorporated. See
[AI_USE.md](AI_USE.md) for Codex's contribution and student responsibilities,
and [REFERENCES.md](REFERENCES.md) for the course document and method/library
references. The repository must still be committed, pushed, made accessible to
the instructor, and its link submitted on Canvas after the student's review.
