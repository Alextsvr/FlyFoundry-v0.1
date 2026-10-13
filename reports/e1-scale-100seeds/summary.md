# FlyFoundry run summary

- **Status:** completed  |  **Run:** `20261013T072023Z-66bb21`
- **Generations:** 0 -> 60 (cumulative 60)
- **Fitness evaluations:** 3,600,000 total, 360,000 this run (100 agents x 6 arms x 100 seeds)
- **Resources this run:** CPU 59.494 s, wall 59.502 s, peak RSS 170.6 MB
- **Code revision:** `d9e6719f067d`  |  **Checkpoint:** v1 (sha256 `082072c8d2b0`)
- **Checkpoint recovery problems:** none
- **Resume test:** {"note": "merged from 10 shards", "shards": [{"version": 1, "sha256": "ce784cc85a43b5078d02665a032b2b5b2f335c5984f9a3d94de4b31b9e6ead06", "file": "ckpt_000001.json.gz", "bytes": 25486387, "problems": []}, {"version": 1, "sha256": "2b858acf1e6e45a0a8047cc2b38fc70e8ce2491d78ff71da0a03feba2aefebd9", "file": "ckpt_000001.json.gz", "bytes": 25447945, "problems": []}, {"version": 1, "sha256": "164cc8d13be5bbb7cf9aecbac13484ea8b849cb8fbfbfdbfcf45ebe3aa5ebd66", "file": "ckpt_000001.json.gz", "bytes": 25591601, "problems": []}, {"version": 1, "sha256": "1d7bdfa41ea9c6289888882f5f271c9a72b7f617759a8588efff8a352bb86963", "file": "ckpt_000001.json.gz", "bytes": 25543639, "problems": []}, {"version": 1, "sha256": "4d81cc1617f1416ea18173c2750c1da49f41a7455bdad01e7dad05987c54aad7", "file": "ckpt_000001.json.gz", "bytes": 25526129, "problems": []}, {"version": 1, "sha256": "8aaf794c40073b4bb64e7e27b6c43a717ba2fff9b07a164a49a5af0fd9721911", "file": "ckpt_000001.json.gz", "bytes": 25560161, "problems": []}, {"version": 1, "sha256": "836c3eec7744244e0fc59d00b8488a91b3a9e3624cd525aedfad11e0f13b8301", "file": "ckpt_000001.json.gz", "bytes": 25336907, "problems": []}, {"version": 1, "sha256": "1d51d3709522d6e1e1ec18232e79a73322c1be323e8fa02c100e72b9ba384352", "file": "ckpt_000001.json.gz", "bytes": 25721746, "problems": []}, {"version": 1, "sha256": "0537eb6b9f8c8dbf484e450272f8050f7c94d7e500f47280e89571bd2517f45a", "file": "ckpt_000001.json.gz", "bytes": 25376410, "problems": []}, {"version": 1, "sha256": "c43793e6c4131114e4f592e10e91b4175718ffd19c6d6d959ca7e7847d0772f2", "file": "ckpt_000001.json.gz", "bytes": 25419980, "problems": []}], "reload_roundtrip_identical": true}
- **Arm E (LLM baseline):** NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)

| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |
|---|---|---|---|---|---|---|
| A fly-inspired + plasticity | 0.196 [0.191, 0.202] | 0.222 | 0.401 | 2.0 | 0.0327 | 0.216 |
| A fly-inspired, no plasticity | 0.197 [0.193, 0.201] | 0.224 | 0.405 | 2.0 | 0.0329 | 0.226 |
| A fly-inspired, shuffled wiring | 0.196 [0.191, 0.201] | 0.222 | 0.403 | 2.1 | 0.0327 | 0.217 |
| B evolved ANN | 0.345 [0.343, 0.348] | 0.450 | 0.521 | 2.7 | 0.0576 | 0.399 |
| C genetic algorithm | 0.364 [0.360, 0.367] | 0.460 | 0.479 | 2.7 | 0.0606 | 0.393 |
| D random search | 0.325 [0.323, 0.328] | 0.321 | 0.215 | 0.1 | 0.0542 | 2.318 |

## Conclusions (conservative, auto-generated)

**Scope**  
Results cover 60 generations x 100 agents per arm and 100 paired seeds on a SYNTHETIC benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). Seed count is sufficient for formal comparisons.

