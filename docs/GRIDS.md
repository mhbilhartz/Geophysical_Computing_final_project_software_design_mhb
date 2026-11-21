# Survey upgrade, Step 6: grid dimensions and domain sizing

**Step 7 update:** the [live Panel interface](LIVE_APP.md) now calls this backend.
The milestone report below records its original implementation and checks.

[grid.py](../tunnel_resistivity/grid.py) plans a rectangular domain and prepares
its conductivity model for the **existing** survey solver. It supports automatic
bounds/resolution and explicit manual bounds/cell counts. It adds no second PDE
solver. The later [live interface](LIVE_APP.md) now exposes these settings. Both existing verification
notebooks, numerical solvers, receiver/survey modules and their tests are retained.

## Physical coordinates and manual dimensions

`TunnelGeometry(center_x_m, depth_m, radius_m)` uses physical x and depth in
meters; depth is to the center and increases downward. Radius must be positive,
and center depth must exceed radius so the tunnel is fully buried.

`GridSpec(x_min_m, x_max_m, height_m, nx, nz)` defines side **faces** and the bottom
at depth `height_m`. The top remains z=0. Width is x_max−x_min, dx=width/nx and
dz=height/nz. Cell centers lie half a cell inside each face. Negative x_min is
valid: it adds model space left of the electrodes and does not move the survey.

The original circle helper expects a center measured from its left face.
`prepare_survey_model` converts physical tunnel x to `center_x_m − x_min_m`
when calling it. Electrodes remain in world coordinates. Pass
`grid.solver_kwargs()` to `forward_survey` so width, height **and x origin** match
that conductivity array. Omitting the origin on a shifted grid would model a
different physical arrangement.

## Automatic planning rules

Let S be the largest full measurement spread, p the smallest physical electrode
separation, r tunnel radius, and g=center depth−r the roof clearance. Defaults:

```text
padding P = max(10 m, 2*S)
left  = min(first physical electrode, tunnel left edge) − P
right = max(last physical electrode, tunnel right edge) + P
bottom depth = max(tunnel bottom, S/2) + P

maximum dx = min(requested max_cell_size_m, r/4, p/4)
maximum dz = min(requested max_cell_size_m, r/4, g/2)
nx = ceil(width / maximum dx), nz = ceil(height / maximum dz)
```

The whole physical electrode line is included, even when some electrodes do not
participate at a requested level. The bounds grow with spacing, measurement
spread, line length, tunnel depth/radius or an off-center tunnel. Finer cell
counts preserve the physical size limit as a domain grows. The two g/2-limited
surface rows stay above the physical roof; shallow roofs can refine **z only**,
so the horizontal mesh is not unnecessarily refined too.

`max_cell_size_m` defaults to 1.25 m and is an **upper bound**, not a promise of
exact spacing. Radius/spacing/roof requirements may force finer cells. Counts
round upward. `padding_factor` and `min_padding_m` change P; positive
`side_padding_m` and `bottom_padding_m` independently override it.
`cells_per_radius` defaults to 4 and must be at least 4 for automatic grids.
`cells_per_electrode_spacing` defaults to 4 and must be at least 2.

These are **heuristics**, not an adaptive error estimator or exact open boundary
condition. In particular S/2 does not label a datum's investigation depth.
Changing array name alone has no numerical effect; its actual electrode spread
and configuration determine these rules. Domain and resolution sensitivity
remain necessary.

## Plan, prepare, and run from Python or Jupyter

Run from the repository root in the existing project environment:

```python
from tunnel_resistivity.survey import generate_survey, forward_survey
from tunnel_resistivity.grid import TunnelGeometry, suggest_grid, prepare_survey_model

survey = generate_survey('wenner', electrode_count=9,
                         electrode_spacing_m=5, line_start_x_m=30,
                         levels=(1, 2), current_a=0.1)
tunnel = TunnelGeometry(center_x_m=50, depth_m=15, radius_m=5)
grid = suggest_grid(survey, tunnel, max_cell_size_m=1.25)
print(grid)  # x=-30…130 m, bottom=80 m, nx=128, nz=64
print(grid.cell_count, survey.unique_source_pair_count)

model = prepare_survey_model(survey, tunnel, grid,
                             host_resistivity=100, tunnel_resistivity=1e8)
print(model.diagnostics)
print(model.warnings)
result = forward_survey(model.conductivity, survey, **grid.solver_kwargs())
print([datum.apparent_resistivity_ohm_m for datum in result.measurements])
```

To keep a fixed domain for comparisons, construct a manual grid and use the same
preparation and solver calls:

```python
from tunnel_resistivity.grid import GridSpec

manual = GridSpec(x_min_m=-30, x_max_m=130, height_m=80, nx=256, nz=128)
model = prepare_survey_model(survey, tunnel, manual,
                             host_resistivity=100, tunnel_resistivity=5)
result = forward_survey(model.conductivity, survey, **manual.solver_kwargs())
```

