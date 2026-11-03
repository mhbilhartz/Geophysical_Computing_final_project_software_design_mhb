# Assignment requirement checklist

Reviewed against the user-supplied *GPGN 436/536 — Final Project Instructions
and Grading Policy*, Fall 2026, on November 3, 2026. This checks the technical
submission and identifies obligations that software tests cannot establish.
**PASS** means evidence was inspected/executed; **PENDING** means a student,
instructor or publication action remains. A passing artifact is not a grade.

## Sections 1–3: software, distinctness, AI and organization

| Requirement | Status | Evidence / remaining action |
| --- | --- | --- |
| Meaningful, clearly defined geophysical problem | PASS | Onyx-motivated tunnel depth/size/contrast question in README and analysis report |
| Numerical method for elliptic/parabolic/hyperbolic PDE | PASS | Elliptic conductivity PDE, visible conservative finite-difference implementation in `solver.py`; student must explain its connection to course methods |
| Python implementation | PASS | Production source, tests and analysis |
| UI changes parameters, runs and shows results | PASS | Panel controls; callback tests and clean-install live browser check documented in FINAL_REVIEW |
| Clearly labeled outputs and physical units | PASS | Tested plot fields/axes/color bars; published analysis figures and CSV column units |
| Focused 1D/2D model is sufficient | PASS | 2D isotropic DC model; complexity is not presented as a grading advantage |
| Substantially distinct from classmates | PENDING | Only instructor/class discussion can establish distinctness and proposal priority |
| Separate simulation and UI modules | PASS | `solver.py`, `geometry.py`, `simulation.py` versus `app.py`; no UI import needed to solve |
| Simulation contains numerical method, parameters and boundaries | PASS | Explicit face assembly, coefficient array and fixed-voltage/insulating conditions; steady elliptic problem has no initial condition |
| Simulation independently importable | PASS | Notebook, analysis and tests import production solver directly |
| Visible course method, not a wrapper around a specialized simulator | PASS | NumPy/SciPy assembly and sparse solve; no geophysical package |
| Use and disclose AI assistance | PASS | AI_USE.md identifies OpenAI Codex and contributions |
| Acknowledge external code/references | PASS | REFERENCES.md; no copied external numerical implementation, illustrative materials identified |
| Student understands and checks AI-generated work | PENDING | Tests provide checking evidence, but independent student understanding must be demonstrated |

## Section 4: numerical verification

| Requirement | Status | Evidence |
| --- | --- | --- |
| Separate Jupyter notebook | PASS | `verification.ipynb`, tracked with saved outputs |
| Same simulation code, independent of UI | PASS | Direct import of `solve_conductivity`, source-path/hash check, no alternate solver |
| Test problem and analytical solution | PASS | Smooth linear conductivity; logarithmic potential derived by substitution |
| Matching parameters and boundary conditions | PASS | Fixed dimensions, coefficients and side voltages; insulated horizontal faces |
| Applicable initial conditions | PASS / not applicable | No time evolution or initial state in a steady elliptic boundary-value problem |
| Run numerical simulation | PASS | Ten code cells executed, plus independent fresh-environment execution |
| Analytical/numerical plots | PASS | Maps, horizontal profiles, errors and current comparisons |
| Quantitative error measure | PASS | Maximum error, RMSE and voltage-span-normalized RMSE |
| Grid/time-step dependence | PASS | Four grids, measured error orders; no time step applies |
| Agreement, discrepancies and limitations | PASS | Measured near-second-order smooth-case convergence; coefficient, boundary and tunnel-geometry limitations explained |
| Simplified verification may support a more complex application | PASS | Same variable-conductivity solver, while explicitly limiting claims about circular interfaces |
| Executed outputs visible on GitHub | PASS locally / PENDING online | Four figures and tables retained; complete notebook still needs commit/push and online visibility check |

## Section 6: repository and submission

