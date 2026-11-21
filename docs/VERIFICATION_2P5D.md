# Survey upgrade, Step 4: analytical verification notebook

Open [verification_2p5d.ipynb](../verification_2p5d.ipynb). It imports the existing
production `solver_2p5d.py`, the spatial operator that solver calls, and
`receivers.py`, independently of Panel. No solver, receiver, UI module, existing
test, or original `verification.ipynb` is replaced by this milestone.

The default Panel application now uses this 2.5D backend through the
[Step 7 live interface](LIVE_APP.md). The saved notebook records the earlier
Step 4 state, when UI integration was still pending; its numerical solver and
receiver code are unchanged. The original notebook continues to verify the
retained fixed-voltage application launched via `legacy_app.py`.

## Open and rerun

Use the existing project environment from the repository root:

```bash
python -m pip install -r requirements-notebook.txt
python -m jupyterlab verification_2p5d.ipynb
```

In JupyterLab, select the kernel associated with that environment, choose
**Restart Kernel and Run All Cells**, then save. If a kernel needs registering,
follow the README's `ipykernel install` instructions. No external data are needed.
The largest mesh/domain solves can take several minutes; successful completion
prints `VERIFICATION COMPLETE` in the final cell. There are no time steps or
initial conditions because the PDE is steady elliptic.

On Windows PowerShell, use the environment's interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv\Scripts\python.exe -m jupyterlab verification_2p5d.ipynb
```

Substitute your actual environment directory if it has another name, such as
`.sim-venv`. In an already running JupyterLab, open the notebook and select your
project kernel; do not restart unrelated running kernels.

After registering the `tunnel-resistivity` kernel as documented in the README,
a command-line execution can preserve the submitted notebook and write an
ignored copy instead:

```bash
python -m nbconvert --to notebook --execute verification_2p5d.ipynb --output verification_2p5d.reexecuted --output-dir outputs/verification_2p5d --ExecutePreprocessor.timeout=360 --ExecutePreprocessor.kernel_name=tunnel-resistivity
```

Windows uses the same arguments after `.\.venv\Scripts\python.exe -m nbconvert`.
Local notebook execution requires local kernel sockets. In this cloud session,
the restricted command sandbox blocked those sockets; the prepared notebook was
run using the execution tool's approved permission for local kernel startup.
No network service, repository push, or environment publication is part of this
verification.

## What the notebook verifies

| Check | Analytical reference or independent calculation | What it establishes |
| --- | --- | --- |
| Homogeneous fields and all three arrays | ρI/(2π)(1/rA−1/rB); independent current gradients and closed-form K | Units, source amplitude, receiver sampling and dipole polarity; primary recovery is exact by construction |
| Fourier normalization | ∫₀∞ K₀(kr) dk=π/(2r) | Inverse-transform factor and log-quadrature Jacobian |
| Spatial refinement | Manufactured sin(πx/W)cos(πz/(2H)) with constant and smoothly varying positive σ | Convergence of the same production Fourier operator with exactly matching boundaries |
| Mode conservation | Independently reconstructed harmonic face currents plus k² mass term | Local conservative balance; a 2D physical-current divergence test would omit cross-line spreading |
| Nonzero physical response | Independent two-layer image-source series | Full source solve plus surface receiver calculation, beyond a zero-secondary test |
| Analytical-reference checks | Layer potential/current continuity and image-series truncation | Internal mathematical checks on the independent reference |
| Mesh and outer walls | Fixed domain while refining; fixed spacing while enlarging domain | Separates sensitivity to spatial resolution and artificial boundaries |
| Actual Fourier integration | Fixed physical models while varying node count/cutoffs | Sensitivity of nonzero layered/water-tunnel corrections |
| Air/water sanity | Positive finite σ, finite fields, mode diagnostics and signed Wenner response | Qualitative consistency and numerical stability for the stated contrasts |

The manufactured test imports the production assembly and solves a prescribed
forcing with SciPy, rather than copying finite-difference code. Analytical image
functions only evaluate explicit mathematical series; they are not separate
numerical PDE solvers.

## Reading the errors correctly

The restored project's **92 automated tests passed** before notebook work.
The executed notebook has **10 code cells, five embedded figures, and 26
successful acceptance checks**. Its variable-conductivity manufactured problem
measures orders **1.988765, 1.997145, and 1.999283**; the finest RMSE is
2.0832843e-5 V·m. The layered reference has exact ΔV=1.805438647386 V and
ρₐ=113.439055823 Ω·m. On the 192×128 benchmark mesh, apparent-resistivity error
is about **0.002545%**, and secondary receiver-voltage error about **0.02148%**.

On that same layered mesh, changing 64 nodes/fixed cutoffs to 96 nodes/extended
cutoffs changes the secondary field by about 3.11e-7 relative and the secondary
receiver voltage by about 1.65e-7 relative. These small sensitivity values
support using the chosen quadrature for this case, while the domain/grid study
still exposes finite-boundary and interpolation effects.

The notebook distinguishes maximum/absolute RMS cell error, error relative to the
exact **secondary** field, error relative to secondary receiver voltage, and
error relative to total apparent resistivity. Small secondary anomalies can have
larger relative errors even when total apparent resistivity agrees closely.

The manufactured problem matches the numerical boundaries exactly. The layered
reference is an infinite half-space, while the production solver imposes
homogeneous-primary total potential at finite side/bottom walls. That mismatch is
explicitly included in the discussion and domain study. It must not be mistaken
for a pure spatial-truncation error.

The smooth manufactured operator shows approximately second-order convergence.
Physical receiver refinement is not assumed to have that rate: interpolation,
integration and boundary errors can cancel, producing nonmonotonic total errors.
The notebook retains and explains those results instead of forcing a slope.
Stair-stepped circles have additional geometric errors not bounded by smooth-mode
verification. None of these checks is validation against field measurements.

## Saved evidence and reproducibility

The notebook itself contains executed numerical tables, five embedded figures,
and the final assertion record. It remains readable when generated output files
are absent. Rerunning regenerates the following ignored artifacts under
`outputs/verification_2p5d/`:

- CSV tables for homogeneous recovery, Fourier identity, manufactured modes,
  layer-series truncation, layered mesh/domain results, layered and water Fourier
  sensitivity, tunnel sanity, and acceptance checks.
- Five standalone figures in both PNG and PDF formats.
- `summary.json`, with full-precision results, package versions, source SHA-256
  hashes, parameters, diagnostics and acceptance-check outcomes.

Reruns replace those regenerable copies. All numerical results and figures
needed to review the notebook are also saved inline; the ignored directory is
not required input and is not automatically committed to GitHub.

See [Step 2](SOURCE_PAIR_2P5D.md) for the numerical method and
[Step 3](RECEIVER_MEASUREMENTS.md) for surface interpolation, K and voltage
polarity. The notebook's final checklist maps its evidence to the supplied
course document's numerical-verification criteria. GitHub publication remains separate work. Step 7 now connects this backend to
the interactive application, and [Step 8](VISUALIZATIONS.md) supplies its field
visualizations. See [the current final review](../FINAL_REVIEW.md) for regression
results after both integrations.
