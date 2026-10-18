# FlyFoundry run summary

- **Status:** completed  |  **Run:** `20261018T001323Z-aee335`
- **Generations:** 160 -> 180 (cumulative 180)
- **Fitness evaluations:** 540,000 total, 60,000 this run (100 agents x 6 arms x 5 seeds)
- **Resources this run:** CPU 13.911 s, wall 13.913 s, peak RSS 164.3 MB
- **Code revision:** `b4d4e5e213a5`  |  **Checkpoint:** v9 (sha256 `c1a879a91924`)
- **Checkpoint recovery problems:** none
- **Resume test:** {"loaded_from_version": 8, "gens_before": 160, "saved_version": 9, "reload_roundtrip_identical": true, "generation_after_reload": 180}
- **Arm E (LLM baseline):** NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |
|---|---|---|---|---|---|---|
| A fly-inspired + plasticity | 0.200 [0.188, 0.213] | 0.225 | 0.428 | 4.2 | 0.0111 | 0.076 |
| A fly-inspired, no plasticity | 0.196 [0.160, 0.226] | 0.225 | 0.439 | 4.0 | 0.0109 | 0.079 |
| A fly-inspired, shuffled wiring | 0.191 [0.171, 0.212] | 0.220 | 0.438 | 3.8 | 0.0106 | 0.074 |
| B evolved ANN | 0.359 [0.353, 0.366] | 0.479 | 0.520 | 3.2 | 0.0200 | 0.146 |
| C genetic algorithm | 0.367 [0.349, 0.384] | 0.479 | 0.478 | 3.2 | 0.0204 | 0.136 |
| D random search | 0.341 [0.335, 0.349] | 0.324 | 0.217 | 0.4 | 0.0189 | 0.841 |

## Conclusions (conservative, auto-generated)

**Scope**  
Results cover 180 generations x 100 agents per arm and 5 paired seeds on a SYNTHETIC benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). With n=5 < 10 seeds, no statistical-significance claim is made; intervals are indicative only.

**Best arm per measured metric (mean of last 5 generations, across seeds)**  
- Held-out quality-diversity score: highest mean = C_genetic (0.367); lead over B_evolved_ann = +0.007; bootstrap intervals overlap (no clear separation).
- Held-out best candidate score: highest mean = B_evolved_ann (0.479); lead over C_genetic = +0.001; bootstrap intervals overlap (no clear separation).
- Held-out peak discovery rate: highest mean = C_genetic (0.169); lead over B_evolved_ann = +0.021; bootstrap intervals overlap (no clear separation).
- Train best-of-generation fitness: highest mean = B_evolved_ann (0.520); lead over C_genetic = +0.043; intervals do not overlap [training metric - not a basis for declaring a winner].
- Train mean fitness: highest mean = B_evolved_ann (0.265); lead over C_genetic = +0.034; intervals do not overlap [training metric - not a basis for declaring a winner].
- Distinct real peaks discovered (train): highest mean = A_fly_plastic (4.200); lead over A_fly_noplast = +0.200; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Viable niches (archive): highest mean = A_fly_plastic (60.600); lead over A_fly_noplast = +1.360; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Population diversity: highest mean = D_random (0.402); lead over A_fly_noplast = +0.099; intervals do not overlap.
- Novelty: highest mean = D_random (0.251); lead over A_fly_plastic = +0.084; intervals do not overlap.

**Headline (held-out only)**  
On the held-out quality-diversity score the highest-scoring arm is C_genetic (0.367) ahead of B_evolved_ann (0.359). Paired difference +0.007 (95% bootstrap CI -0.006 to +0.021, n=5). The CI includes zero, but with this few seeds this is preliminary and is not declared a winner.

**Did the biologically inspired architecture add measurable value?**  
- Mushroom-body-inspired controller with plasticity vs an evolved ANN with the same parameter budget and evolutionary engine: held-out QD diff -0.159 [-0.170, -0.145] - CI excludes zero (preliminary).
- Mushroom-body-inspired controller with plasticity vs the same circuit without plasticity: held-out QD diff +0.004 [-0.017, +0.026] - CI includes zero: no measurable difference.
- Mushroom-body-inspired controller with plasticity vs the same circuit with shuffled PN->KC wiring: held-out QD diff +0.009 [-0.017, +0.037] - CI includes zero: no measurable difference.
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

- `HYP-BEVO-s4-a5502-g78` freelance translators / error-prone document handling / alerting / monitoring service / usage-based fee (held-out fixed score 0.430, EUR 14 est.)
- `HYP-BEVO-s2-a5041-g71` indie game studios / error-prone document handling / template + workflow kit / usage-based fee (held-out fixed score 0.425, EUR 8 est.)
- `HYP-BEVO-s2-a8798-g127` municipal procurement officers / error-prone document handling / template + workflow kit / usage-based fee (held-out fixed score 0.417, EUR 5 est.)
- `HYP-BEVO-s0-a9559-g136` indie game studios / poor demand forecasting / alerting / monitoring service / marketplace commission (held-out fixed score 0.414, EUR 11 est.)
- `HYP-CGEN-s1-a8025-g84` indie game studios / error-prone document handling / alerting / monitoring service / marketplace commission (held-out fixed score 0.412, EUR 1 est.)