| Requirement | Status | Evidence / remaining action |
| --- | --- | --- |
| All simulation and UI source | PASS | Full package and root launch file tracked/staged |
| Executed verification notebook | PASS | Outputs preserved; source notebook unchanged during final reproduction |
| Data needed to run software/verification | PASS | No external data needed; all inputs are generated from stated parameters |
| Dependency file | PASS | Runtime and optional notebook requirements; genuinely isolated fresh install tested |
| README: problem, PDE, method, install, launch and usage | PASS | Final README includes Linux/macOS and PowerShell instructions; only Linux tested |
| Working example and expected results | PASS | Static examples and default UI table; homogeneous exact values stated |
| AI-use statement and references | PASS | AI_USE.md and REFERENCES.md |
| Important figures and data included | PASS | Five PNG/PDF pairs, three CSV tables and provenance in tracked `analysis/results/` |
| Runnable from a fresh download | PASS on tested platform | Separate project copy and clean Python 3.12 environment; FINAL_REVIEW evidence |
| Repository accessible to instructor | PENDING | Student must verify access after upload; the agent's local tests do not prove instructor access |
| Complete project uploaded by deadline | PENDING | **November 29, 2026, 11:59 p.m. Mountain Time**; no push authorized during this review |
| Submit only repository link on Canvas | PENDING | Student action after verifying the uploaded repository |
| README and notebook provide written documentation | PASS | Both supplied; analysis report is additional scientific interpretation, not a required separate submission |

## Sections 5 and 7: discussion, attendance and presentation

| Requirement | Status | Student preparation / action |
| --- | --- | --- |
| Present a general project idea on assigned discussion date | PENDING | Molly's PDF slot: **November 9, 2026, 10:24–10:36 a.m. Mountain Time**, lecture classroom |
| Discussion: ~5-minute idea presentation + ~7-minute discussion | PENDING | Explain problem/motivation, PDE/method, functionality, verification approach and questions/challenges |
| Attend discussion sessions and sign attendance sheets | PENDING | Attendance is a student obligation; project artifacts cannot establish it |
| Seek arrangements for approved assigned-date absence | PENDING if needed | Contact instructor if applicable; no contact is made by this project review |
| Final presentation is 10 minutes | PENDING | Molly's PDF slot: **November 30, 2026, 10:24–10:34 a.m. Mountain Time**, lecture classroom |
| 4 minutes software design/demo | PENDING | Introduce geophysical purpose, demonstrate controls and interpret actual results |
| 4 minutes simulation code + verification walkthrough | PENDING | Explain PDE, face averaging, boundary distances, sparse solve and notebook error/refinement plots |
| 2 minutes independent instructor questions | PENDING | Answer without AI; navigate source/notebook on GitHub; no live coding required |
| Before presentation: running UI, GitHub solver, executed GitHub notebook open | PENDING | Complete local setup and online checks before the slot begins |
| Explain physics, discretization, solver, conditions and limitations | PENDING | README and notebook support preparation; understanding is demonstrated by the student |
| UI implementation explanation not required | PASS / scope note | Focus code walkthrough on the geophysical simulation |
| Attend all final-presentation sessions and sign sheets | PENDING | November 30; December 2, 3 and 7; December 9 if presentations are subsequently scheduled there |
| Interpret verification separately from a software demo | PASS artifacts / PENDING delivery | Executed notebook is separate, with mathematical derivation and measured errors |

## Section 8: grading and readiness

The rubric allocates **30 points to participation** and **70 to presentation**:
30 software design/demo, 15 numerical-code explanation, 15 analytical verification,
and 10 independent answers. Repository completeness and successful tests provide
evidence, not guaranteed points. The instructor assesses distinctness, scientific
reasoning, attendance, presentation and independent understanding.

No required technical artifact is currently known to be missing. The project is
ready for student review of the final files and Git status. **Publication, access
verification, Canvas submission, attendance and presentation remain pending.**
See [FINAL_REVIEW.md](FINAL_REVIEW.md) for executed reproduction results and the
final file/Git-status snapshot. Nothing is pushed by this review.
