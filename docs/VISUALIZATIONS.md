# Survey upgrade, Step 8: field and survey visualizations

The live survey app now includes selected-measurement fields, a surface-potential
anomaly curve, and a map of measured configurations. It uses the existing 2.5D
source-pair solver, grid and receiver methods. Neither numerical solver nor either
executed verification notebook was changed for this stage.

## Open and use the explorer

From the project root, with requirements installed:

```bash
python -m panel serve app.py --show
```

For an already running app, stop its own server with Ctrl+C and relaunch to load
new code. Other terminals, inversions and kernels can continue. In JupyterLab,
follow [the live-app notebook instructions](LIVE_APP.md#use-inside-an-existing-jupyterlab)
using `SurveySimulatorApp`; close your old simulation instance before replacing it.

1. Wait for the initial survey and selected fields to finish. Survey completion
   and field completion have separate status messages.
2. Scroll below the measurement table to **Explore fields and survey
   configurations**. The default selection is the largest requested spacing
   level, with spread midpoint nearest the tunnel. This is a display default,
   not a sensitivity optimization.
3. Select a measurement. The label gives its ID, spacing level and A/B/M/N world
   coordinates. A injects +I and B withdraws I; M/N are passive receivers.
4. Use the three explorer tabs described below. **Download selected field PNG**
   exports the four-panel figure, including source/receiver and tunnel settings.
5. Switch the upper **Latest completed survey / Previous survey** tabs to
   compare completed snapshots. The explorer, highlighted datum, receiver labels
   and PNG filename follow that snapshot. The survey CSV still follows the same
   upper tab and includes all measurements, not just the selected one.

Selecting another measurement does not recompute the entire survey. An uncached
A/B/current pair requires one additional production source solve, using that
completed model's exact conductivity, grid, background and saved Fourier
settings. A two-entry, per-session cache reuses fields for shared source pairs.
Changing only M/N still updates receiver values and labels. The cache is bounded,
keeps snapshot identity, and retains no sparse matrix factorizations.

Field changes are debounced by 200 ms and computed outside the UI callback.
Editing model/survey controls invalidates pending fields, hides the explorer's
old images and disables PNG download until completion. A source solve already
inside SciPy finishes before cooperative cancellation takes effect. Generation,
snapshot and measurement checks prevent old results from repainting a new
selection. `simulation.close()` closes both of that instance's workers.

## Potential and current fields

Four panels use the selected source pair and the same grid at cross-line y=0:

| Panel | Quantity and scale | Interpretation |
| --- | --- | --- |
| Resistivity | 1/σ, Ω·m; logarithmic | Host and cell-center circular tunnel mask; dashed circle is the intended geometry |
| Electrical potential | V, volts; symmetric-log | Signed potential from the point sources, with a linear interval around zero and logarithmic tails |
| Current | √(Jx²+Jz²), A/m²; logarithmic | Colors encode magnitude; equal-length cyan arrows encode direction only |
| Tunnel − homogeneous potential | Vsecondary, volts; zero-centered linear | Difference from the exact homogeneous primary for these sources and host |

Axes show world horizontal distance and depth in meters, with depth increasing
downward. A/B triangles and M/N circles mark electrodes on the surface. Positive
Jx is rightward and positive Jz downward. Arrows use those physical components on
the inverted depth axis. They should leave A and enter B; tunnel deflections
vary with the chosen source pair.

The plotted current is the existing solver's approximate cell-center current.
Near a conductivity interface, a single cell-center vector cannot show both
one-sided limits. Interface conservation is enforced in the solver using
harmonic face conductivity, not by these arrows. For 2.5D, a two-dimensional
`div(Jx,Jz)` calculation alone is not a complete current balance: cross-line
variation/Fourier terms must be included. Use the existing mode-balance diagnostics.

Each figure chooses its own color limits; compare color bars and numbers when
comparing materials or snapshots. Potential's symmetric-log colors are not a
linear voltage ramp. Homogeneous/constant scales have a finite display interval
so roundoff is not amplified into an apparent anomaly. Current color values
below the display floor are clipped to that floor, with an extension marker.
Exact point sources are singular; maps display finite cell-center samples.

The reference is the analytical primary already used by the 2.5D solver, not the
old fixed-1-V/0-V model. The field difference is read directly from the stored
secondary potential, avoiding cancellation from subtracting large primary
potentials. The secondary uses zero outer-face values; the primary supplies the
outer total potential. Thus tunnel and reference share source and boundary
conventions. This view does not change the finite-domain approximation.

## Surface potential difference

This curve shows δV(x, z=0) = Vtunnel − Vhomogeneous for the selected source pair.
M/N markers use exactly the existing receiver surface-reconstruction method.
The title reports δVM − δVN, the tunnel contribution to the receiver voltage.
It is distinct from the total receiver voltage VM − VN in the survey table.
A/B guides identify sources; exact source samples are omitted. This is a
same-source voltage anomaly, not a new electrode survey or an inverted section.

## Survey configuration map

Two panels plot the actual completed measurements as colored squares:

- Apparent resistivity ρa = K(VM − VN)/I, in Ω·m.
- Relative anomaly 100(ρa/ρhost − 1), in percent, centered on zero.

The horizontal coordinate is the midpoint of the full A/B/M/N spread. The
vertical coordinate is **array spacing level, not depth**. Definitions remain
those in [SURVEYS.md](SURVEYS.md): Wenner a/p, Schlumberger A–M gap/p, and
dipole–dipole n. No interpolation, pseudo-depth assignment or inversion is used.
A black square outlines the selected measurement. The logarithmic ρa scale is
used only for positive data; signed symmetric-log colors preserve nonpositive
apparent resistivities if a configuration produces them. Negative signed K and
voltage for dipole–dipole are preserved in the underlying data.

## Reproduce examples without Panel

```bash
python -m tunnel_resistivity.visualization_demo
```

Use `--output-dir path` to choose another directory. By default, the ignored
`outputs/visualizations_2p5d/` directory receives:

- Homogeneous, air and water four-field, surface and survey-map PNG/PDF figures.
- Compressed selected-field arrays (`*_selected_fields.npz`): coordinates,
  conductivity, total/primary/secondary potential and Jx/Jz, with units in keys.
- `summary.json` with geometry, grid, current, selected measurement, voltage,
  apparent resistivity, residuals, Fourier settings and conductivity hash.

The executed default examples use host 100 Ω·m, tunnel center (50, 15) m,
radius 5 m, Wenner electrodes at 5 m pitch and levels 1–2. Selected measurement
8 has A=35, B=65, M=45, N=55 m and I=0.1 A on a 128×64 grid, x=−30…130 m,
bottom=80 m. These are computed examples, not measured mine data:

| Model | Tunnel resistivity (Ω·m) | Selected ρa (Ω·m) | δVM − δVN (V) |
| --- | ---: | ---: | ---: |
| Homogeneous | 100 | 100.000000000 | 0 |
| Air | 1e8 | 105.761873456 | +0.00917030642 |
| Water | 5 | 95.175462281 | −0.00767849026 |

Across these examples, maximum relative Fourier-mode residual was below
5.4e−15 and mode balance error below 4.1e−15. Small residuals show the discrete
systems were solved; they do not certify continuum accuracy or detectability.

## Checks executed for this stage

The restored 150 tests passed before implementation. The expanded full suite
passed **167 tests in 64.854 s**. After the color-bar label adjustment, the
17 visualization tests passed again in 9.002 s. Seventeen added tests cover physical plot data,
units/depth orientation, current arrows, saved solver settings, matching receiver
voltages, surface reconstruction, homogeneous recovery, signed survey maps,
source reuse with changed M/N, bounded cache ownership, cancellation, stale
snapshot/measurement rejection, selected-tab PNG and session cleanup.

```bash
python -m unittest discover -s tests -p test_visualizations.py -v
python -m unittest discover -s tests -v
```

An isolated Jupyter kernel executed three smoke-test cells: display, automatic
air/water/homogeneous field updates, zero homogeneous secondary potential,
enabled PNG download, and closure of both session workers. The test notebook
is a disposable artifact under `outputs/`, separate from both verification
notebooks.

The live Panel server passed **14 native Chromium checks**, with no JavaScript
page errors: initial nine-measurement/default-field rendering, measurement
selection, surface and map tabs, valid PNG bytes/filename, water/custom updates,
Previous/Latest field and export ownership, shared-source dipole receiver labels,
invalid-domain hiding/disabled exports, and Reset to default fields. Browser
screenshots and `browser_report.json` are saved with the generated examples.
The browser harness needed parent-paragraph text extraction for Panel's bold
metadata and a wait for server-updated slider limits; these were test-harness
corrections. Visual inspection also found crowded logarithmic map color-bar
ticks; disabling minor ticks fixed the display without changing data.

## Scientific and runtime limits

The material is invariant along the tunnel axis; a finite 3D tunnel, topography,
contact resistance, noise, electrode footprints and inversion are absent.
Circle stair-stepping, grid spacing, domain walls and Fourier integration still
require the checks in [VERIFICATION_2P5D.md](VERIFICATION_2P5D.md) and
[GRIDS.md](GRIDS.md). The coarse plots are exploratory; source proximity and
large contrasts require care. Selecting sources costs computation, so slider
updates and field selection are responsive but not guaranteed instantaneous.
Independent sessions each have their own small field cache and workers.
