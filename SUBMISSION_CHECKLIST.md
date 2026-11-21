# Assignment requirement checklist

Project artifacts rechecked November 21, 2026. Course requirements, rubric and
schedule below were transcribed from the user-supplied *GPGN 436/536 — Final
Project Instructions and Grading Policy*, Fall 2026, during the November 3 review.
This review does not establish attendance, instructor approval or a grade.
**PASS** means local technical evidence; **PENDING** identifies a remaining
student, instructor or GitHub action. See [the current review](FINAL_REVIEW.md)
for checks actually executed and platform limits. Publication statuses were
updated after the November 21 upload of code commit `b7e4118` to public GitHub
`main`; the report records the independent-download and web-page checks.

## Software, method and organization

| Requirement | Status | Evidence / remaining action |
| --- | --- | --- |
| Meaningful geophysical problem | PASS | Onyx-motivated tunnel effects on surface DC measurements; hypothetical properties, no measured mine data |
| Visible Python numerical PDE method | PASS | Conservative finite differences and harmonic interface conductivities in `solver.py` and `solver_2p5d.py`; SciPy sparse solves, no geophysical simulation package |
| Clear model and boundaries | PASS | Default 2.5D point sources: insulating surface away from electrodes, analytical-primary total potential on finite outer walls; retained original 2D model: 1/0 V sides, insulated top/bottom |
| Separate simulation and UI | PASS | Importable source, receiver, survey and grid modules; Panel in `survey_app.py`, plotting in `survey_plotting.py` |
| Adjustable inputs and labeled results | PASS | Tunnel depth/radius/position, material/custom resistivity, array/spacing/current and grids; automatic updates, fields/profiles/data and diagnostics |
| Simulation independently importable | PASS | Both verification notebooks and tests call production numerical modules without the UI |
| Appropriate scope | PASS | Steady 2.5D forward model with flat surface and infinite tunnel axis; no inversion, finite 3D tunnel or instrument-detection claim |
| Substantially distinct from classmates | PENDING | Instructor/class discussion establishes distinctness and proposal approval |
| AI assistance and references disclosed | PASS | `AI_USE.md` and `REFERENCES.md` describe contributions, methods and student responsibility |
| Independent student understanding | PENDING | Explain sources, boundaries, Fourier reduction, harmonic fluxes, receiver polarity, errors and limitations without AI |

## Numerical verification

| Requirement | Status | Evidence |
| --- | --- | --- |
| Separate executed notebook for current app | PASS locally | `verification_2p5d.ipynb`: production 2.5D source/operator/receiver imports, ten executed code cells, five embedded figures, 26 acceptance checks |
| Analytical solution/reference | PASS | Homogeneous half-space fields, transform identity, manufactured constant/smooth-conductivity modes and independent two-layer image series |
| Same numerical method as application | PASS | Manufactured tests import the production spatial assembly; nonzero layered tests call the actual source solver and receiver reconstruction |
| Matching parameters/conditions explained | PASS | Manufactured boundary/forcing matches exactly; layered half-space versus finite numerical-wall mismatch is identified and studied |
| Quantitative error and refinement | PASS | Field/receiver/apparent-resistivity errors, mesh refinement, Fourier integration and domain sensitivity; near-second-order smooth spatial-mode convergence |
| Distinguish verification from a demo | PASS artifacts / PENDING delivery | Mathematical references, error tables and discussion are separate from the interactive survey |
| Applicable initial/time conditions | PASS / not applicable | Steady elliptic model has no time step or initial condition |
| Original numerical verification retained | PASS locally | `verification.ipynb`: ten executed code cells, four figures, smooth logarithmic solution and grid refinement for retained `legacy_app.py` |
| Error limits stated | PASS | Exact homogeneous primary is insufficient alone; nonzero layered check included; stair-stepped circles, finite walls, Fourier cutoffs, interpolation and cancellation remain limitations |
| Saved notebook files/outputs online | PASS files / PENDING visual preview | Both GitHub pages returned HTTP 200; independent download contains all nine embedded figures and saved results. Cloud cannot reach GitHub’s notebook-preview host; student should open both previews once |

