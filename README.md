# Underground Tunnel Electrical Resistivity Simulator

**Molly Bilhartz · GPGN 436, Geophysical Computing · Fall 2026**

Motivated by our field investigation of the historic **Onyx mine in Steamboat
Springs, Colorado**, this project explores how tunnel properties affect DC
surface measurements. The default Panel application is now a **2.5D point-electrode
survey forward modeler** for Wenner, Schlumberger and dipole–dipole arrays, with
visible Python finite differences and a circular tunnel in a uniform host.
Conductivity is independent of cross-line distance while point-source current
spreads in 3D. No specialized geophysical simulation package or inversion is used.
No Onyx field data or instrument-detection threshold is used.

- [2.5D solver](tunnel_resistivity/solver_2p5d.py), [receivers](tunnel_resistivity/receivers.py),
  [surveys](tunnel_resistivity/survey.py), and [grid planning](tunnel_resistivity/grid.py)
- [Live Panel interface](tunnel_resistivity/survey_app.py), launched through [app.py](app.py)
- [Original fixed-voltage solver](tunnel_resistivity/solver.py) and
  [original interface](tunnel_resistivity/app.py), launched through [legacy_app.py](legacy_app.py)
- [Executed original 2D verification](verification.ipynb) and
  [2.5D source/receiver verification](verification_2p5d.ipynb)
- [Geophysical analysis and interpretation](analysis/README.md)
- [Submission checklist](SUBMISSION_CHECKLIST.md) and [final reproducibility review](FINAL_REVIEW.md)
- [AI-use disclosure](AI_USE.md) and [references](REFERENCES.md)

## Browser website — updated course requirement

The browser version uses **Pyodide in a Web Worker**, with **GitHub Actions →
GitHub Pages** deployment and **no simulation backend server**. It reuses the
existing Python solver. The desktop Panel application and both executed
verification notebooks remain available.

Target runnable URL:
<https://mhbilhartz.github.io/Geophysical_Computing_final_project_software_design_mhb/>

Deployment requires Pages to use **GitHub Actions** and the workflow to finish
successfully. See [browser deployment and phone instructions](docs/BROWSER_DEPLOYMENT.md)
for the one-time repository setting, current-runtime requirements, controls and
local reproduction. The updated submission asks for this runnable website URL;
the repository URL supplies code and verification evidence.

First use downloads about 45 MB of Python/scientific packages. Controls update
automatically, and the four maps stack on a phone. The browser has smaller
workload limits than the desktop app. The Pyodide build uses compatible
WebAssembly library versions; it does not install the desktop wheels below.

## Desktop installation and Panel launch

**Survey-upgrade status:** Steps 1–6 are connected by the
[Step 7 live interface](docs/LIVE_APP.md). Tunnel radius/depth sliders, material
presets/custom resistivity, electrode geometry and automatic/manual grids now
rerun the existing survey backend automatically. A background worker coalesces
rapid edits, cancels superseded work between source solves, and prevents stale
results from replacing the latest request. [Step 8 visualizations](docs/VISUALIZATIONS.md)
add selected-measurement potential, current and anomaly maps, a surface-potential
difference curve, and a survey configuration map alongside profiles and diagnostics.
The [Step 9 final review](FINAL_REVIEW.md) records current regression,
clean-install and notebook reproduction evidence, plus remaining GitHub and
submission actions. The [original review](docs/LEGACY_FINAL_REVIEW.md) is retained
as historical evidence for the fixed-voltage model.

Numerical details: [electrode geometry](docs/ELECTRODE_GEOMETRY.md),
[2.5D source pairs](docs/SOURCE_PAIR_2P5D.md), [receiver calculations](docs/RECEIVER_MEASUREMENTS.md),
[verification](docs/VERIFICATION_2P5D.md), [surveys](docs/SURVEYS.md), and
[grid/domain planning](docs/GRIDS.md). The two executed verification notebooks
remain separate for the original fixed-voltage and new 2.5D models.

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

### Windows Git Bash with an existing simulation environment

If your working environment is named `.sim-venv`, use its interpreter directly:

```bash
./.sim-venv/Scripts/python.exe -m pip install -r requirements.txt
./.sim-venv/Scripts/python.exe -m panel serve app.py --show
```

Use your actual environment name. These are terminal commands. For a notebook,
use the Python example below and select the kernel for this environment; a new
terminal tab alone does not select a different Jupyter kernel.

Panel opens the app in a local browser. Keep its terminal running; stop with
Ctrl+C. The initial air-filled survey runs automatically in the background.
Changes rerun after a 400 ms pause; **no Run button is needed**. Full surveys take
seconds or longer depending on the selected grid and number of source pairs.
Python callbacks
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

