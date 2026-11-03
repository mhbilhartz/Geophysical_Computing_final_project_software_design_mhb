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
