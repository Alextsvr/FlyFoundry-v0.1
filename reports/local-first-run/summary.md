# FlyFoundry run summary

- **Status:** completed  |  **Run:** `20261011T220705Z-c2262f`
- **Generations:** 40 -> 60 (cumulative 60)
- **Fitness evaluations:** 180,000 total, 60,000 this run (100 agents x 6 arms x 5 seeds)
- **Resources this run:** CPU 12.136 s, wall 12.265 s, peak RSS 139.6 MB
- **Code revision:** `ee3f7becee17`  |  **Checkpoint:** v3 (sha256 `bfb044e69455`)
- **Checkpoint recovery problems:** none
- **Resume test:** {"loaded_from_version": 2, "gens_before": 40, "saved_version": 3, "reload_roundtrip_identical": true, "generation_after_reload": 60}
- **Arm E (LLM baseline):** NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |
|---|---|---|---|---|---|---|
| A fly-inspired + plasticity | 0.192 [0.181, 0.208] | 0.212 | 0.378 | 2.4 | 0.0320 | 0.203 |
| A fly-inspired, no plasticity | 0.201 [0.180, 0.222] | 0.220 | 0.388 | 1.8 | 0.0335 | 0.222 |
| A fly-inspired, shuffled wiring | 0.192 [0.176, 0.213] | 0.211 | 0.385 | 2.0 | 0.0320 | 0.205 |
| B evolved ANN | 0.344 [0.334, 0.353] | 0.430 | 0.510 | 2.6 | 0.0573 | 0.395 |
| C genetic algorithm | 0.369 [0.351, 0.392] | 0.459 | 0.480 | 3.0 | 0.0615 | 0.413 |
| D random search | 0.322 [0.319, 0.325] | 0.322 | 0.209 | 0.0 | 0.0536 | 2.250 |

## Conclusions (conservative, auto-generated)

**Scope**  
Results cover 60 generations x 100 agents per arm and 5 paired seeds on a SYNTHETIC benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). With n=5 < 10 seeds, no statistical-significance claim is made; intervals are indicative only.

**Best arm per measured metric (mean of last 5 generations, across seeds)**  
- Held-out quality-diversity score: highest mean = C_genetic (0.369); lead over B_evolved_ann = +0.025; bootstrap intervals overlap (no clear separation).
- Held-out best candidate score: highest mean = C_genetic (0.459); lead over B_evolved_ann = +0.029; bootstrap intervals overlap (no clear separation).
- Held-out peak discovery rate: highest mean = C_genetic (0.171); lead over B_evolved_ann = +0.073; intervals do not overlap.
- Train best-of-generation fitness: highest mean = B_evolved_ann (0.510); lead over C_genetic = +0.029; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Train mean fitness: highest mean = B_evolved_ann (0.236); lead over C_genetic = +0.011; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Distinct real peaks discovered (train): highest mean = C_genetic (3.000); lead over B_evolved_ann = +0.400; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Viable niches (archive): highest mean = A_fly_shuffled (52.160); lead over A_fly_plastic = +0.200; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Population diversity: highest mean = D_random (0.401); lead over A_fly_noplast = +0.094; intervals do not overlap.
- Novelty: highest mean = D_random (0.250); lead over A_fly_noplast = +0.082; intervals do not overlap.

**Headline (held-out only)**  
On the held-out quality-diversity score the highest-scoring arm is C_genetic (0.369) ahead of B_evolved_ann (0.344). Paired difference +0.025 (95% bootstrap CI +0.004 to +0.047, n=5). The CI excludes zero, but with this few seeds this is preliminary and is not declared a winner.

**Did the biologically inspired architecture add measurable value?**  
- Mushroom-body-inspired controller with plasticity vs an evolved ANN with the same parameter budget and evolutionary engine: held-out QD diff -0.152 [-0.166, -0.137] - CI excludes zero (preliminary).
- Mushroom-body-inspired controller with plasticity vs the same circuit without plasticity: held-out QD diff -0.009 [-0.030, +0.012] - CI includes zero: no measurable difference.
- Mushroom-body-inspired controller with plasticity vs the same circuit with shuffled PN->KC wiring: held-out QD diff +0.001 [-0.031, +0.032] - CI includes zero: no measurable difference.
- Even a positive difference would show value of a sparse, plastic architecture on THIS synthetic task, not of real Drosophila connectivity (none is used).

**Uncertainty**  
Intervals are percentile bootstrap CIs over 5 seeds (2000 resamples); a single world (fixed hidden landscape) is used, so results do not generalise across worlds. Metrics are averaged over the last 5 generations to reduce evaluation noise.

**What remains unverified**  
- Any real-world validity: no public evidence dataset is wired in yet; all hypotheses are synthetic-tier.
- Arm E (LLM baseline): NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)
- Biological fidelity: no FlyWire/hemibrain connectivity is used; the controller is a documented mushroom-body-inspired model.
- Robustness across different hidden worlds and benchmark difficulty levels.
- Seeds: n=5 is below the configured minimum of 10.

**Suggested next experiments**  
- Increase seeds to >= 10 (cheap: ~minutes of CPU) and re-test the paired differences.
- Add a second, non-stationary benchmark world (peaks drift over generations) where lifetime plasticity should matter; the current stationary task gives plasticity little to exploit.
- Wire in one public, legitimately accessible evidence dataset (evidence-tier fitness) with recorded provenance.
- Run arm E when a free LLM endpoint is available, at a matched evaluation budget.

## Top hypotheses (synthetic benchmark only; not real-world evidence)

- `HYP-CGEN-s2-a1994-g20` indie game studios / hard-to-compare pricing / automated checker / validator / monthly subscription (held-out fixed score 0.412, EUR 4 est.)
- `HYP-BEVO-s2-a3700-g52` municipal procurement officers / error-prone document handling / alerting / monitoring service / monthly subscription (held-out fixed score 0.405, EUR 15 est.)
- `HYP-AFLY-s3-a1247-g17` indie game studios / hard-to-compare pricing / curated public-data digest / monthly subscription (held-out fixed score 0.404, EUR 5 est.)
- `HYP-CGEN-s3-a4696-g49` freelance translators / error-prone document handling / alerting / monitoring service / usage-based fee (held-out fixed score 0.403, EUR 18 est.)
- `HYP-BEVO-s3-a3133-g44` municipal procurement officers / hard-to-compare pricing / curated public-data digest / monthly subscription (held-out fixed score 0.394, EUR 42 est.)
