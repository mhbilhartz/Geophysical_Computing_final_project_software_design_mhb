# Five-minute discussion speaking script

> Historical idea-discussion material for the November 9 slot and original
> fixed-voltage model. It is not an updated final-presentation script for the
> 2.5D survey app. Use [the current review](../FINAL_REVIEW.md) and
> [live-app guide](../docs/LIVE_APP.md) for current behavior and verification.

November 9, 2026 · Molly Bilhartz · approximately 5 minutes, followed by 7 minutes of discussion.
Timing targets total 300 seconds. Practice with a timer and allow short pauses for figures.

## Slide 1 — Underground mine tunnels: an electrical perspective (45 seconds)

My project investigates electrical responses from underground mine tunnels. It is motivated by our field investigation of the historic Onyx mine in Steamboat Springs, Colorado. The question is how tunnel depth, radius, and electrical contrast influence potential near the ground surface. A void containing air can be much more resistive than surrounding rock, while conductive water can change that contrast or reverse it. I have built a simplified two-dimensional forward model to explore those effects. These are hypothetical experiments, not a fit to Onyx survey data, and they do not establish whether a particular instrument could detect a tunnel. Today I would especially like feedback on the model assumptions and the appropriate scope.

## Slide 2 — Steady conduction on a finite-difference grid (75 seconds)

The governing equation is divergence of conductivity times the potential gradient equals zero. It describes steady electrical conduction without internal current sources. Ohm’s law gives current density as minus conductivity times the potential gradient, and conductivity is the reciprocal of resistivity. Conservation of current then gives this elliptic equation. There is no time step or initial condition.

I divide a rectangular subsurface region into cells and assign one potential to each cell center. Cells whose centers fall inside a circle receive the tunnel conductivity; the others receive host conductivity. This makes the intended circle stair-stepped on the grid.

Each cell exchanges current with its four neighbors. At a shared face, I use the harmonic mean of the two conductivities, representing two half-cell resistances in series. The same face conductance enters both neighbors’ equations, conserving current. The left boundary is fixed at one volt and the right at zero; the top and bottom are insulating. Side boundaries are half a cell from adjacent centers. These equations form a sparse system, A V equals b, solved with SciPy. The assembly remains visible in Python.

## Slide 3 — Explore scenarios with the actual Panel app (60 seconds)

This is an actual screenshot of the Panel application. The numerical solver is separate from the interface, so I can import the same solver in tests and notebooks. Controls change tunnel center depth, radius, horizontal position, host resistivity, tunnel resistivity, and grid resolution. Air, water, and custom presets help compare contrasts. Run updates the simulation, and Reset restores defaults.

The four panels display resistivity, electrical potential, current-density magnitude with direction arrows, and potential difference relative to a homogeneous model. The reference uses the same grid and boundary conditions. The interface also reports current conservation and retains the previous successful run. I am showing a screenshot rather than relying on a live demonstration during this short discussion. The completed implementation gives me a way to test scientific ideas, but the aim today is feedback on the project’s framing.

## Slide 4 — Preliminary results: depth weakens; size strengthens (75 seconds)

These figures come from the controlled experiments, with a hundred-ohm-meter host. On the left, keeping radius at five meters, increasing burial depth from seven and a half to thirty-five meters reduces the air-case peak from about thirty-eight point three one to four point two five millivolts. The more distant perturbation produces a weaker, broader surface response.

On the right, at fifteen meters depth, increasing radius from two to nine meters raises the air anomaly from about two point seven one to fifty-two point one five millivolts. The trend is approximately quadratic over this range, rather than linear, consistent with an increasing disturbed cross-sectional area. This is an empirical trend in this model, not a universal scaling law.

Resistive tunnels divert current around their interiors. Conductive tunnels concentrate current and reverse the signed surface-anomaly pattern relative to the air case. The plotted magnitudes alone do not show that sign reversal. These results use idealized side voltages; they are not apparent-resistivity measurements or instrument detection predictions.

## Slide 5 — Verification, limitations, and discussion (45 seconds)

For verification, I used the same solver with smoothly varying conductivity and a logarithmic analytical potential. Errors were evaluated at cell centers on twenty-by-ten, forty-by-twenty, eighty-by-forty, and one-hundred-sixty-by-eighty grids. The measured RMS error orders approach two. This verifies the smooth mathematical case; it is not field validation or proof of the same accuracy at a circular conductivity jump.

Limitations include idealized side voltages, an infinitely long two-dimensional tunnel, and a stair-stepped circle. Doubling domain width changed gradient-normalized anomalies by roughly fourteen to eighteen percent, so boundaries matter.

Is this controlled fixed-potential model sufficient for the assignment? Would realistic surface electrodes be a worthwhile later extension, or should I prioritize deeper interpretation and sensitivity checks within the present scope?

Approximate script length: 714 words. At 140–150 words/minute, speech takes 4.8–5.1 minutes, plus brief pointing pauses.
