# AI-use disclosure

**Tool:** OpenAI Codex, used during development, debugging, documentation and
repository preparation. The student supplied the geophysical motivation and
project goals and remains responsible for scientific correctness and understanding.

Codex assisted with:

- The visible conservative finite-difference implementation, harmonic face
  averaging, circular geometry, numerical diagnostics and static examples.
- The separate Panel controls, plotting and interface-to-solver orchestration.
- Automated tests and live browser checks; debugging a color scale that amplified
  roundoff in the homogeneous current plot without changing its computed values.
- The analytical derivation, executed verification notebook and measured grid
  convergence using the same production solver as the application.
- Controlled geophysical experiments, CSV results, scientific figures and their
  interpretation, including grid/domain sensitivity and nonuniqueness.
- Final documentation, assignment checklist, isolated fresh-install reproduction,
  file/Git review and minimal nonfunctional whitespace/cache cleanup.
- The subsequent survey upgrade: electrode geometry, a separate primary/secondary
  2.5D Fourier source-pair solver, numerical tests, static examples and derivations
  in [the Step 2 notes](docs/SOURCE_PAIR_2P5D.md). Subsequent steps connected this
  backend to Panel; it has not been validated against field data.
- [Step 3 receiver calculations](docs/RECEIVER_MEASUREMENTS.md): surface sampling,
  signed geometric factors and apparent resistivity, nonzero layered-earth
  comparisons, automated tests, and reproducible static examples.
- The separate [2.5D verification notebook](verification_2p5d.ipynb), including
  manufactured solutions using the production spatial operator, independent
  image-source references, executed refinement/integration/domain experiments,
  plots, and discussion of error cancellation. Interactive survey controls were added in the later Step 7 work below.
- [Step 5 survey generation](docs/SURVEYS.md), including physical electrode-line
  geometry, source-pair reuse within one fixed-model run, ordered scalar/CSV
  results, automated tests and example surveys. Off-center dipole anomaly signs
  were checked with direct calls, mesh refinement and domain extension.
- [Step 6 grid/domain planning](docs/GRIDS.md): automatic and manual grids,
  physical-coordinate conversion into the original circle helper, resolution
  and cell-budget checks, diagnostic notes, automated tests and controlled
  mesh/domain examples. The numerical method and existing interface are retained.

- [Step 7 live interface](docs/LIVE_APP.md): immutable parameter snapshots,
  debounced background calculations, cooperative cancellation in the survey
  orchestrator, stale-result protection, Panel controls and basic result views,
  CSV metadata, automated tests, real Chromium interactions and an isolated
  Jupyter live-update check. The numerical solver/receiver methods were retained.

- [Step 8 visualizations](docs/VISUALIZATIONS.md): completed-measurement selection,
  reuse of the existing source-pair solver with saved grid/Fourier settings,
  a bounded source-field cache, potential/current/anomaly maps, surface curves,
  uninterpolated survey maps, snapshot-safe PNG export, automated tests,
  reproducible examples and live browser checks. Both solvers, receiver
  calculations and executed verification notebooks were preserved.

- [Step 9 final review](FINAL_REVIEW.md): clean-environment installation and
  regression testing, reexecution of both verification notebooks to separate
  copies, reproduction/comparison of scientific results, current/legacy browser
  checks, documentation corrections and repository-readiness review. Historical
  model results and presentation material were distinguished from the current
  2.5D survey application; no new solver or modeling features were added.

- The updated [browser-only deployment](docs/BROWSER_DEPLOYMENT.md): Pyodide
  Web Worker integration, browser controls and mobile layout, static-runtime
  packaging, GitHub Actions/Pages workflow, browser-adapter tests and actual
  WebAssembly numerical/interaction checks. Existing solvers and saved
  verification notebooks were preserved. The deployment architecture follows
  the instructor's subsequently supplied directions.

No external numerical implementation or specialized geophysical simulator was
incorporated. Standard libraries perform array operations, sparse linear algebra
and plotting. [REFERENCES.md](REFERENCES.md) acknowledges the course document,
analytical-profile origin and method/library references. The Onyx mine motivation
came from the student's field investigation; no field data or measured material
properties were used. All reported experimental values are simulated.

Automated tests and AI assistance do not replace independent student review.
The student must understand and reproduce the solver and verification, explain
limitations, and answer presentation questions independently without AI assistance.
No field-validation or instrument-detectability claim is made.