Manual dimensions are respected; they are not silently resized. All electrodes
and the whole circle must lie strictly inside the side/bottom faces. The first
cell-center row must be strictly above the roof to guarantee the homogeneous
surface row required by the source solver. A manual grid whose second row
contains contrasting tunnel material is supported, but its affected receivers
use Step 3's first-row reconstruction and receive a diagnostic note.

## Cell budget and diagnostics

The default budget is **100,000 cells**. Planning and preparation check it before
allocating the conductivity mesh. An oversized grid raises an actionable error;
it is **not silently coarsened** or cropped. Change line/domain demands or
resolution, or explicitly increase `max_cells` in **both** `suggest_grid` and
`prepare_survey_model`. The resolution floors still apply in automatic planning.
This is an allocation/work limit, not a guarantee on memory, runtime or accuracy;
sparse factorization costs also depend on shape and conductivity contrast.

Preparation reports actual dimensions, dx/dz, total cells, cells per radius in
both directions, horizontal cells per minimum electrode spacing, aspect ratio,
surface/side/bottom clearances, geometric host rows above the tunnel, sampled
circle area versus πr², and measurement/source-pair counts. Manual underresolved
circles, fewer than four horizontal cells per electrode spacing, aspect ratio
above four, and second-row receiver fallback produce inspectable notes.

Four cells per radius is a minimum planning rule, not convergence proof. The
sampled circle is stair-stepped and its area/shape can change discontinuously
with resolution or tunnel position. A small algebraic residual cannot detect
these geometric errors. Resistivity must remain positive and finite; existing
reciprocal-conductivity checks reject zero/negative/nonfinite values.

## Reproducible examples and executed checks

```bash
python -m unittest discover -s tests -p test_grid.py -v
python -m unittest discover -s tests -v
python -m tunnel_resistivity.grid_demo
```

Windows PowerShell uses `.\.venv\Scripts\python.exe` in place of `python`,
or the interpreter in your actual project environment. `--output-dir PATH`
selects another output directory. No new dependency is needed.

For the nine-electrode line x=30…70 m with p=5 m, levels 1/2, and tunnel center
(50,15) m/radius 5 m, automatic planning gives:

| Array | x faces (m) | Bottom (m) | nx×nz | dx=dz (m) | Cells |
| --- | --- | ---: | --- | ---: | ---: |
| Wenner | −30…130 | 80 | 128×64 | 1.25 | 8192 |
| Schlumberger | −20…120 | 70 | 112×56 | 1.25 | 6272 |
| Dipole–dipole | −10…110 | 60 | 96×48 | 1.25 | 4608 |

The demo plots these footprints at identical physical scales, keeping the tunnel
and electrode line at the same positions. Gray areas are outside a model. It
also solves **one** central level-2 Wenner datum (A/B/M/N=35/65/45/55 m, I=0.1 A)
for air/water, changing resolution and padding separately:

| Case | Domain (m) | nx×nz | dx=dz (m) | Air ρa (Ω·m) | Water ρa (Ω·m) |
| --- | --- | --- | ---: | ---: | ---: |
| Base, P=2S | 160×80 | 128×64 | 1.25 | 105.761873 | 95.175463 |
| Finer cells, P=2S | 160×80 | 256×128 | 0.625 | 105.503458 | 95.088554 |
| Larger domain, P=3S | 220×110 | 176×88 | 1.25 | 105.795067 | 95.157716 |

Host=100 Ω·m; air=1e8 Ω·m; water=5 Ω·m. Both materials use the same circle,
electrodes, current and fixed Fourier settings: 64 modes, k∈[1e-8,16] m⁻¹.
The first change isolates mesh sensitivity at fixed bounds; the second isolates
domain sensitivity at fixed cell size. Values differ despite maximum relative
mode residual/balance below 1.73e-14/1.53e-14. There is no analytical tunnel
solution here, so these changes are **not error bounds or proof of convergence**.

Saved artifacts under ignored `outputs/grids_2p5d/` are `automatic_domains.png/.pdf`,
`grid_domain_sensitivity.png/.pdf`, `sensitivity.csv` and `summary.json` with
geometry, line/settings, diagnostics and results. They are regenerated by the
command above. The example performs six single-source solves, not six complete
surveys. Full-survey runtime also scales with the number of distinct source pairs.

The restored **112 tests passed before changes**. Nineteen new tests cover
array/spread-dependent sizing, the full physical line, deep/off-center tunnels,
padding overrides, resolution floors, shallow-roof refinement, preallocation
budget checks, invalid inputs, manual geometry, physical-coordinate mapping,
translation, diagnostics, homogeneous recovery for all arrays and actual
conserved air/water data matching direct production calls.
The final full run **passed all 131 tests in 75.840 seconds**. File-hash checks
also confirmed that all 29 pre-existing source/test/notebook files were unchanged
from the start of this step.

The subsequent [live-interface stage](LIVE_APP.md) connected survey/grid/tunnel settings to the interactive interface
and automatic updates. A full survey may take many seconds; live controls need
appropriate debounce/preview behavior. This grid stage does not add Panel
controls, inversion, repository pushes or environment publication.
