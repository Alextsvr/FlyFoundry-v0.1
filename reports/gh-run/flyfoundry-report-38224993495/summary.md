# FlyFoundry run summary

- **Status:** completed  |  **Run:** `20261012T084034Z-add290`
- **Generations:** 0 -> 20 (cumulative 20)
- **Fitness evaluations:** 60,000 total, 60,000 this run (100 agents x 6 arms x 5 seeds)
- **Resources this run:** CPU 10.77 s, wall 10.772 s, peak RSS 89.5 MB
- **Code revision:** `5a318a64909f`  |  **Checkpoint:** v1 (sha256 `9ac3cbee3be0`)
- **Checkpoint recovery problems:** none
- **Resume test:** {"loaded_from_version": null, "gens_before": 0, "saved_version": 1, "reload_roundtrip_identical": true, "generation_after_reload": 20}
- **Arm E (LLM baseline):** NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |
|---|---|---|---|---|---|---|
| A fly-inspired + plasticity | 0.188 [0.181, 0.196] | 0.206 | 0.341 | 0.1 | 0.0942 | 0.682 |
| A fly-inspired, no plasticity | 0.200 [0.186, 0.217] | 0.219 | 0.320 | 0.4 | 0.0998 | 0.771 |
| A fly-inspired, shuffled wiring | 0.186 [0.170, 0.203] | 0.212 | 0.350 | 0.6 | 0.0930 | 0.687 |
| B evolved ANN | 0.293 [0.274, 0.313] | 0.325 | 0.407 | 1.1 | 0.1464 | 1.138 |
| C genetic algorithm | 0.353 [0.327, 0.379] | 0.416 | 0.458 | 2.4 | 0.1763 | 1.375 |
| D random search | 0.298 [0.284, 0.313] | 0.299 | 0.233 | 0.0 | 0.1491 | 6.660 |

## Conclusions (conservative, auto-generated)

**Scope**  
Results cover 20 generations x 100 agents per arm and 5 paired seeds on a SYNTHETIC benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). With n=5 < 10 seeds, no statistical-significance claim is made; intervals are indicative only.

**Best arm per measured metric (mean of last 5 generations, across seeds)**  
- Held-out quality-diversity score: highest mean = C_genetic (0.353); lead over D_random = +0.054; intervals do not overlap.
- Held-out best candidate score: highest mean = C_genetic (0.416); lead over B_evolved_ann = +0.091; intervals do not overlap.
- Held-out peak discovery rate: highest mean = C_genetic (0.071); lead over B_evolved_ann = +0.063; intervals do not overlap.
- Train best-of-generation fitness: highest mean = C_genetic (0.458); lead over B_evolved_ann = +0.052; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Train mean fitness: highest mean = C_genetic (0.206); lead over B_evolved_ann = +0.073; intervals do not overlap [training metric - not a basis for declaring a winner].
- Distinct real peaks discovered (train): highest mean = C_genetic (2.400); lead over B_evolved_ann = +1.320; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Viable niches (archive): highest mean = C_genetic (36.920); lead over A_fly_shuffled = +1.720; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Population diversity: highest mean = D_random (0.401); lead over A_fly_noplast = +0.100; intervals do not overlap.
- Novelty: highest mean = D_random (0.250); lead over A_fly_noplast = +0.076; intervals do not overlap.

**Headline (held-out only)**  
On the held-out quality-diversity score the highest-scoring arm is C_genetic (0.353) ahead of D_random (0.298). Paired difference +0.054 (95% bootstrap CI +0.020 to +0.079, n=5). The CI excludes zero, but with this few seeds this is preliminary and is not declared a winner.

**Did the biologically inspired architecture add measurable value?**  
- Mushroom-body-inspired controller with plasticity vs an evolved ANN with the same parameter budget and evolutionary engine: held-out QD diff -0.104 [-0.131, -0.078] - CI excludes zero (preliminary).
- Mushroom-body-inspired controller with plasticity vs the same circuit without plasticity: held-out QD diff -0.011 [-0.036, +0.010] - CI includes zero: no measurable difference.
- Mushroom-body-inspired controller with plasticity vs the same circuit with shuffled PN->KC wiring: held-out QD diff +0.002 [-0.022, +0.024] - CI includes zero: no measurable difference.
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

- `HYP-AFLY-s3-a1247-g17` indie game studios / hard-to-compare pricing / curated public-data digest / monthly subscription (held-out fixed score 0.404, EUR 5 est.)
- `HYP-BEVO-s0-a897-g13` municipal procurement officers / hard-to-compare pricing / curated public-data digest / usage-based fee (held-out fixed score 0.397, EUR 28 est.)
- `HYP-BEVO-s2-a1112-g15` indie game studios / error-prone document handling / alerting / monitoring service / marketplace commission (held-out fixed score 0.392, EUR 17 est.)
- `HYP-CGEN-s1-a1830-g19` municipal procurement officers / slow support triage / automated checker / validator / one-off paid report (held-out fixed score 0.389, EUR 4 est.)
- `HYP-CGEN-s0-a1562-g16` municipal procurement officers / error-prone document handling / template + workflow kit / monthly subscription (held-out fixed score 0.384, EUR 21 est.)
