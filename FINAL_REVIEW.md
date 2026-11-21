# Final review: 2.5D survey application

Reviewed **November 21, 2026** (Mountain Time). **Local technical result: PASS
on Linux/Python 3.12.** The current default application is the 2.5D point-electrode
survey forward modeler in `app.py`; the original fixed-voltage application is
retained as `legacy_app.py`. This review added documentation corrections and
reproduction evidence, with no changes to Python source, tests, numerical
methods or the two saved verification notebooks.

The [assignment checklist](SUBMISSION_CHECKLIST.md) distinguishes local technical
artifacts from instructor approval, attendance, GitHub access, submission and
presentation. The [November 3 review](docs/LEGACY_FINAL_REVIEW.md) is a historical
record for the original model, not the current test count or Git status.

## GitHub publication update — November 21, 2026

The completed survey upgrade was pushed successfully to public repository
[GitHub main](https://github.com/mhbilhartz/Geophysical_Computing_final_project_software_design_mhb)
as code commit [`b7e4118f44a1c56d756e32c20082389a1728c663`](https://github.com/mhbilhartz/Geophysical_Computing_final_project_software_design_mhb/commit/b7e4118f44a1c56d756e32c20082389a1728c663),
“Complete 2.5D electrical resistivity survey simulator.” The existing local
`work` branch tracks `origin/main`. The push was a normal fast-forward; no pull
request or history rewrite was needed. Repository visibility was read from
GitHub's **Public** label and was not changed.

An independent clone of `main` matched all **82 project files byte-for-byte**,
including source, tests, analysis figures/CSVs, requirements and documentation.
The repository and source/analysis/documentation pages returned HTTP 200. The
rendered README contains the current 2.5D description, 167-test count, Windows
instructions and working links to the committed local files.

Both notebook pages returned HTTP 200. The independently downloaded notebooks
retain ten executed code cells each, four original-model figures and five
2.5D figures, with no saved error outputs. The managed cloud network blocks
`notebooks.githubusercontent.com`, so the live GitHub notebook preview could
not be inspected here. **Open both notebook previews in your own browser once**
to confirm their visual rendering; the published files contain the saved images
and numerical outputs. GitHub API access was also unavailable, so metadata
checks used the repository web page and Git transport.

The prepublication Git snapshot later in this report records the Step 9 state.
Those files have now been added and published. A documentation-only follow-up
records these checks; the application and verification artifacts remain those
of the code commit above. Current commit history is visible on GitHub.

Canvas submission, instructor-specific access confirmation and the final
presentation remain student actions in the [checklist](SUBMISSION_CHECKLIST.md).
No Canvas action or cloud-environment publication was performed by this Git step.

## Checks actually executed

A complete copy of the working tree, including currently untracked survey files,
was created under `/tmp/gpgn-final-review`. Git metadata, the development `.venv`,
caches and ignored outputs were excluded. A new Python **3.12.14** environment
was created there with `include-system-site-packages = false` and user-site
imports disabled. Scientific imports resolve inside that new environment.

| Executed check | Result |
| --- | --- |
| Restored environment dependency check | PASS: `pip check` reports no broken requirements |
| Restored full suite, before documentation changes | PASS: **167 tests in 94.802 s**, none skipped |
| Install pinned runtime requirements into empty environment | PASS |
| Full suite with runtime dependencies only | PASS: **167 tests in 105.267 s**, none skipped |
| Install optional notebook requirements; final `pip check` | PASS |
| Reexecute original notebook in fresh kernel | PASS: ten code cells, four embedded figures, no error outputs |
| Reexecute 2.5D notebook in fresh kernel | PASS: ten code cells, five embedded figures, **26 acceptance checks**, no error outputs |
| Compare both notebooks with saved outputs | PASS: all nine figures pixel-identical; original numerical Markdown identical; 170 scientific summary values in 2.5D summary match, excluding runtime/version metadata |
| Reproduce original geophysical experiments | PASS: 53 records, 45 distinct tunnel solves, seven homogeneous references |
| Compare original analysis CSVs | PASS: all 53 summary rows, 13,440 surface rows and 25 statistics rows match; maximum numeric difference **0** |
| Compare original analysis figures | PASS: all five PNGs pixel-identical; five PDFs regenerated |
| Run all seven README static-example commands | PASS; visualization numerical summary exactly matches its saved summary |
| Current and legacy Panel startup from clean environment | PASS: HTTP 200 and initialized applications |
| Native Chromium interactions against clean server | PASS: **14 checks**, no JavaScript page errors |
| Live notebook interface in isolated clean kernel | PASS: three smoke-test cells, automatic air/water/custom fields, zero homogeneous anomaly, PNG state and both workers closed |
| Local documentation/notebook links and file-path review | PASS; current source/notebook content is present; environment/caches/credentials excluded from candidate files |
| Protected-file hashes and whitespace | PASS: Python source/tests, both notebooks and tracked scientific results unchanged; `git diff --check` clean |

Notebook reruns wrote separate copies; the submitted notebooks were not saved
over. The 2.5D comparison excludes elapsed times and dependency-version metadata,
which legitimately differ on rerun. Its scientific summary and figures agree
with the saved evidence. The automated tests are the existing 167 tests; no
implementation-mirroring tests or extra application features were added.

The browser checks covered default automatic fields; finite nine-measurement
CSV; PNG bytes/filename; water/custom updates; Previous/Latest ownership; surface
and survey-map tabs; homogeneous recovery; Schlumberger receiver spacing;
dipole length and signed K; current scaling; invalid manual domain; Reset; and
the retained original app's Run button. Doubling current doubled voltage while
leaving apparent resistivity unchanged. The notebook smoke test checks kernel
callbacks; it is not a full browser test of the JupyterLab frontend.

Direct runtime versions were NumPy 2.3.5, SciPy 1.17.0, Matplotlib 3.10.8 and
Panel 1.10.0. The clean install resolved Param 2.4.2, Bokeh 3.10.2 and pandas
3.1.1. Optional tools were JupyterLab 4.6.5, nbconvert 7.17.2 and ipykernel 7.4.0.
Requirements pin direct dependencies, not a complete transitive or cross-platform
lock. **Windows and macOS execution were not tested.**

Package downloads and local kernel/server sockets required the cloud tool's
normal approved execution outside its restricted command sandbox. TLS checks
were retained. Writable cache settings are documented in the README. The kernels
printed a local TCP transport notice; no numerical check failed. Browser
sessions, isolated test kernels and the temporary Panel server were closed.

## Numerical results and interpretation

| Reproduced result | Value / implication |
| --- | --- |
| Original smooth-conductivity grid orders | 1.997472, 1.999365, 1.999841; finest RMSE 7.90049e−6 V |
| 2.5D variable-conductivity manufactured-mode orders | **1.988765, 1.997145, 1.999283**, approaching second order |
| Independent layered reference | Exact receiver voltage 1.805438647386 V; apparent resistivity 113.439055823 Ω·m |
| Layered 192×128 benchmark | Apparent-resistivity error **0.00254467%**; secondary receiver-voltage error **0.0214796%** |
| Default selected Wenner measurement | A=35, B=65, M=45, N=55 m; I=0.1 A; host 100 Ω·m, tunnel center (50,15) m and radius 5 m |
| Homogeneous / air / water selected apparent resistivity | **100.000000 / 105.761873 / 95.175462 Ω·m**, on the default 128×64 automatic grid |
| Corresponding secondary receiver voltage | **0 / +0.00917030642 / −0.00767849026 V** |

Homogeneous recovery is exact by construction in the primary/secondary method;
that check alone cannot establish accuracy. The nonzero layered reference and
manufactured refinement support the numerical method. Layered receiver error
is nonmonotonic under refinement because boundary, integration and interpolation
errors can cancel; this result remains in the notebook rather than being forced
to exhibit second-order receiver convergence.

Conductivity remains positive and finite, including the air approximation.
Conservative harmonic face fluxes and Fourier-mode balance are tested. The
current arrows are approximate cell-center directions; they are not the face
fluxes used for balance. In 2.5D, a two-dimensional divergence check omitting the
cross-line/Fourier term is incomplete. The survey map's spacing-level axis is
not depth and is not an inversion.

Finite walls, quadrature cutoffs, stair-stepped tunnel geometry, sharp contrasts
and surface reconstruction still require sensitivity checks. The model has a
flat surface and an infinitely long tunnel axis. Finite 3D tunnel ends, contact
resistance, field noise and inversion are absent. No Onyx field data or actual
instrument-detectability claim is made. Original analysis voltage anomalies are
for the fixed-voltage model and are not apparent resistivity.

## Documentation corrections

- Replaced the obsolete 42-test final report with this current review; archived
  the original report with working links.
- Updated the assignment checklist for the current solver, boundaries,
  verification notebook, automatic controls, visualizations and Git state.
- Corrected guides that still described completed receiver/grid/UI/field stages
  as pending, while keeping historical test evidence labeled by milestone.
- Added Windows Git Bash instructions using the existing `.sim-venv` interpreter
  and clarified that terminal tabs do not select Jupyter kernels.
- Clarified that the source-free PDE applies away from singular source points.
- Labeled the original analysis and idea-discussion presentation material by
  model and date. The historical slide deck itself was not redesigned.
- Updated the AI-use disclosure. Solver methods, saved numerical results and
  notebook outputs were retained.

## Reproduction commands

From the repository root, create/activate a Python 3.12 environment as shown in
[README.md](README.md). For just the app/tests, install `requirements.txt`.
For notebook reproduction, use the superset below:

```bash
python -m pip install -r requirements-notebook.txt
python -m pip check
python -m unittest discover -s tests -v
python -m ipykernel install --prefix .venv --name tunnel-resistivity --display-name "Python (tunnel-resistivity)"
python -m nbconvert --to notebook --execute verification.ipynb --output verification.reexecuted --output-dir outputs/verification --ExecutePreprocessor.timeout=180 --ExecutePreprocessor.kernel_name=tunnel-resistivity
python -m nbconvert --to notebook --execute verification_2p5d.ipynb --output verification_2p5d.reexecuted --output-dir outputs/verification_2p5d --ExecutePreprocessor.timeout=360 --ExecutePreprocessor.kernel_name=tunnel-resistivity
python -m tunnel_resistivity.visualization_demo
python -m tunnel_resistivity.survey_demo
python -m panel serve app.py --show
```

Use the actual environment prefix if it is named `.sim-venv`. On Windows Git
Bash, replace `python` with `./.sim-venv/Scripts/python.exe`; in PowerShell with
a `.venv`, use `.\.venv\Scripts\python.exe`. Both the registered kernel and
interpreter must point to that environment. The [live-app guide](docs/LIVE_APP.md)
also explains notebook use without restarting other kernels.

The other executed static examples are `tunnel_resistivity.demo`, `tunnel_demo`,
`demo_2p5d`, `receiver_demo` and `grid_demo`, all invoked with `python -m` and the
`tunnel_resistivity.` prefix. `python -m analysis.run_experiments` reproduces the
original model's tracked `analysis/results/`; use a separate copy if comparing
without replacing those artifacts. The legacy UI launches with
`python -m panel serve legacy_app.py --show`.

Detailed local logs, rerun notebook copies, comparison JSON, browser screenshots
and environment metadata are under ignored `outputs/final_review/`. These are
review artifacts, not required application inputs. The notebooks, guides and
tracked analysis files contain the scientific evidence needed in the repository.

## Git snapshot at the Step 9 review, before publication

This section records the earlier review snapshot; see the publication update
above for the completed upload and remote verification.

Local branch: **`work`**. HEAD: **`73badd4`**, “Complete 2D electrical resistivity
forward modeling simulator.” Remote:

<https://github.com/mhbilhartz/Geophysical_Computing_final_project_software_design_mhb>

The index has **44 tracked files** from the original project. The current working
tree contains modified documentation/entry points and **38 untracked files**,
including the survey upgrade, its tests, guides, `legacy_app.py`, historical
presentation material and **`verification_2p5d.ipynb`**. None of these untracked
files will be included by `git commit -a` alone. No files were staged, committed
or pushed by this review; the existing index/HEAD were preserved.

Before any future GitHub upload, inspect the full working tree:

```bash
git status --short --untracked-files=all
git diff
git ls-files --others --exclude-standard
```

The future commit must include both entry points, the whole `tunnel_resistivity/`
package, all `tests/`, both executed notebooks, dependency files, current README,
AI disclosure/references, guides/checklist/review and the original
`analysis/results/` figures/CSVs. Environments, caches, generated `outputs/`,
credentials and the instructor's original PDF are excluded. Candidate-file
inspection found no credential patterns; this does not certify unknown future
edits.

**Actions identified at that review:** review/stage the complete upgrade and publish it to the
intended GitHub branch; verify both notebooks' saved outputs, source, figures,
CSVs and documentation links online; confirm instructor access; then submit the
repository link on Canvas. Repository visibility and remote contents were not
changed or rechecked here. Saving/publishing this cloud environment is separate
from committing and pushing to GitHub.

The course document lists the repository deadline as **November 29, 2026,
11:59 p.m. Mountain Time**, and Molly's final presentation as **November 30,
10:24–10:34 a.m. Mountain Time**. Confirm any instructor schedule updates. The
historical idea-discussion deck predates the electrode upgrade; prepare the
final demonstration using the current app and `verification_2p5d.ipynb`.
