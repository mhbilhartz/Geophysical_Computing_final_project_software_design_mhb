# Historical final review: original fixed-voltage model

This is the November 3, 2026 review, retained as a historical record. It
predates the 2.5D survey upgrade. For current evidence and Git status, use
[the Step 9 final review](../FINAL_REVIEW.md).

Reviewed November 3, 2026, against the original GPGN 436/536 Fall 2026 PDF.

**Technical result: PASS on Linux/Python 3.12. Ready for student review, not yet
submitted.** Nothing was committed, pushed, deployed or published by this review.
The instructor's distinctness/access checks, Canvas submission, attendance and
independent presentation remain student/instructor actions. See the complete
[assignment checklist](../SUBMISSION_CHECKLIST.md) for PASS/PENDING statuses rather
than treating those obligations as automatically satisfied by passing tests.

## Fresh-install evidence

A separate copy of the tracked project was made under `/tmp`, excluding the old
`.venv`, caches and ignored outputs. A new Python **3.12.14** virtual environment
was created without `--system-site-packages`. Its configuration has
`include-system-site-packages = false`, `ENABLE_USER_SITE = False`, and scientific
packages resolve inside that new environment. The original development environment
was not used to provide application dependencies.

| Executed check | Result |
| --- | --- |
| Install `requirements.txt` into empty environment | PASS; all dependencies downloaded/installed using verified package transport |
| Runtime-only automated suite, before Jupyter installation | PASS: 42 tests, none skipped |
| Install `requirements-notebook.txt` | PASS |
| `pip check` | PASS: no broken requirements |
| Full suite after notebook-tool install and final whitespace cleanup | PASS: 42 tests, none skipped |
| Reexecute analytical notebook from fresh kernel | PASS: all 10 code cells, no error outputs, 4 embedded figures |
| Compare notebook error tables/conclusions | PASS: saved Markdown outputs match the submitted notebook |
| Recreate geophysical experiments | PASS: 53 records, 45 unique tunnel solves, 7 references |
| Compare summary CSV | PASS: 53 rows, 2,116 numeric cells, maximum absolute difference 0 |
| Compare surface-profile CSV | PASS: 13,440 rows, 53,760 numeric cells, maximum absolute difference 0 |
| Compare derived-statistics CSV | PASS: 25 rows/values, maximum absolute difference 0 |
| Compare five regenerated PNGs | PASS: dimensions and pixels identical to saved figures |
| Regenerate five PDF figures | PASS; PDFs are export artifacts, not compared bytewise because metadata may vary |
| Panel startup from the clean environment | PASS: HTTP 200 and initialized application |
| Chromium interaction | PASS: initial plots/controls, water preset, Run, comparison tabs, custom matched material, Reset; no JavaScript errors |
| Static homogeneous and air/water example commands | PASS; analytical error and current outputs agree with README expectations |
| Relative documentation links and staged content | PASS; checked after final staging |

The app server ran with the clean environment's Python. Installed system Chromium
and a separate browser-driving tool were used to inspect it; browser automation
is not an application dependency. These are Linux results. **Windows PowerShell
and macOS execution were not tested**; platform-specific instructions are supplied
without claiming otherwise. A fresh Python environment is not a new operating
system or container.

Direct runtime versions are NumPy 2.3.5, SciPy 1.17.0, Matplotlib 3.10.8 and Panel
1.10.0. Notebook tools are JupyterLab 4.6.5, nbconvert 7.17.2 and ipykernel 7.4.0.
Transitive dependencies were resolved afresh, including pandas 3.1.0. Requirements
pin direct dependencies, not a complete per-platform dependency lock.

No unexpected numerical warnings or unresolved test failures occurred. The cloud
kernel needed normal local-socket execution permission; Jupyter printed a local
TCP transport notice, not a numerical failure. The headless/writable-cache
settings documented in the README handle this machine's read-only home. The
browser and test server were stopped after validation.

## Notebook and scientific claims