## Use the live controls and inspect results

| Control | Meaning |
| --- | --- |
| Tunnel radius and center depth | Sliders in meters; depth must exceed radius by at least 0.5 m in the UI |
| Tunnel horizontal position | World x in meters; automatic bounds include the tunnel and electrode line |
| Host/tunnel resistivity | Ω·m; Air-filled=1e8, Water-filled=5; Custom enables the tunnel value |
| Array | Wenner, Schlumberger, or dipole–dipole |
| Electrode count, line pitch and first x | A fixed physical surface line; electrode positions are not snapped to cells |
| Maximum level | All valid translations for levels 1 through the selected level |
| Schlumberger MN / pitch | Independent receiver spacing; displayed for Schlumberger |
| Dipole length / pitch | AB=MN; displayed for dipole–dipole |
| Source current | Positive amperes, with A injecting and B withdrawing |
| Automatic grid | Cell-size upper bound and boundary-padding factor |
| Manual grid | Left/right faces, bottom depth, nx and nz |

Spacing/level limits adjust to keep the requested array on the physical line.
Source/receiver conventions and counts are explained in [the live-app guide](docs/LIVE_APP.md).
Material presets are illustrative. Conductivity stays positive and finite;
air is never represented by zero conductivity. Automatic grid sizes are planning
heuristics, not error-certified boundaries. Invalid geometry, resistivity, or
oversized plans produce an error while retaining clearly labeled completed data.

Moving sliders or editing fields updates the requested plan immediately. After
a brief pause, a per-session background calculation starts. Changes during a
calculation signal cancellation, effective after the current sparse source solve
finishes; only the latest requested snapshot may publish. Controls stay active.
The status reports completed source pairs. Old data remain labeled with their
own parameters until a new survey completes, and CSV download is disabled while
the request is pending/invalid. Reset restores defaults and reruns automatically.

The result views contain a resistivity cross-section and electrode line,
apparent-resistivity profiles at each level, ordered measurement data and
mode residual/balance diagnostics. The Latest/Previous tabs retain two completed
snapshots. CSV download includes geometry/settings and numerical data for the
displayed completed snapshot. These profiles are forward data, not a depth image
or inversion. Finite walls, stair-stepped circles and Fourier integration still
need sensitivity checks.

Below the completed survey, **Inspect measurement from displayed survey** chooses
the A/B source pair and M/N receivers for the field explorer. Its three tabs show
four field maps, surface ΔV, and measured survey configurations. The selected
field PNG download follows the Latest/Previous snapshot. Current arrows show
direction; colors show magnitude. The configuration map's vertical axis is
spacing level, not depth. See [the visualization guide](docs/VISUALIZATIONS.md)
for scales, caching and interpretation limits.

**Try the controls:**

1. Start with defaults, then choose Water-filled; wait for the completion status
   and compare with the previous snapshot.
2. Choose Custom and set tunnel resistivity equal to the host. Every apparent
   resistivity should recover that host value; the homogeneous reference is
   analytical in this primary/secondary solver.
3. Move radius/depth sliders. The plan and results update automatically after
   computation. Rapid movement is coalesced rather than queueing every position.
4. Change arrays, spacing, levels or grid mode and inspect source counts,
   grid dimensions, signed K and VM−VN. Dipole–dipole normally has negative K
   and homogeneous voltage under this label ordering.

For JupyterLab, use your project environment's kernel:

```python
import panel as pn
pn.extension()
from tunnel_resistivity.survey_app import SurveySimulatorApp
simulation = SurveySimulatorApp()
simulation.view
```

The kernel must remain running. Before replacing that instance, call
`simulation.close()` to cancel its own worker; this does not stop other kernels.
See [LIVE_APP.md](docs/LIVE_APP.md) for launch and test details.

### Original fixed-voltage comparison application

Launch `python -m panel serve legacy_app.py --show` to use the retained original
interface and four field plots. The instructions/results in this subsection
apply to that original model, with fixed side voltages and current per unit
cross-line thickness, rather than point-electrode survey data.


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

At the original application's default **160×80** UI grid, depth 15 m, radius 5 m, and host 100 Ω·m:

| Model | Total current (A/m) | Peak absolute surface anomaly (mV) |
| --- | ---: | ---: |
| Homogeneous | 0.00500000 | 0 |
| Air, 1e8 Ω·m | 0.00482530 | 16.190 |
| Water, 5 Ω·m | 0.00514558 | 13.478 |

