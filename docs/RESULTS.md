# Results log

> **Status: LOCAL run only.** At the time of writing the repository could not be created on GitHub from the build session
> (HTTP 403 from the session's GitHub proxy: "sessions are bound to their configured repositories"), so **no GitHub Actions run has happened yet**.
> Everything below was produced on the build sandbox (Python 3.13.16, numpy 2.5.3; the 19 tests also pass on Python 3.12.3 with `requirements.lock`) with the same code and `configs/nightly.json`.
> Update this file with the Actions run URL once the first workflow run has completed.

## Local first run (3 consecutive resumes x 20 generations = 60 generations)

100 agents x 6 arms x 5 seeds, 180,000 fitness evaluations total (30,000 per arm; 6,000 per arm-seed). Arm E not run.
Checkpoints v1→v2→v3 were each restored by a separate process; every reload was bit-identical to the in-memory state.
CPU ≈ 12 s per 20 generations for all 30 runners (single core); peak RSS ≈ 140 MB; checkpoint ≈ 12 MB.

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Real peaks found (of 6) |
|---|---|---|---|---|
| A fly-inspired + plasticity | 0.192 [0.181, 0.208] | 0.212 | 0.378 | 2.4 |
| A fly-inspired, no plasticity | 0.201 [0.180, 0.222] | 0.220 | 0.388 | 1.8 |
| A fly-inspired, shuffled wiring | 0.192 [0.176, 0.213] | 0.211 | 0.385 | 2.0 |
| B evolved ANN | 0.344 [0.334, 0.353] | 0.430 | 0.510 | 2.6 |
| C genetic algorithm | 0.369 [0.351, 0.392] | 0.459 | 0.480 | 3.0 |
| D random search | 0.322 [0.319, 0.325] | 0.322 | 0.209 | 0.0 |

Reading (conservative; n = 5 seeds < 10, so no significance claim):

* C (plain GA) and B (evolved ANN) are the best arms on held-out metrics; their difference is small (QD +0.025, CI +0.004…+0.047, preliminary).
* All three mushroom-body-inspired variants are **worse** than B, C and, on held-out QD, even than random search. The biological architecture added **no**
  measurable value on this task; plasticity and shuffled wiring made no measurable difference (CIs include 0). Held-out QD is lenient (distance-based partial credit),
  which is why random search scores 0.32; held-out discovery rate (C 0.17, B 0.10, A ≈ 0.0) separates the arms better.
* The stationary landscape gives lifetime plasticity little to exploit; a non-stationary world is the obvious next experiment.
* Nothing here says anything about real markets. Real revenue: EUR 0 / unknown.

Full output of this run: `reports/local-first-run/` (open `index.html`).
