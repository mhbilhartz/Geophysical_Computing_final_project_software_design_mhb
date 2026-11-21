# Survey upgrade, Step 5: generated surface surveys

**Step 7 update:** the [live Panel interface](LIVE_APP.md) now calls this backend.
The milestone report below records its original implementation and checks.

**Current status:** [Step 6 grid/domain planning](GRIDS.md) now prepares
automatic or manual meshes for this survey backend. This page records Step 5's
survey rules and checks; the existing Panel app still uses the original solver.

[survey.py](../tunnel_resistivity/survey.py) generates Wenner, Schlumberger, and
dipole–dipole measurements on a fixed physical electrode line and forwards them
through the **existing** 2.5D solver and receiver calculations. It contains no
second PDE solver. Each datum retains its actual A/B/M/N coordinates, current,
signed voltage, geometric factor and apparent resistivity.

The Panel app, numerical solvers, receiver module, existing tests, and both
executed verification notebooks are unchanged. This stage is a programmatic
survey backend; grid-sizing controls and interactive updates are subsequent work.

## Electrode line and spacing levels

The generator uses N uniformly spaced surface electrodes at
`line_start_x_m + i * electrode_spacing_m`, where i=0,…,N−1. The pitch p can be
any finite positive distance; electrodes are not snapped to numerical grid cells.
The project limits N to 4–1001. Large plans can still be expensive to solve.

For each requested integer level q, generate every valid translation by one
physical electrode pitch. Larger levels use wider spreads and therefore have
fewer valid translations. Requested level order is preserved, followed by
increasing leftmost electrode index; duplicate or oversized levels raise errors.
A level that does not fit is **not silently omitted**.

| Array | Meaning of level q | Full spread | Measurements at that level |
| --- | --- | --- | --- |
| Wenner alpha | Adjacent spacing a=q·p | 3q·p | N−3q |
| Schlumberger | A–M=N–B=q·p; MN=r·p | (2q+r)·p | N−(2q+r) |
| Dipole–dipole | n=q; AB=MN=d·p | (q+2)d·p | N−(q+2)d |

Here `r=receiver_spacing_steps` (default 1) and `d=dipole_spacing_steps`
(default 1). Schlumberger AB/2=(q+r/2)p and MN/2=rp/2. This permits independent
receiver spacing; source gaps expand with level. The smallest Schlumberger case
q=r=1 has the same coordinates as Wenner at a=p, which is legitimate. The
geometry module imposes 0<MN/2<AB/2 without an arbitrary large AB/MN ratio.
Nondefault r applies only to Schlumberger, and nondefault d only to dipole–dipole;
inapplicable settings are rejected rather than ignored.

Dipole–dipole n=1 means B-to-M gap **one dipole length**, not zero gap. A/B/M/N
indices are stored in **label order**, which is different from spatial order for
Wenner and Schlumberger. Indices are zero-based; exported measurement and source
pair IDs are one-based. `spread_center_x_m` is the **full spread midpoint**, not
necessarily the source midpoint and not the tunnel position or an inferred depth.

## Python/Jupyter example

Run in the repository root using the existing project environment:

```python
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.survey import generate_survey, forward_survey, export_survey_csv

plan = generate_survey(
    'dipole-dipole',
    electrode_count=9, electrode_spacing_m=5,
    line_start_x_m=30, levels=(1, 2),
    dipole_spacing_steps=1, current_a=0.1,
)
print(len(plan.measurements))           # 11
print(plan.unique_source_pair_count)    # 6
plan.validate_domain(0, 100, boundary_padding_m=20)

sigma, mask = circular_tunnel(
    width=100, height=50, nx=80, nz=40,
    center_x=50, depth=15, radius=5,
    host_resistivity=100, tunnel_resistivity=1e8,
)
result = forward_survey(sigma, plan, width=100, height=50,
                        boundary_padding_m=20)
print(result.solve_count)              # 6
print(result.measurements[0].apparent_resistivity_ohm_m)
print(result.max_relative_mode_residual)
rows = result.records()               # ordered dictionaries; standard-library scalars
export_survey_csv(result, 'outputs/my_dipole_survey.csv')
```

