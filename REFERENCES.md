# References and attribution

## Course and project sources

- Course instructor, *GPGN 436/536 — Final Project Instructions and Grading
  Policy*, Fall 2026, user-supplied PDF. Sections 3, 4, 6, 7 and 8 specify code
  organization, verification, submission and presentation requirements. The
  PDF itself is not redistributed here; it includes classmates' schedules.
- The student's stated Onyx mine investigation in Steamboat Springs, Colorado
  motivates the application. No mine data or measured material properties are
  incorporated, and illustrative values are not attributed to field measurements.
- The logarithmic analytical profile was proposed in the student's Step 4
  request; its derivation and substitution into the PDE are shown in
  [verification.ipynb](verification.ipynb). It is not taken on trust as numerical
  ground truth without the mathematical check.

## Numerical and software references

- LeVeque, R. J. (2007). *Finite Difference Methods for Ordinary and Partial
  Differential Equations: Steady-State and Time-Dependent Problems*. SIAM.
  [DOI: 10.1137/1.9780898717839](https://doi.org/10.1137/1.9780898717839).
  Suggested background on finite differences and convergence; no implementation
  from this book was copied into the project.
- NumPy: [array documentation](https://numpy.org/doc/stable/).
- SciPy: [sparse matrix documentation](https://docs.scipy.org/doc/scipy/reference/sparse.html)
  and [`spsolve`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.spsolve.html).
- Matplotlib: [plotting documentation](https://matplotlib.org/stable/).
- Panel: [application documentation](https://panel.holoviz.org/).
- Jupyter: [JupyterLab](https://jupyterlab.readthedocs.io/en/stable/) and
  [nbconvert execution](https://nbconvert.readthedocs.io/en/latest/execute.html).

The steady PDE follows charge conservation and Ohm's law, as explained in the
README. The conservative face balance and harmonic mean are explicitly visible
in `solver.py`; no external solver implementation or geophysical package was
copied. Libraries perform array operations, sparse linear algebra and display.
The project does not claim a site-calibrated physical model or field validation.

AI-generated contributions and the student's responsibility to review and
understand them are disclosed in [AI_USE.md](AI_USE.md).