## Governing equation and numerical method

Steady conduction away from source electrodes satisfies

$$
\nabla\cdot(\sigma\nabla V)=0,\qquad \mathbf J=-\sigma\nabla V,
\qquad \sigma=1/\rho.
$$

Coordinates x and depth z are in meters, V in volts, conductivity σ in S/m,
resistivity ρ in Ω·m, and current density J in A/m². The model is steady elliptic:
there is **no initial condition and no time step**.
In the point-electrode application, surface injection is supplied by the
source/return primary field. The source-free equation does not apply at the
singular electrode points themselves.

### Live 2.5D point-electrode application

The new solver separates an analytical homogeneous primary from numerical
secondary Fourier modes. With conductivity independent of y,

$$
A_\sigma(k)\widehat V_s=
-\partial_x(\sigma\partial_x\widehat V_s)
-\partial_z(\sigma\partial_z\widehat V_s)+k^2\sigma\widehat V_s.
$$

The contrast-forcing right-hand side, harmonic interfaces and primary treatment
are derived in [the source-pair notes](docs/SOURCE_PAIR_2P5D.md). The top secondary
normal derivative is zero; side/bottom secondary potential is zero. The exact
primary carries surface injection and fixes total potential at artificial walls.
The physical field at y=0 is Vprimary+∫Vhat_secondary dk/π. Sources are amperes,
not A/m line sources. The existing Python assembly and SciPy sparse solves remain
visible; the interface calls this backend rather than implementing another solver.

Receiver voltages use the analytical surface primary plus reconstructed secondary.
For VM−VN, signed K=2π/(1/AM−1/BM−1/AN+1/BN) gives apparent resistivity K·ΔV/I
in Ω·m. Homogeneous recovery is exact by construction; the separate notebook also
checks a nonzero layered-earth response and manufactured spatial convergence.
See [receiver notes](docs/RECEIVER_MEASUREMENTS.md) and
[verification](verification_2p5d.ipynb). The original method below belongs to
`legacy_app.py` and its independent verification notebook.