**Best arm per measured metric (mean of last 5 generations, across seeds)**  
- Held-out quality-diversity score: highest mean = C_genetic (0.364); lead over B_evolved_ann = +0.018; intervals do not overlap.
- Held-out best candidate score: highest mean = C_genetic (0.460); lead over B_evolved_ann = +0.010; intervals do not overlap.
- Held-out peak discovery rate: highest mean = C_genetic (0.153); lead over B_evolved_ann = +0.045; intervals do not overlap.
- Train best-of-generation fitness: highest mean = B_evolved_ann (0.521); lead over C_genetic = +0.041; intervals do not overlap [training metric - not a basis for declaring a winner].
- Train mean fitness: highest mean = B_evolved_ann (0.251); lead over C_genetic = +0.023; intervals do not overlap [training metric - not a basis for declaring a winner].
- Distinct real peaks discovered (train): highest mean = B_evolved_ann (2.714); lead over C_genetic = +0.046; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Viable niches (archive): highest mean = A_fly_noplast (53.366); lead over A_fly_shuffled = +0.568; bootstrap intervals overlap (no clear separation) [training metric - not a basis for declaring a winner].
- Population diversity: highest mean = D_random (0.402); lead over A_fly_noplast = +0.105; intervals do not overlap.
- Novelty: highest mean = D_random (0.251); lead over A_fly_plastic = +0.087; intervals do not overlap.

**Headline (held-out only)**  
On the held-out quality-diversity score the highest-scoring arm is C_genetic (0.364) ahead of B_evolved_ann (0.345). Paired difference +0.018 (95% bootstrap CI +0.014 to +0.022, n=100). The CI excludes zero.

**Did the biologically inspired architecture add measurable value?**  
- Mushroom-body-inspired controller with plasticity vs an evolved ANN with the same parameter budget and evolutionary engine: held-out QD diff -0.149 [-0.155, -0.144] - CI excludes zero (preliminary).
- Mushroom-body-inspired controller with plasticity vs the same circuit without plasticity: held-out QD diff -0.001 [-0.007, +0.005] - CI includes zero: no measurable difference.
- Mushroom-body-inspired controller with plasticity vs the same circuit with shuffled PN->KC wiring: held-out QD diff +0.001 [-0.007, +0.008] - CI includes zero: no measurable difference.
- Even a positive difference would show value of a sparse, plastic architecture on THIS synthetic task, not of real Drosophila connectivity (none is used).

**Uncertainty**  
Intervals are percentile bootstrap CIs over 100 seeds (2000 resamples); a single world (fixed hidden landscape) is used, so results do not generalise across worlds. Metrics are averaged over the last 5 generations to reduce evaluation noise.

**What remains unverified**  
- Any real-world validity: no public evidence dataset is wired in yet; all hypotheses are synthetic-tier.
- Arm E (LLM baseline): NOT RUN - NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)
- Biological fidelity: no FlyWire/hemibrain connectivity is used; the controller is a documented mushroom-body-inspired model.
- Robustness across different hidden worlds and benchmark difficulty levels.
- Seeds: n=100 meets the configured minimum.

**Suggested next experiments**  
- Add a second, non-stationary benchmark world (peaks drift over generations) where lifetime plasticity should matter; the current stationary task gives plasticity little to exploit.
- Wire in one public, legitimately accessible evidence dataset (evidence-tier fitness) with recorded provenance.
- Run arm E when a free LLM endpoint is available, at a matched evaluation budget.

## Top hypotheses (synthetic benchmark only; not real-world evidence)

- `HYP-BEVO-s6-a3325-g47` municipal procurement officers / error-prone document handling / alerting / monitoring service / usage-based fee (held-out fixed score 0.454, EUR 21 est.)
- `HYP-BEVO-s11-a2416-g34` municipal procurement officers / error-prone document handling / template + workflow kit / usage-based fee (held-out fixed score 0.437, EUR 17 est.)
- `HYP-BEVO-s97-a4188-g59` municipal procurement officers / poor demand forecasting / alerting / monitoring service / usage-based fee (held-out fixed score 0.430, EUR 10 est.)
- `HYP-AFLY-s6-a1728-g24` indie game studios / error-prone document handling / automated checker / validator / monthly subscription (held-out fixed score 0.426, EUR 17 est.)
- `HYP-BEVO-s74-a3528-g49` municipal procurement officers / hard-to-compare pricing / alerting / monitoring service / marketplace commission (held-out fixed score 0.426, EUR 10 est.)