Replace the array name with `'wenner'` or `'schlumberger'`. Use
`receiver_spacing_steps` for Schlumberger and `dipole_spacing_steps` for
dipole–dipole. `levels=(1,2)` selects those two levels, not all possible levels.
For a full feasible Wenner level set, use
`levels=range(1, (electrode_count-1)//3 + 1)`.

`Survey` and `SurveyMeasurement` also allow an explicit plan on a shared,
strictly increasing physical electrode line. Each index must match its geometry's
coordinate exactly. This supports several Schlumberger MN separations for one
A/B pair, or a mixed plan, while preserving the existing array conventions.
The generator itself uses a uniform line. It does not generate reciprocal,
roll-along, arbitrary electrode-order, or topographic configurations.

## Source reuse, validation, and diagnostics

`forward_survey` snapshots the conductivity array, validates the entire physical
line against the domain and requested padding, and checks geometric factors
before any PDE solve. Invalid or unresolvable geometry raises `ValueError`.
The existing production solver still validates conductivity, its uniform top
row, grid and Fourier parameters. A failure returns no incomplete survey object.

Within one call, measurements are grouped by **exact A, B, and current**. One
production `solve_source_pair` call supplies all receivers in a group through
`measure_receivers(..., electrodes=...)`. Grouped data are returned in the
original plan order. Only scalar data and per-source diagnostics are retained;
the large field arrays are discarded after each group. No persistent source
cache exists. Changing conductivity, geometry, background, grid or integration
settings in a later run cannot reuse a stale field from an earlier run.

Wenner and the fixed-MN Schlumberger generator normally require one solve per
measurement. Dipole–dipole can reuse A/B across different n values. Explicit
Schlumberger plans can reuse A/B across receiver spacings. Current is part of the
reuse key; a changed I receives its own solve.

The homogeneous reference is the analytical primary with the same source pair,
current, background and boundary convention; no extra homogeneous PDE solve is
needed. Voltage polarity remains V_M−V_N. Dipole–dipole has negative K and
negative homogeneous voltage, giving positive homogeneous apparent resistivity.
Signed modeled values are preserved without absolute-value corrections.

CSV rows include geometry/indices, level, source ID, current, individual receiver
potentials, primary/secondary/total voltage, signed K, transfer resistance,
apparent resistivity and anomaly, source residual/balance, grid/Fourier settings,
and a conductivity SHA-256. CSV alone is a data export, not a substitute for the
conductivity model. The demo also saves the conductivity arrays and model settings.
All units are in column names: V, A, meters, Ω, and Ω·m as appropriate.

Mode diagnostics concern the **secondary Fourier systems**, including the k²
term. They are not a new direct measurement of total A/B injection. A small
residual does not certify domain independence, circular geometry accuracy or
field validation. Padding validation checks placement, not physical adequacy.

## Reproduce the examples

```bash
python -m unittest discover -s tests -p test_survey.py -v
python -m unittest discover -s tests -v
python -m tunnel_resistivity.survey_demo
```

Windows PowerShell uses `.\.venv\Scripts\python.exe` in place of `python`, or
the interpreter in your actual environment directory. `--output-dir PATH`
changes the demonstration output location.

The demo uses nine electrodes at x=30…70 m, 5 m pitch, levels 1/2 and I=0.1 A.
The model is 100×50 m with 80×40 cells, a circular tunnel at (50,15) m of radius
5 m, and host resistivity 100 Ω·m. Compare matched 100 Ω·m, air 1e8 Ω·m, and water
5 Ω·m. All use 64 modes and fixed cutoffs [1e-8,16] m⁻¹.

