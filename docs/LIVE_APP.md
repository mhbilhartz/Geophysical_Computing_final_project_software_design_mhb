# Survey upgrade, Step 7: live Panel controls

The default [app.py](../app.py) now launches the 2.5D survey interface in
[survey_app.py](../tunnel_resistivity/survey_app.py). It calls the existing grid,
geometry, source-pair, receiver and survey modules. Neither numerical solver nor
receiver method was replaced. The original interface is retained in its existing
module and launched through [legacy_app.py](../legacy_app.py).

## Launch in a browser

From the repository root with the project requirements installed:

```bash
python -m panel serve app.py --show
```

Windows Git Bash with the environment created earlier:

```bash
./.sim-venv/Scripts/python.exe -m panel serve app.py --show
```

Or Windows PowerShell with a `.venv` environment:

```powershell
.\.venv\Scripts\python.exe -m panel serve app.py --show
```

Use your actual environment directory. Keep this server running. To reload new
code, stop **this** server with Ctrl+C and launch it again; other terminals and
kernels do not need restarting. This is a Python-backed application: a static
HTML file cannot rerun the numerical calculations.

The initial air-filled survey starts automatically. There is **no Run button**.
The browser receives controls before the first survey completes and reports
progress as source pairs finish.

## Use inside an existing JupyterLab

Use a kernel with the project dependencies, with the notebook in the repository
root. This does not require restarting another kernel or inversion:

```python
import panel as pn
pn.extension()
from tunnel_resistivity.survey_app import SurveySimulatorApp

simulation = SurveySimulatorApp()
simulation.view
```

Keep that kernel alive. Before replacing this simulation instance, clean up its
own worker:

```python
simulation.close()
```

Do not paste terminal commands directly into Python cells. The original
`from tunnel_resistivity.app import create_app` still opens the original
fixed-voltage interface; use the import above for the electrode-survey model.

## Controls and spacing conventions

The controls are organized into three expandable groups:

- **Tunnel and host:** air/water/custom presets, editable Custom resistivity,
  host resistivity, radius and depth sliders, and horizontal-position slider.
  Resistivities are Ω·m, distances meters. Depth is to the center. The UI keeps
  depth at least radius+0.5 m. The selected preset is authoritative, including
  if a delayed disabled-field event arrives from the browser.
- **Electrode survey:** array type; 4–21 physical electrodes; line pitch p;
  first electrode x; maximum level; injected current; and the applicable
  Schlumberger receiver or dipole-length spacing. Changing an array/count
  adjusts valid level/spacing limits visibly. Inputs remain on a fixed physical
  line rather than being snapped to mesh cells.
- **Grid and domain:** Automatic uses a cell-size upper bound and padding
  factor; Manual accepts x faces, bottom depth, nx and nz. Actual dimensions and
  cell sizes appear in the plan summary. Invalid manual geometry is rejected;
  domains are not silently resized. The live app caps grids at 100,000 cells and
  surveys at 120 measurements before submitting expensive work.

All valid translations for levels 1 through the selected maximum are computed.
For Wenner level q, a=q·p. For Schlumberger, A–M=N–B=q·p, while MN is the receiver
spacing multiplier times p. For dipole–dipole, n=q and AB=MN is the dipole-length
multiplier times p. Its B–M gap is n·AB. Only the applicable spacing control is
shown. See [survey definitions](SURVEYS.md).

The minimum/coarsest planning rules still apply when a requested maximum cell
size is larger than the target or spacing permits. Consequently the actual
cells may be finer than the selected upper bound. Small tunnels, shallow roofs
or broad surveys can exceed the budget; reduce demands or use an appropriate
manual grid. See [grid rules and limitations](GRIDS.md).

## Automatic updates, cancellation and result labeling

The UI watches slider **value** changes, not only a button or mouse-release
event. It immediately validates a small immutable plan and shows counts/bounds.
After a **400 ms pause**, the latest plan is sent to a per-session background
worker. Rapid edits replace pending snapshots instead of queueing every slider
position. The controls remain usable during computation.

If another edit arrives during a calculation, its cancellation event is set.
`forward_survey` checks cancellation between source groups and after the current
source solve; SciPy's running sparse solve is allowed to finish. No partial
survey is returned. The next valid pending request then runs. Result, error and
progress callbacks all check the request generation, so an older request cannot
replace newer data or overwrite the current status—even if a worker ignores
cancellation. Invalid edits also invalidate older work.