## Repository and submission

| Requirement | Status | Evidence / remaining action |
| --- | --- | --- |
| All source, tests and launch files available | PASS on GitHub | All 82 project files at code commit `b7e4118` independently downloaded and matched, including the survey upgrade, both entry points and tests |
| Data needed to run | PASS | No external dataset; all inputs generated from stated parameters |
| Dependency files | PASS | Pinned direct runtime and optional notebook requirements; clean Python environment review in `FINAL_REVIEW.md` |
| README covers problem, PDE, method, installation and use | PASS | Current default app and retained legacy app are distinguished; browser and Jupyter launch instructions supplied |
| Working examples and expected results | PASS | Static solver, receiver, survey, grid and visualization commands; numerical references in guides |
| Important figures and CSVs | PASS locally | Original analysis artifacts in tracked `analysis/results/`; 2.5D verification results also saved inline in its notebook. Ignored `outputs/` artifacts are regenerable |
| Reproducible fresh download | PASS on tested platform | Isolated Linux/Python 3.12 reproduction passed; independently cloned GitHub code commit matches the reviewed project byte-for-byte |
| GitHub availability / instructor access | PASS public availability / PENDING instructor confirmation | Public repository and required file pages returned HTTP 200. Student should check the link from the browser/account used for class |
| Complete project uploaded by deadline | PASS upload | Pushed November 21, before **November 29, 2026, 11:59 p.m. Mountain Time**; main contains the complete reviewed project |
| Submit repository link on Canvas | PENDING | Student action after verifying GitHub contents; this review does not submit anything |
| Written documentation | PASS | README, separate notebooks, numerical/user guides and analysis interpretation |

## Discussion, attendance and final presentation

| Requirement | Status | Student action |
| --- | --- | --- |
| Assigned idea discussion | PENDING verification | PDF slot: **November 9, 2026, 10:24–10:36 a.m. Mountain Time**; date has passed, attendance/outcome not established here |
| Discussion format | PENDING verification | Approximately five-minute idea presentation and seven-minute discussion; files under `presentations/` are historical original-model material |
| Discussion attendance/sign-in and any absence arrangement | PENDING verification | Student/instructor records establish these obligations |
| Final presentation, ten minutes | PENDING | PDF slot: **November 30, 2026, 10:24–10:34 a.m. Mountain Time**, lecture classroom |
| Four-minute design/demo | PENDING | Demonstrate current arrays, sliders, automatic updates and correctly interpret fields/apparent resistivity |
| Four-minute code/verification walkthrough | PENDING | Use current `solver_2p5d.py` and `verification_2p5d.ipynb`; distinguish the original fixed-voltage notebook if shown |
| Two-minute independent questions | PENDING | Answer without AI; navigate source/notebook; no live coding required |
| UI, GitHub solver and executed GitHub notebook open beforehand | PENDING | Prepare the running app and verify online outputs before the slot |
| Explain physics/numerical conditions/limits | PENDING | Include why point electrodes require the 2.5D source formulation, signs of K and voltage, and spacing level versus depth |
| UI-code explanation | PASS / scope note | Focus numerical walkthrough on the simulation; UI implementation explanation is not required |
| Final-session attendance/sign-in | PENDING | November 30; December 2, 3 and 7; December 9 if scheduled, per original course document |

## Grading and readiness

The original rubric allocates **30 participation points** and **70 presentation
points**: 30 software design/demo, 15 numerical-code explanation, 15 analytical
verification and 10 independent answers. Tests and artifacts are evidence, not
guaranteed points. Schedule changes, approval, attendance, independent understanding
and grading remain with the student/instructor.

The current technical and publication review is [FINAL_REVIEW.md](FINAL_REVIEW.md).
The complete upgrade is on public GitHub `main`. Remaining actions are the visual
notebook-preview check, instructor-specific access confirmation, Canvas link
submission and presentation. The old idea-discussion slide deck is retained as
historical material and should not be used as the final 2.5D presentation without
updating its physics and screenshots.
