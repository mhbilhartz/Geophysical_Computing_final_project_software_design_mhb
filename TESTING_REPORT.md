# Testing and debugging checkpoint

Executed November 3, 2026, before the analytical verification notebook.

## Outcome

**39 automated tests passed, none skipped.** The 26 existing tests passed before
changes. Thirteen additional tests cover scenarios A–F, independent face-flux
checks, visualization data, and control/error handling. A new visualization
regression failed before its fix and passed afterward. No unresolved application
test failures remain. No numerical solver or geometry changes were needed; their
hashes and the original homogeneous/variable solver test files are unchanged.

Environment: Python 3.12, NumPy 2.3.5, SciPy 1.17.0, Matplotlib 3.10.8,
Panel 1.10.0. All required dependencies were already installed in `.venv`.

Reproduce automated checks from the repository root:

```bash
source .venv/bin/activate
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/tunnel-mpl XDG_CACHE_HOME=/tmp/tunnel-cache \
  python -m unittest discover -s tests -v
```

## Numerical scenarios — all passed

Unless stated otherwise: 100×50 m domain, 160×80 cells, center (50,15) m,
radius 5 m, host resistivity 100 Ω·m, 1 V/0 V sides, insulated top/bottom.
Surface signals are peak absolute tunnel-minus-reference potential differences.
Currents below are per unit out-of-plane thickness.

| Check | Executed result |
| --- | --- |
| A: Equal host/tunnel resistivity | Zero difference from the computed reference; maximum error against the linear potential was 2.56e-14 V; Jx = 1e-4 A/m², Jz ≈ 0 |
| B: Resistive tunnel, 1e8 Ω·m | Total current 0.00482530 A/m versus reference 0.005; mean interior current-density magnitude 2.16e-10 A/m²; nonzero vertical current confirms deflection |
| C: Conductive tunnel, 5 Ω·m | Total current 0.00514558 A/m; mean interior current density 1.89e-4 A/m² versus reference 1e-4 |
| D: Depth 10 → 20 → 30 m | Air surface signal 27.327 → 10.896 → 5.779 mV; water 20.962 → 9.281 → 4.930 mV |
| E: Radius 3 → 7 m, depth 15 m | Air surface signal 6.120 → 30.670 mV; water 4.964 → 24.961 mV; total-current changes have the expected opposite signs |
| Position/host controls | Mirroring x = 35 and 65 m satisfies V_mirror = 1 − V; increasing host resistivity to 200 Ω·m decreases total current |

Twenty-one numerical configurations were examined. Across them:

- Maximum matrix residual: **2.78e-16 A/m**.
- Maximum relative entering/leaving current imbalance: **1.15e-12**.
- Maximum cell imbalance / maximum face current: **2.14e-12**.
- All conductivities were finite and strictly positive; potentials were bounded
  by the side voltages, and top/bottom face currents were exactly zero.
- Reconstructing side-face voltages from adjacent cell values and half-cell
  resistance recovered 1 V and 0 V. Cell-center columns are not boundary faces.
- Independent half-cell series-resistance calculations matched horizontal and
  vertical face current densities. The existing aligned-layer analytical test
  also passed, checking harmonic interface averaging against exact series resistance.
- Tunnel and reference coordinates and boundary voltages matched exactly.

## F: Grid differences and artifacts

| Grid | Rasterized tunnel area (m²) | Air surface signal (mV) | Water surface signal (mV) |
| --- | ---: | ---: | ---: |
| 80×40 | 81.250 | 16.999 | 13.385 |
| 160×80 | 81.250 | 16.190 | 13.478 |
| 240×120 | 77.778 | 15.308 | 12.907 |

The circle's geometric area is 78.540 m². Medium-to-fine peak surface signals
change by **−5.45% (air)** and **−4.23% (water)**, while total currents change by
+0.204% and −0.117%. The water signal changes nonmonotonically across these grids.
The interface-flux checks pass; inspection of the rasterized geometry shows that
refinement changes the stair-stepped boundary and sometimes its area. Equal
rasterized areas do not imply identical interface shapes or resistances. These
are grid-sensitivity results, not evidence of a convergence order or exact error.

## Application and visualizations — passed

The existing `panel serve app.py` application was launched locally. HTTP returned
200. Headless system Chromium rendered the initial plots and exercised:

- Air/water/custom presets and editable tunnel resistivity.
- Host resistivity, depth, radius, horizontal position, and all three grid choices.
- Run, Reset, pending-result messages, and Latest/Previous result snapshots.
- Invalid browser input: entering zero resistivity restored the previous valid
  value (20 Ω·m in that test), so zero did not reach the solver. Separate callback
  tests directly supplied zero, negative, NaN, and missing numeric values: runs
  were rejected, earlier results retained, and buttons remained usable.

The successful browser run reported no JavaScript errors. Programmatic checks
confirmed four fields and four labeled color bars, SI units, x increasing right,
depth increasing down, circle center/radius placement, and plotted arrays matching
the solver outputs. Arrow components matched averaged face currents; `angles='xy'`
respects the depth-axis inversion. Surface/depth/grid plots were also inspected.

## Bug found and fixed

The homogeneous model's current-density colors showed artificial spatial texture
and repeated 1e-4 tick labels. Autoscaling stretched roughly 3e-13 relative
floating-point variation over the full colormap. This was a display bug, not
incorrect current physics. `plotting._log_norm` now pads nearly constant positive
fields when their relative span is at most 1e-10. Raw fields and all calculations
are unchanged. The new regression checks that homogeneous current colors remain
effectively uniform. Its initial failure and subsequent pass were executed.

## Remaining limitations and readiness

The application is **ready to proceed to analytical verification**, with no
notebook work started here. This checkpoint does not establish full physical
accuracy. Stair-stepped circles remain sensitive to resolution; small residuals
and conservation alone do not prove geometric accuracy. Sub-cell boundary
clearances can also be lost in the rasterized geometry near domain edges.
Large contrasts remain conditioning risks. Domain-size sensitivity and formal
convergence order are unverified. The model assumes isotropic 2D DC conduction,
idealized side electrodes, and an infinitely long tunnel; air uses finite high
resistivity. Surface values use the zero-gradient first-row reconstruction.

Browser testing covered installed Chromium, not every browser or mobile layout.
Runs remain synchronous, and results are not persisted across sessions. The
temporary test server was stopped after validation.

Generated evidence is under `outputs/testing/` (ignored by Git): `unittest.txt`,
`scenarios.json`, `browser.json`, browser screenshots, homogeneous plots before
and after the fix, and `depth_grid_sensitivity.png`. The automated tests are
retained in the repository; screenshots are supporting evidence, not assertions
that unexecuted browsers or configurations work.