This requires time to compute: a complete default survey uses nine source
solves, each with 64 Fourier modes. Larger cases can take much longer than one
slider event. Source-pair progress and pending status keep this explicit; the
UI does not promise instantaneous full-survey calculations.

Completed data remain labeled with their own geometry, material values and grid.
The Latest/Previous tabs retain two completed snapshots in that session.
Pending/invalid controls do not relabel old plots as current, and download is
disabled until a current request completes. Errors retain the last completed
view. Reset restores defaults in one batch and schedules another automatic run.
Browser sessions have independent controls, histories and workers. Destroying a
server session, or calling `close()` in a notebook, cancels its work and stops
its own executor. Other sessions/kernels are unaffected.

## Views, data and diagnostics

This stage provides the basic interface views needed to use the survey backend:

- A resistivity cross-section with the circular tunnel and physical electrode
  line. World x coordinates and depth orientation match the prepared grid.
- Apparent resistivity versus full spread midpoint, grouped by spacing level,
  with the homogeneous host reference. Profiles are forward measurements,
  not recovered tunnel geometry or an inverted depth section.
- An ordered measurement table with A/B/M/N coordinates, VM−VN, signed K,
  apparent resistivity and relative anomaly.
- Source count, elapsed time, relative Fourier-mode residual/balance, and grid
  notes when present. These diagnostics do not certify boundary or geometry accuracy.

CSV download follows the selected Latest/Previous tab and uses that completed
snapshot, with source/receiver coordinates,
voltages, K, apparent resistivity, grid/Fourier settings, conductivity hash, and
explicit tunnel/material/line settings. Dipole–dipole negative K and negative
homogeneous voltages are preserved. Material conductivity remains positive and
finite; air is a finite high resistivity. The homogeneous reference is the
analytical primary already used by the verified solver.

[Step 8 visualizations](VISUALIZATIONS.md) now add a measurement selector and
three explorer tabs below these completed-survey views: four field maps, surface
potential difference, and a survey configuration map. The explorer follows the
Latest/Previous snapshot and offers a selected-field PNG download. An uncached
selection runs one additional existing source-pair solve; it does not rerun the
whole survey. The retained original application continues to offer its original
four field plots for the fixed-voltage problem. No inversion or field calibration
is implemented here.

## Tests actually executed for Step 7

The existing **131 tests passed before changes**. Nineteen additional tests
cover debounce, latest-only scheduling, cooperative cancellation, stale results,
stale progress/errors, cleanup, parameter/grid handling, presets/custom input,
control propagation, real production-backed runs, comparisons, CSV and Bokeh
serialization. The final complete run **passed all 150 tests in 52.232 s**. Run:

```bash
python -m unittest discover -s tests -p test_live_survey.py -v
python -m unittest discover -s tests -v
```

Live headless Chromium testing used the real Panel server and native browser
selects, numeric fields, slider key events and download controls. It verified
initial automatic rendering; electrode count and water preset updates; Custom
homogeneous recovery and CSV; radius/depth updates; dipole selection and signed
factors; invalid manual-domain retention; Reset followed by a new completed
survey; and absence of JavaScript page errors. A separate isolated Jupyter-kernel
check verified display plus actual automatic initial/preset calculations. A selected-tab export regression
also checks that switching tabs cannot download the other snapshot's data.
The final browser runs passed **13 checks** with no JavaScript page errors,
including independent Schlumberger MN spacing, dipole length, source-current
scaling and CSV exports for both result tabs. The selected-tab export defect
found during review was corrected and covered by an automated regression test.

The browser checks initially used a wait too short for the full default Reset
calculation. Extending that test wait allowed the full calculation to finish;
no change to numerical results was needed. Local server/browser/kernel startup
used the execution tool's approved local-socket permission after the command
sandbox blocked those sockets. No public server or environment publication was
created. Windows/macOS commands are documented but were not executed here.

Saved smoke-check evidence is regenerable under ignored `outputs/live_app/`:
`browser_checks.json`, browser screenshots and `notebook_smoke.ipynb`. The
production [tests](../tests/test_live_survey.py) provide reproducible automated
coverage; the saved smoke notebook records the isolated notebook check.
