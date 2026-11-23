# Browser-only simulator: Pyodide, Web Worker and GitHub Pages

This implements the professor's updated deployment architecture: **Python runs
in Pyodide inside a Web Worker; GitHub Actions builds and deploys static files
to GitHub Pages; no Python/Panel backend server is deployed.** The submission
URL must open the runnable site, rather than only the GitHub source repository.

Target website:

<https://mhbilhartz.github.io/Geophysical_Computing_final_project_software_design_mhb/>

The target becomes live after the repository's Pages setting is configured and
the **Test and deploy browser simulator** workflow succeeds. Check the workflow's
deployment URL before submitting. The repository remains available for source,
tests, saved notebooks and documentation:

<https://github.com/mhbilhartz/Geophysical_Computing_final_project_software_design_mhb>

## First use, including a phone

Open the website in a current Chrome, Firefox, Edge or Safari with JavaScript and
WebAssembly enabled. The first visit downloads approximately **44.3 MiB** of
Python/scientific runtime files; ordinary browser caching helps subsequent visits.
Keep the page open during loading and computation. No Python installation,
terminal, account or local server is needed by visitors.

The status panel appears above the controls on narrow screens. Choose **View
results** to jump below them. Default browser parameters use seven physical
electrodes, two Wenner levels, host 100 Ω·m and a 5 m radius tunnel at (50,15) m.
The desktop Panel app retains its nine-electrode default.

- Radius, center depth and horizontal position are sliders. Depth is to the
  center. Valid changes rerun automatically after a 400 ms pause.
- Air/water presets set 1e8/5 Ω·m; Custom enables explicit tunnel resistivity.
  All conductivities remain positive and finite.
- Wenner, Schlumberger and dipole–dipole arrays use the existing physical
  electrode-line definitions and independent applicable spacing controls.
- Automatic and manual grids call the existing production planning/validation.
  Browser budgets are 32,768 cells, 32 unique source solves and 48 measurements.
  The source budget covers every electrode/level combination offered by the UI.
  An oversized grid is rejected; the grid is never silently coarsened.
- Uncheck automatic updates to make several edits, then use **Update simulation**.
  This is optional; the sliders do not require a Run-button click.
- A calculation already running in the worker finishes before the latest queued
  request starts. Old results cannot replace a newer requested scenario.
- **Stop calculation** terminates the worker immediately, reloads Python and
  pauses automatic updates. This clears in-memory comparison history. This uses
  standard Worker termination, not SharedArrayBuffer or special Pages headers.
- Latest/Previous scenarios retain two completed results. Measurement selection
  reuses a source field when possible and labels the requested M/N receivers.
  CSV and PNG downloads follow the selected completed scenario.
- Four separate field panels stack vertically on a phone. Tap a plot to open
  the figure dialog, then choose **Actual size** to inspect labels and arrows.
  Surface curves, a survey map, profiles and a measurement table are also included.

Cold startup plus the initial survey took about 40 seconds in the first local
Chromium test. Runtime depends on device, connection, source count and grid.
Phone viewport testing is browser emulation, not a claim that every physical
phone has been tested. Large jobs remain better suited to the retained desktop
application.

## What actually runs

`web/app.js` manages controls, debounce, request generations, snapshots and
image/CSV downloads. It creates `web/worker.js` using the standard Worker API.
The worker loads Pyodide, checks and unpacks the published Python source archive,
and calls `tunnel_resistivity/browser.py`.

The adapter imports the same production `solver_2p5d.py`, `receivers.py`,
`survey.py`, `grid.py`, `survey_simulation.py` and `fields.py` used by the Panel
application. It adds browser workload limits, serializable results and exports
of the existing Matplotlib axes; it contains no alternate PDE assembly or solver.
Python computation and plotting stay off the browser's UI thread. The native
browser interface avoids Panel's server/thread runtime; Panel remains available
through `app.py` on a user's computer.

The browser build pins **Pyodide 0.27.7 / Python 3.12.7**, with its compatible
**NumPy 2.0.2, SciPy 1.14.1 and Matplotlib 3.8.4**. These are the WebAssembly
packages shipped by that Pyodide release, not the desktop CPython wheels in
`requirements.txt`. Both numerical outputs and three original independent tests
are checked in the actual browser runtime. CSVs record package versions.

The build downloads the runtime and its dependency closure, validates scientific
wheel SHA-256 checksums against the versioned Pyodide lock, and bundles it under
`pyodide/`. Runtime files are then served by Pages itself; visitors do not need a
separate CDN or backend connection. Pyodide's license and distribution-wheel
licenses are retained. Source hashes and the source-archive digest are in
`runtime-config.json`. The worker checks the archive before importing it.

## GitHub Actions and the one-time repository setting

The workflow is [.github/workflows/pages.yml](../.github/workflows/pages.yml).
It runs on pushes to `main` and by manual dispatch. It:

1. Installs native test requirements and runs the complete Python suite.
2. Checks JavaScript syntax and builds an allowlisted static artifact.
3. Runs the real Pyodide/Chromium suite, including phone layout and independent
   numerical tests, and saves browser evidence as an Actions artifact.
4. Uploads the static Pages artifact and deploys with GitHub's official Pages
   actions using `pages: write` and `id-token: write`.

A repository owner may need to set **Settings → Pages → Build and deployment →
Source → GitHub Actions** once. GitHub's standard workflow token can deploy an
already enabled Pages site; the official configure-pages action does not grant
it permission to enable a new site automatically. No personal token is stored
in this repository. If a first run reports Pages is not configured, make that
setting change, then choose **Actions → Test and deploy browser simulator → Run
workflow** on `main` (or rerun the failed workflow).

An account setting or a failed deployment must not be reported as a successful
live website. The code repository URL alone does not satisfy the new submission
requirement. Verify the Pages URL loads Python and produces results before
submitting it. The project should still link its repository for numerical code
and saved analytical verification.

## Reproduce locally

From a project environment at the repository root:

```bash
python -m pip install -r requirements-web-test.txt
python -m unittest discover -s tests -v
python scripts/build_pages.py --output-dir outputs/site --vendor-runtime
python -m playwright install chromium
python scripts/test_browser.py --site-dir outputs/site --output-dir outputs/browser-tests
```

The test driver temporarily serves static files and launches Chromium. That
server is a local test fixture, not a simulation backend. To inspect the built
site manually, use a normal static server:

```bash
python -m http.server 5050 --directory outputs/site
```

Then open `http://localhost:5050/`. Opening `index.html` directly as `file://`
will not load the worker and WebAssembly correctly. The Pages site uses HTTPS.
Generated runtime binaries and site artifacts live under ignored `outputs/`
(or `site/`) and are not committed; GitHub Actions reproduces them.

## Scientific scope and verification

The original numerical solvers, original tests and both executed verification
notebooks remain intact. The browser adapter has separate native tests for
preset handling, budgets, payload/reference consistency, retention and artifact
contents. The actual Chromium suite compares a nonzero tunnel survey with the
native production solver, checks matched-material recovery, current scaling,
arrays, stale results, invalid inputs, cancellation and a fresh phone-sized
runtime.

Three original `IndependentNumericalChecks` tests from `test_solver_2p5d.py`
are also executed inside Pyodide: the Bessel/Fourier integral identity,
manufactured-mode spatial refinement, and piecewise-conductivity harmonic flux
and boundaries. Those reuse the existing tests and production operator; the
JavaScript does not replace the solver or mock its responses.

The scientific limitations from the [verification guide](VERIFICATION_2P5D.md)
remain: finite outer walls, quadrature cutoffs, stair-stepped circles, high
contrasts and approximate cell-center currents. The model has a flat surface
and an infinite tunnel axis, with no inversion or field-calibrated detection
threshold. Plot colors have per-scenario scales; arrows show direction. The
survey map's spacing-level axis is not depth.

## Local checks executed before publication

- All **167 pre-existing tests** passed before the browser changes.
- The complete native suite passed **174 tests in 123.400 s**, including seven
  new adapter/build tests. No pre-existing Python source, tests or executed
  notebook was changed (40 protected file hashes checked).
- The real static-site Chromium suite passed **14 checks**, with no JavaScript
  errors. It served the site under a URL path prefix, as on project Pages,
  compared a nonzero tunnel survey against the native production solver and
  verified that application requests are same-origin static GETs, with no
  simulation API or WebSocket.
- Three original independent numerical tests passed inside the actual
  Pyodide worker: Fourier normalization, smooth manufactured spatial refinement,
  and harmonic interface flux/boundary handling.
- After the final mobile status/figure-dialog adjustments, two additional phone
  checks passed: startup status visible on a 390px screen with no overflow and
  a completed worker calculation; figure dialog, actual-size zoom and Close.
- Full browser evidence, numerical-test results, screenshots, native-suite logs
  and protected hashes are saved under ignored `outputs/browser_deployment/`.

These are executed local checks. GitHub Actions and the live Pages deployment
must be checked separately; they are not inferred from a passing local suite.

## November 23 control-limit correction

The initial browser source limit of 12 rejected a valid offered configuration:
12 Wenner electrodes at 6 m pitch and levels 1–2 need 15 source solves. This
prevented changed material settings from producing a new result. The source
budget is now 32, covering the largest offered configuration (28 Schlumberger
source pairs), while the 32,768-cell memory limit remains unchanged. The selected
electrodes, spacing and levels are preserved; no measurements are silently dropped.

Queued edits now show the currently finishing survey's progress. Site builds
version JavaScript/CSS/worker URLs and refresh the Python source/configuration
to avoid reusing an old browser limit after an update; the large fixed Pyodide
runtime stays cacheable. After a deployment, reload an already-open page to
load its updated worker. The regression suite exercises the reported 15-source
water-filled case and verifies that a subsequent material edit still works.