The original `verification.ipynb` was **not overwritten**: its complete byte hash
matches the pre-review value. Reexecution wrote the separate ignored file
`outputs/verification/verification.reexecuted.ipynb` in the clean copy. The
submission notebook retains all executed plots/tables and is tracked/staged.

| Claim checked against reproduced results | Result |
| --- | --- |
| Smooth-conductivity grid convergence | Measured RMSE orders 1.997472, 1.999365, 1.999841; finest RMSE 7.90049e-6 V |
| Depth response | 7.5→35 m: air 38.309→4.252 mV; water 26.008→3.606 mV |
| Radius response | 2→9 m: air 2.710→52.147 mV; water 2.214→40.445 mV; descriptive powers 1.967/1.936 |
| Conductive/resistive response | Opposite signed patterns; current concentrates/diverts; matched material gives zero anomaly |
| Current conservation | Across analysis, maximum relative boundary imbalance 5.41e-12; residual at most 1.11e-15 A/m |
| Grid dependence | Medium→fine peak changes −5.45%/−4.23%; water is nonmonotonic over three grids |
| Side-boundary dependence | Width 100→200 m: normalized peaks increase **17.62% air / 14.15% water** |
| Remaining side/bottom influence | Width 150→200 m still changes normalized peaks 5.39%/4.36%; height 50→100 m changes peaks −5.08%/−3.98% |

Normalization is A/E0 with E0=1 V/W, so the width comparison separates changing
forcing from boundary displacement. It is not apparent resistivity. No domain
independence, circular-interface convergence order, field validation or actual
Onyx instrument detectability is claimed. The 2D, isotropic, simplified-material,
infinitely long tunnel and idealized side-electrode assumptions remain limitations.

## Changes and organization

- Reorganized the accumulated README into final user instructions and scientific
  explanations, including PowerShell commands and working relative links.
- Corrected stale text saying domain sensitivity was unassessed; distinguished
  160×80 UI results from 240×120 analysis results and highlighted the 14–18% effect.
- Added `SUBMISSION_CHECKLIST.md`, `REFERENCES.md`, and this final review.
- Shortened the AI-use disclosure while retaining contributions/responsibility.
- Expanded `.gitignore` for environment files, logs and OS/test caches.
- Removed generated project `__pycache__` directories. Existing ignored historical
  `outputs/` evidence and the development `.venv` were retained locally, but are
  excluded from submission. Important analysis results remain tracked.
- Removed only trailing blank lines from `app.py`, `diagnostics.py`, and
  `plotting.py` inside the package; their parsed Python ASTs are identical.
- Kept all solver/geometry/method logic, tests, analysis calculations, saved
  analysis data and original notebook outputs unchanged. Distinct working
  examples were retained; no duplicate solver or new application feature was added.

The scientific tables/figures are in tracked `analysis/results/`, not just ignored
outputs. No credentials, private keys, environment directory, kernel connection
files, unrelated attachments or instructor PDF are staged. Text-pattern scanning
and manual file-type/path review found no secret material; this is an inspection,
not a universal guarantee for unknown future edits.

## Exact reproduction commands

After creating/activating a Python 3.12 environment at the repository root, as
shown for both operating systems in [README.md](../README.md):

```bash
python -m pip install -r requirements-notebook.txt
python -m unittest discover -s tests -v
python -m ipykernel install --prefix .venv --name tunnel-resistivity --display-name "Python (tunnel-resistivity)"
python -m nbconvert --to notebook --execute verification.ipynb --output verification.reexecuted --output-dir outputs/verification --ExecutePreprocessor.timeout=180 --ExecutePreprocessor.kernel_name=tunnel-resistivity
python -m analysis.run_experiments
python -m panel serve app.py --show
```

`requirements-notebook.txt` includes the runtime requirements. The UI alone needs
only `requirements.txt`. On Windows, prepend these module commands with
`.\.venv\Scripts\python.exe` instead of `python`; no activation policy change is
needed. On a headless/read-only-home cloud machine use the environment settings
in the README and omit `--show`.

