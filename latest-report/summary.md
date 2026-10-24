# FlyFoundry run summary

- **Status:** completed  |  **Run:** `20261024T005923Z-2e1eff`
- **Generations:** 280 -> 300 (cumulative 300)
- **Fitness evaluations:** 900,000 total, 60,000 this run (100 agents x 6 arms x 5 seeds)
- **Resources this run:** CPU 14.045 s, wall 14.047 s, peak RSS 205.7 MB
- **Code revision:** `b4d4e5e213a5`  |  **Checkpoint:** v15 (sha256 `f7504a40b0d6`)
- **Checkpoint recovery problems:** none
- **Resume test:** {"loaded_from_version": 14, "gens_before": 280, "saved_version": 15, "reload_roundtrip_identical": true, "generation_after_reload": 300}
- **Arm E (LLM baseline):** NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |
|---|---|---|---|---|---|---|
| A fly-inspired + plasticity | 0.193 [0.176, 0.207] | 0.224 | 0.444 | 4.8 | 0.0064 | 0.043 |
| A fly-inspired, no plasticity | 0.194 [0.162, 0.223] | 0.226 | 0.460 | 4.2 | 0.0065 | 0.046 |
| A fly-inspired, shuffled wiring | 0.191 [0.170, 0.212] | 0.222 | 0.476 | 4.2 | 0.0064 | 0.043 |
| B evolved ANN | 0.361 [0.358, 0.366] | 0.486 | 0.527 | 3.6 | 0.0120 | 0.086 |
| C genetic algorithm | 0.383 [0.374, 0.390] | 0.495 | 0.490 | 3.2 | 0.0128 | 0.079 |
| D random search | 0.350 [0.343, 0.356] | 0.333 | 0.214 | 0.6 | 0.0117 | 0.517 |

## Conclusions (conservative, auto-generated)

**Scope**  
Results cover 300 generations x 100 agents per arm and 5 paired seeds on a SYNTHETIC benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). With n=5 < 10 seeds, no statistical-significance claim is made; intervals are indicative only.

**Best arm per measured metric (mean of last 5 generations, across seeds)**  
- Held-out quality-diversity score: highest mean = C_genetic (0.383); lead over B_evolved_ann = +0.022; intervals do not overlap.
- Held-out best candidate score: highest mean = C_genetic (0.495); lead over B_evolved_ann = +0.009; bootstrap intervals overlap (no clear separation).
- Held-out peak discovery rate: highest mean = C_genetic (0.220); lead over B_evolved_ann = +0.080; intervals do not overlap.
- Train best-of-generation fitness: highest mean = B_evolved_ann (0.527); lead over C_genetic = +0.037; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Train mean fitness: highest mean = B_evolved_ann (0.267); lead over C_genetic = +0.038; intervals do not overlap [training metric - not a basis for declaring a winner].
- Distinct real peaks discovered (train): highest mean = A_fly_plastic (4.800); lead over A_fly_noplast = +0.600; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Viable niches (archive): highest mean = A_fly_plastic (62.200); lead over A_fly_shuffled = +1.000; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Population diversity: highest mean = D_random (0.402); lead over A_fly_noplast = +0.097; intervals do not overlap.
- Novelty: highest mean = D_random (0.251); lead over A_fly_plastic = +0.086; intervals do not overlap.

**Headline (held-out only)**  
On the held-out quality-diversity score the highest-scoring arm is C_genetic (0.383) ahead of B_evolved_ann (0.361). Paired difference +0.022 (95% bootstrap CI +0.015 to +0.030, n=5). The CI excludes zero, but with this few seeds this is preliminary and is not declared a winner.

**Did the biologically inspired architecture add measurable value?**  
- Mushroom-body-inspired controller with plasticity vs an evolved ANN with the same parameter budget and evolutionary engine: held-out QD diff -0.168 [-0.185, -0.151] - CI excludes zero (preliminary).
- Mushroom-body-inspired controller with plasticity vs the same circuit without plasticity: held-out QD diff -0.001 [-0.022, +0.020] - CI includes zero: no measurable difference.
- Mushroom-body-inspired controller with plasticity vs the same circuit with shuffled PN->KC wiring: held-out QD diff +0.002 [-0.023, +0.031] - CI includes zero: no measurable difference.
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

- `HYP-CGEN-s0-a27704-g291` municipal procurement officers / hard-to-compare pricing / curated public-data digest / one-off paid report (held-out fixed score 0.445, EUR 0 est.)
- `HYP-CGEN-s4-a23720-g249` municipal procurement officers / hard-to-compare pricing / template + workflow kit / one-off paid report (held-out fixed score 0.437, EUR 2 est.)
- `HYP-BEVO-s4-a5502-g78` freelance translators / error-prone document handling / alerting / monitoring service / usage-based fee (held-out fixed score 0.430, EUR 14 est.)
- `HYP-AFLY-s1-a13083-g188` municipal procurement officers / hard-to-compare pricing / automated checker / validator / monthly subscription (held-out fixed score 0.428, EUR 3 est.)
- `HYP-BEVO-s0-a14626-g209` municipal procurement officers / error-prone document handling / template + workflow kit / usage-based fee (held-out fixed score 0.426, EUR 11 est.)
