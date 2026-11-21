# Preparation and likely questions

> Historical idea-discussion material for the November 9 slot and original
> fixed-voltage model. It is not an updated final-presentation script for the
> 2.5D survey app. Use [the current review](../FINAL_REVIEW.md) and
> [live-app guide](../docs/LIVE_APP.md) for current behavior and verification.

This is the Section 5 idea discussion: 5 minutes presenting and 7 minutes discussing, not the final 10-minute assessment. Molly's assigned slot is November 9, 2026, 10:24–10:36 a.m. Mountain Time. Attend and sign the sheet. A working program is not required for this discussion; describe the completed work as preliminary evidence and invite feedback.

## Likely questions and accurate answers

- **Why this PDE?** Charge conservation gives divergence of J = 0; isotropic Ohm's law J = −σ grad V gives the elliptic conductivity equation for steady DC conduction without internal sources.
- **Why harmonic averaging?** Adjacent half-cell electrical resistances add in series. One shared face conductance is used in both neighbor equations, conserving current.
- **What are the boundaries?** Left 1 V, right 0 V, insulated top/bottom. Fixed-voltage faces are half a cell from adjacent unknowns; the first column itself is not fixed at 1 V.
- **Why no initial condition?** This is a steady elliptic boundary-value problem, not time evolution.
- **What makes air different from water?** The illustrative air tunnel is 1e8 Ω·m and water 5 Ω·m in a 100 Ω·m host. Air suppresses interior current; water concentrates it. Actual mine properties were not supplied.
- **What is the reference?** A uniform host on the same grid, domain and boundary conditions. Surface anomaly is tunnel minus reference potential reconstructed from the first row under the insulating condition.
- **How is verification nontrivial?** Smooth σ(x)=0.01(1+2x/100) produces exact V=1−ln(1+2x/100)/ln(3), a curved profile. Errors decrease with measured near-second-order convergence. The homogeneous linear solution alone cannot demonstrate convergence.
- **What does the order prove?** Accuracy for this smooth, x-varying test using the production 2D solver. It does not prove the same order at stair-stepped circular jumps or validate field predictions.
- **Does widening the domain change the imposed field?** Yes: fixed 1 V across width W gives E0=1/W. Comparing A/E0 separates that forcing change from boundary displacement. It has units of meters, not apparent resistivity. Normalized peaks increase 17.62% for air and 14.15% for water from W=100 to 200 m.
- **Is a bigger anomaly necessarily detectable?** No. No electrode array, instrument noise, acquisition geometry or site calibration is modeled. These are simulated potential differences, not apparent resistivity or a detection limit.
- **Can you uniquely recover a tunnel?** Not from peak magnitude alone. Depth, size and contrast trade off; multiplying both resistivities by the same factor leaves potential unchanged under fixed voltages while changing current.
- **Would you add electrodes now?** That is a possible later extension, not part of the current implementation. Ask whether it would improve the course project's scope enough to justify new boundary/source modeling and verification.

## Practice checklist

- Rehearse to 5 minutes; shorten explanations before rushing the verification/discussion slide.
- Slide 2: explain current balance intuitively rather than deriving the entire matrix.
- Slide 3: use the real screenshot; no live demo is required for this short talk.
- Slide 4: read air-case numbers once, then explain the physical cause. Magnitude plots do not display sign; describe sign reversal separately.
- Slide 5: leave time to ask both questions. Do not claim the professor has approved scope or distinctness.
- Review the actual solver and notebook before answering independently.

## Figure provenance

- Slide 3: existing `outputs/panel_interface.png`, a captured real Panel session. Its Run 3 label and prior-run diagnostics belong to that captured session.
- Slide 4: `analysis/results/01_depth.png` and a crop of the left amplitude panel of `02_radius.png`. The crop changes framing, not data.
- No generated illustrative or fabricated scientific images are used.
- Source documents: professor's Fall 2026 instructions, Section 5; project README, analysis report, solver and executed verification notebook.

All slide text and shapes remain editable; scientific figures and the screenshot are embedded raster images. Speaker notes contain the complete script. No presentation files were committed or pushed.