| Array | Data per material | Source solves per material | Air ρa range (Ω·m) | Water ρa range (Ω·m) |
| --- | ---: | ---: | ---: | ---: |
| Wenner | 9 | 9 | 100.95627–105.61027 | 94.58250–98.77890 |
| Schlumberger | 10 | 10 | 100.95627–105.03354 | 94.91462–98.77890 |
| Dipole–dipole | 11 | 6 | 99.40036–105.31611 | 93.93339–100.86117 |

Across all materials the demo computed **90 measurements using 75 source solves**
in about **25.3 seconds** on this cloud machine. All homogeneous data recover
100 Ω·m. Maximum relative mode residual was 9.66e-15; maximum relative mode
balance error was 1.34e-14. Timing varies by machine, grid, quadrature and plan.

Outputs under ignored `outputs/surveys_2p5d/` are nine measurement CSVs,
`summary.json` (model/line/quadrature settings and source diagnostics), three
`conductivity_*.npy` arrays in S/m, and `survey_profiles.png/.pdf`. The plot shows
apparent resistivity versus spread midpoint, with different spacing levels.
It is **not an inverted section or a depth image**.

### Investigated dipole–dipole anomaly signs

Some off-center dipole measurements have air ρa below the host and water ρa above
it. Apparent-resistivity sensitivity is signed and depends on geometry; a
resistive target need not increase every datum. These cases were checked with
independent single-source calls, a finer circle mesh, and a larger domain at
fixed cell spacing, rather than attributed to physics without checking.

| Case | A/B/M/N x (m) | 80×40, 100×50 m | 160×80, 100×50 m | 160×80, 200×100 m |
| --- | --- | ---: | ---: | ---: |
| Air | 30/35/40/45 | 99.40036 | 99.42896 | 99.40651 |
| Water | 55/60/65/70 | 100.86117 | 100.83783 | 100.86320 |

Values are Ω·m. The enlarged domain has x origin −50 m and the tunnel remains
at physical x=50 m; I and cutoffs remain fixed. Both signs persist, while the
values still exhibit mesh/domain dependence. Reproduce those direct checks:

```python
from tunnel_resistivity.electrodes import ElectrodeArray
from tunnel_resistivity.solver_2p5d import solve_source_pair
from tunnel_resistivity.receivers import measure_receivers

for rho, xs in ((1e8, (30,35,40,45)), (5, (55,60,65,70))):
    electrodes = ElectrodeArray('dipole-dipole', *xs, current_a=0.1)
    for w,h,nx,nz,origin in ((100,50,80,40,0), (100,50,160,80,0),
                           (200,100,160,80,-50)):
        sigma, _ = circular_tunnel(
            width=w, height=h, nx=nx, nz=nz,
            center_x=50-origin, depth=15, radius=5,
            host_resistivity=100, tunnel_resistivity=rho,
        )
        model = solve_source_pair(sigma, electrodes, width=w, height=h,
                                  x_origin_m=origin, n_wavenumbers=64,
                                  k_min=1e-8, k_max=16)
        print(rho, w, nx, measure_receivers(model).apparent_resistivity_ohm_m)
```

## Executed tests and remaining stages

The 92 existing tests passed before changes. Twenty new tests cover survey
counts, coordinates, level/spacing conventions, physical line membership,
input errors, immutability, all-array homogeneous recovery, actual air/water
responses, agreement with separate production solves, source reuse, output
ordering, changed-current keys, fresh runs after conductivity changes, domain
translation, factor/domain preflight, diagnostics and CSV data/provenance.
The full suite **passed all 112 tests in 49.547 seconds**.

All underlying 2.5D scientific limits from the [verification notebook](../verification_2p5d.ipynb)
remain. Complete surveys require many source solves and will not necessarily
finish instantly during slider motion. The live controls use debouncing and
suitable grid/plan sizes; the source-count estimate is available before a solve.
The subsequent [grid planning](GRIDS.md), [live interface](LIVE_APP.md) and
[survey visualization](VISUALIZATIONS.md) stages are now complete. No inversion, repository push or publication is included here.