## Final file list

The following files are tracked in the index and prepared for the next commit:

```text
.gitignore
AI_USE.md
FINAL_REVIEW.md
README.md
REFERENCES.md
SUBMISSION_CHECKLIST.md
TESTING_REPORT.md
analysis/README.md
analysis/__init__.py
analysis/results/01_depth.pdf
analysis/results/01_depth.png
analysis/results/02_radius.pdf
analysis/results/02_radius.png
analysis/results/03_contrast_and_profiles.pdf
analysis/results/03_contrast_and_profiles.png
analysis/results/04_representative_maps.pdf
analysis/results/04_representative_maps.png
analysis/results/05_grid_domain_sensitivity.pdf
analysis/results/05_grid_domain_sensitivity.png
analysis/results/provenance.json
analysis/results/summary.csv
analysis/results/surface_profiles.csv
analysis/results/trend_statistics.csv
analysis/run_experiments.py
app.py
requirements-notebook.txt
requirements.txt
tests/test_analysis.py
tests/test_app.py
tests/test_physics_scenarios.py
tests/test_plotting.py
tests/test_simulation.py
tests/test_solver.py
tests/test_variable_solver.py
tunnel_resistivity/__init__.py
tunnel_resistivity/app.py
tunnel_resistivity/demo.py
tunnel_resistivity/diagnostics.py
tunnel_resistivity/geometry.py
tunnel_resistivity/plotting.py
tunnel_resistivity/simulation.py
tunnel_resistivity/solver.py
tunnel_resistivity/tunnel_demo.py
verification.ipynb
```

## Git status for student review

Local branch: `work`. Local HEAD remains `40830f1` (`outline addition`). The source,
notebook and results from development are staged, not yet committed or uploaded.
`A` means staged addition and `M` staged modification. No push was attempted.

```text
A  .gitignore
A  AI_USE.md
A  FINAL_REVIEW.md
M  README.md
A  REFERENCES.md
A  SUBMISSION_CHECKLIST.md
A  TESTING_REPORT.md
A  analysis/README.md
A  analysis/__init__.py
A  analysis/results/01_depth.pdf
A  analysis/results/01_depth.png
A  analysis/results/02_radius.pdf
A  analysis/results/02_radius.png
A  analysis/results/03_contrast_and_profiles.pdf
A  analysis/results/03_contrast_and_profiles.png
A  analysis/results/04_representative_maps.pdf
A  analysis/results/04_representative_maps.png
A  analysis/results/05_grid_domain_sensitivity.pdf
A  analysis/results/05_grid_domain_sensitivity.png
A  analysis/results/provenance.json
A  analysis/results/summary.csv
A  analysis/results/surface_profiles.csv
A  analysis/results/trend_statistics.csv
A  analysis/run_experiments.py
A  app.py
A  requirements-notebook.txt
A  requirements.txt
A  tests/test_analysis.py
A  tests/test_app.py
A  tests/test_physics_scenarios.py
A  tests/test_plotting.py
A  tests/test_simulation.py
A  tests/test_solver.py
A  tests/test_variable_solver.py
A  tunnel_resistivity/__init__.py
A  tunnel_resistivity/app.py
A  tunnel_resistivity/demo.py
A  tunnel_resistivity/diagnostics.py
A  tunnel_resistivity/geometry.py
A  tunnel_resistivity/plotting.py
A  tunnel_resistivity/simulation.py
A  tunnel_resistivity/solver.py
A  tunnel_resistivity/tunnel_demo.py
A  verification.ipynb
```

The GitHub submission is **pending**, not a passed publication check: review this
list/status, commit and push the complete project when authorized, verify the
instructor can access it and see the notebook outputs, then submit the repository
link on Canvas by November 29, 2026, 11:59 p.m. Mountain Time. Presentation and
attendance obligations are listed in [SUBMISSION_CHECKLIST.md](../SUBMISSION_CHECKLIST.md).