### Original fixed-voltage 2D method

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
python -m tunnel_resistivity.demo_2p5d
python -m tunnel_resistivity.receiver_demo
python -m tunnel_resistivity.survey_demo
python -m tunnel_resistivity.grid_demo
python -m tunnel_resistivity.visualization_demo
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tunnel_resistivity.demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.tunnel_demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.demo_2p5d
.\.venv\Scripts\python.exe -m tunnel_resistivity.receiver_demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.survey_demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.grid_demo
.\.venv\Scripts\python.exe -m tunnel_resistivity.visualization_demo
```

There are **176 tests**, covering analytical/physical solver checks, harmonic
interfaces, geometry, current conservation, UI callbacks, plot data/axes,
analysis measures, electrode geometry, the 2.5D solver, receiver measurements,
signed apparent resistivity, survey geometry/forward calls/source reuse,
automatic/manual grid planning and model preparation, live parameter handling,
background generation/cancellation, failure handling, selected-source field reuse,
receiver labels, snapshot-safe PNG exports, and field/surface/survey plot data.
They do not require a browser. The 2.5D tests include a nonzero layered-earth
response, manufactured-mode refinement, Fourier integration and domain checks;
see [the Step 2 numerical notes](docs/SOURCE_PAIR_2P5D.md) and
[Step 3 receiver benchmarks](docs/RECEIVER_MEASUREMENTS.md). Historical
checks are recorded in [TESTING_REPORT.md](TESTING_REPORT.md); the final clean
review is in [FINAL_REVIEW.md](FINAL_REVIEW.md). Historical milestone test counts
in the numerical guides describe their respective stages; the current suite has
176 tests including the browser adapter.

Static examples write regenerable files under ignored `outputs/`. The homogeneous
example should have linear V, Jx=1e-4 A/m², Jz≈0 and total current 0.005 A/m.
The tunnel example writes air/water four-panel figures and surface profiles.
It supports `--help`, geometry/resistivity/grid arguments, and `--output-dir`.

## Reproduce analytical verification

[verification.ipynb](verification.ipynb) imports the **same production solver**
as the retained original application (`legacy_app.py`), independently of Panel. It derives the exact logarithmic solution for
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

### New 2.5D source/receiver notebook

Open [verification_2p5d.ipynb](verification_2p5d.ipynb) in JupyterLab and select
the same project environment's kernel:

```bash
python -m jupyterlab verification_2p5d.ipynb
```

Use **Restart Kernel and Run All Cells**, then save. Its larger mesh/domain
experiments may take several minutes. Embedded plots/tables remain readable
without rerunning. CSV/JSON and PNG/PDF copies are regenerated under ignored
`outputs/verification_2p5d/`. For command-line reexecution to a separate copy:

```bash
python -m nbconvert --to notebook --execute verification_2p5d.ipynb --output verification_2p5d.reexecuted --output-dir outputs/verification_2p5d --ExecutePreprocessor.timeout=360 --ExecutePreprocessor.kernel_name=tunnel-resistivity
```

On Windows, prefix the module commands with `.\.venv\Scripts\python.exe` in
place of `python`. The same commands work with another environment name when
using that environment's interpreter and matching Jupyter kernel.
This notebook imports the production 2.5D backend now used by the live Panel
application (`app.py`). It does not replace the original 2D verification.
The [verification guide](docs/VERIFICATION_2P5D.md) explains the analytical
references, error denominators and limits on convergence claims.

## Reproduce original fixed-voltage geophysical experiments

These historical experiments use the original 2D boundary-value problem, not
the new surface electrode surveys. Their reported A/m currents and potential
anomalies must not be interpreted as apparent resistivity.

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
- The original model's fixed side voltages are idealized. The live 2.5D app uses
  point-electrode arrays, with approximate primary-valued outer walls.
- Stair-stepped circles change area/interface shape with resolution; surface
  values are first-row zero-gradient reconstructions. Small residuals and good
  conservation do not establish geometric accuracy.
- Large contrasts affect conditioning; air is a finite-resistivity approximation.
- Original-model surface potential anomalies are not apparent resistivity.
  The new app explicitly models electrode spacing and apparent resistivity, but
  neither model includes instrument noise, contact effects or site calibration.
- The experiments explain electrical physics relevant to underground voids but
  **do not establish actual Onyx mine tunnel detectability**.

## Repository map

```text
app.py                         Live 2.5D survey Panel entry point
legacy_app.py                  Original fixed-voltage Panel entry point
tunnel_resistivity/
  solver.py                    Visible numerical assembly and sparse solve
  geometry.py                  Circular conductivity array
  electrodes.py                Surface electrode geometry (survey Step 1)
  solver_2p5d.py                Fourier source-pair backend (survey Step 2)
  demo_2p5d.py                  Static source-pair comparison
  receivers.py                 Surface voltages and apparent resistivity (Step 3)
  receiver_demo.py             Static single-measurement comparisons and CSV
  survey.py                    Surface survey planning, forwarding and CSV (Step 5)
  survey_demo.py               Reproducible small surveys and profile plots
  grid.py                      Domain/grid planning and model preparation (Step 6)
  grid_demo.py                 Automatic footprints and grid/domain comparisons
  simulation.py                UI parameter validation and orchestration
  app.py                       Original fixed-voltage controls and views
  survey_simulation.py         Immutable live survey settings and orchestration
  live.py                      Debounce, background work and generation protection
  survey_app.py                Live Panel survey controls and completed views
  fields.py                    Selected-source solves and bounded field cache
  survey_plotting.py           Model/profile, field, surface and survey maps
  visualization_demo.py        Reproducible 2.5D field/map PNG/PDF and arrays
  browser.py                   Worker adapter calling the existing solver
  plotting.py, diagnostics.py  Shared plots and face-current diagnostics
  demo.py, tunnel_demo.py      Static working examples
tests/                         176 automated tests
verification.ipynb             Executed analytical verification (saved outputs)
verification_2p5d.ipynb        Executed 2.5D backend verification (survey Step 4)
analysis/run_experiments.py     Reproducible controlled experiments
analysis/README.md             Scientific interpretation
analysis/results/              Tracked CSV, PNG, PDF and provenance files
docs/                          Numerical/user guides and historical review
presentations/                 Historical original-model idea discussion
web/                           Static responsive browser UI and Web Worker
scripts/                       Static build and real browser tests
.github/workflows/pages.yml    GitHub Actions testing and Pages deployment
requirements*.txt              Runtime, notebook and browser-test dependencies
AI_USE.md, REFERENCES.md        Assistance disclosure and references
SUBMISSION_CHECKLIST.md         PDF requirements and remaining student actions
FINAL_REVIEW.md                 Fresh-install evidence, file list and Git status
```

No external numerical code or specialized simulator was incorporated. See
[AI_USE.md](AI_USE.md) for Codex's contribution and student responsibilities,
and [REFERENCES.md](REFERENCES.md) for the course document and method/library
references. The repository must still be committed, pushed, made accessible to
the instructor, and its link submitted on Canvas after the student's review.
