# Results log

> **Status: verified on GitHub Actions** (repository `Alextsvr/FlyFoundry-v0.1`, public).
> The sections below the GitHub block were produced locally with the same code and `configs/nightly.json`.

## GitHub Actions runs (verified via the GitHub API, 2026-10-12)

| Run | Result | Notes |
|---|---|---|
| [38224993495](https://github.com/Alextsvr/FlyFoundry-v0.1/actions/runs/38224993495) `experiment` (commit 5a318a6) | success, 34 s | fresh start: generations 0→20, 60,000 evaluations, checkpoint v1 (11.3 MB) written to branch `flyfoundry-state` |
| [38225423603](https://github.com/Alextsvr/FlyFoundry-v0.1/actions/runs/38225423603) `experiment` (commit da24c99) | success, 37 s | independent run, **resumed from v1**: generations 20→40, 120,000 evaluations cumulative, checkpoint v2 |
| ci on da24c99 | success | tests + smoke experiment |

Earlier failures, for the record: runs 38224844942 / 38224907079 failed (state scripts lost their exec bit when the project was unpacked on Windows; fixed by calling them via `bash`);
ci on 5a318a6 failed (a test forbade `https://` in the report, but on Actions the report legitimately links to the run; fixed by cleaning CI env vars in tests).

First GitHub run (20 generations, 5 seeds, mean of last 5 generations): held-out QD — C genetic 0.353, D random 0.298, B evolved ANN 0.293, A fly-inspired 0.186–0.200.
CPU 10.8 s, peak RSS 89.5 MB. Same qualitative picture as the longer local run below; n = 5 seeds, no significance claims.
Nightly schedule (01:30 Europe/Riga) is configured; `experiment` workflow state is `active`; see the schedule observations below.

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


## Schedule observations (GitHub, verified via the public API)

- 2026-10-13: two `schedule` runs fired (ids 38340234730 at 03:07 UTC and 38343014139 at 03:42 UTC), roughly 4.5 h after the
  configured 22:30/23:30 UTC crons. Both finished green, but the schedule guard (window 01:00-03:59 Riga) skipped the experiment
  because the runs started at about 06:07 / 06:42 Riga time. No new checkpoint and no new row in `runs.csv` were produced.
- Conclusion: the schedule trigger works, but the first nightly experiment did NOT run. Cause: guard window too narrow for
  GitHub's real start-time delay (design flaw, not a bug in the guard logic).
- Fix (this commit): guard allows one run per Riga calendar date at any hour (`--window 0-23`). Verification of a full
  scheduled experiment is still pending until the next scheduled run after this fix is pushed.


## E1 scale test (v0.2) - verified on GitHub Actions

Run: https://github.com/Alextsvr/FlyFoundry-v0.1/actions/runs/38361995321 (workflow `swarm`, commit `d9e6719`),
10 shard jobs in parallel (<= 10 cap) + merge, about 17 min of runner time in total. 100 paired seeds, 6 arms, 60 generations,
100 agents per population, 3,600,000 evaluations. Report files: `reports/e1-scale-100seeds/` (history is gzipped).
Metric: held-out QD, mean of the last 5 generations per seed; paired percentile bootstrap, 2000 resamples (verified independently
from `history.csv`: same numbers). Decision rules were fixed in `docs/V0_2_SPEC.md` before the run.

| Pre-registered hypothesis | Paired difference [95% CI] | Verdict |
|---|---|---|
| H1: fly+plasticity >= evolved ANN | -0.149 [-0.155, -0.143] | **REFUTED** (upper bound < 0) |
| H2: plasticity matters (plastic - noplast) | -0.001 [-0.007, +0.006] | **INCONCLUSIVE** (CI contains 0) |
| H3: wiring matters (plastic - shuffled) | +0.001 [-0.006, +0.008] | **INCONCLUSIVE** (CI contains 0) |
| H4: genetic algorithm > random search | +0.038 [+0.034, +0.043] | **SUPPORTED** |

Reading: the prior expectation stated before the run (H1 refuted or inconclusive) held. Neither H2 nor H3 is "supported" under the
rule, and the intervals are narrow (about +-0.007), but no equivalence margin was pre-registered, so we do not claim the effects are
zero, only that none was detected. Scope: one fixed synthetic world, stationary task; this says nothing about real flies, real markets
or revenue. Arm E (LLM) was NOT RUN. The mushroom-body-inspired controller underperforming here may reflect this implementation and
task rather than the biological idea.

## E4 — non-stationary world (drift_amp 0.15), 100 paired seeds, metric track_qd gens 41-60

Run ids: medium 38363756689, slow 38364548452, fast 38365434438. Raw verdicts: `reports/e4-summaries/<condition>/`.

| Condition | E4-H1 fly-plastic − ANN | E4-H2 plasticity | E4-H3 PN→KC wiring | E4-H4 GA − random |
|---|---|---|---|---|
| slow (T=120) | −0.147 REFUTED | +0.001 INCONCLUSIVE | +0.002 INCONCLUSIVE | +0.112 SUPPORTED |
| medium (T=40, primary) | −0.136 REFUTED | +0.001 INCONCLUSIVE | +0.002 INCONCLUSIVE | +0.121 SUPPORTED |
| fast (T=15) | −0.132 REFUTED | +0.004 INCONCLUSIVE | +0.000 INCONCLUSIVE | +0.125 SUPPORTED |

Arm means (fast): fly ≈ 0.183–0.188, random 0.185, GA 0.310, ANN 0.319.

Conclusion (per the pre-registered stopping rule): the fly-inspired controller does not beat the evolved ANN in any drift speed, and neither plasticity nor the wiring shows a detectable effect; fly arms sit at random-search level. The primary claim (E4-H2, medium) is INCONCLUSIVE. For this synthetic task type the fly arm is a dead end; v0.2 continues with C_genetic and B_evolved_ann. Why the fly arm generalizes poorly is an untested hypothesis.

## E2 — island model vs single pool (run 38368713798, 100 paired repeats, 60 generations, 60 000 evaluations per condition)

Protocol frozen in docs/V0_2_SPEC.md before the run. Metric `final_qd`: merged archive judged once, noise-free, on the `final` contexts. Raw verdicts: `reports/e2-summaries/`.

| Arm | islands + migration | islands, no migration | single pool (10x population) |
|---|---|---|---|
| C_genetic | 0.406 | 0.405 | 0.391 |
| B_evolved_ann | 0.367 | 0.368 | 0.370 |

- C_genetic, E2-H1 (primary): +0.0153 [+0.0117, +0.0192] SUPPORTED. The benefit comes from the merge step (E2-H3 +0.0139, SUPPORTED), not from migration (E2-H2 +0.0014, INCONCLUSIVE).
- B_evolved_ann, E2-H1 (primary): −0.0038 [−0.0069, −0.0009] REFUTED (islands slightly worse than one pool).
- Winner's curse: no evidence of over-selection in either arm (E2-H4 INCONCLUSIVE); gaps are +0.008…+0.019 in every condition, including the single pool.
- Caveat (pre-registered): islands use `select` evaluations that the single pool cannot use, so the GA gain is "islands + select-based merge", and it is small (about 4% of final QD). Absolute level: GA 0.41 vs ANN 0.37 on `final` contexts.

## E3 — plumbing backtest on H01-H12 (NOT validation), 30 repeats

Pre-registered criteria (docs/V0_2_SPEC.md): **PASS** — 100% of repeats met all three (Spearman 0.965 / 0.930 on the two final weight sets, top-2 = H07+H01, last = H03). Details: `reports/e3/`.

**But the test is almost vacuous, and this must be read together with the PASS.** Random criterion weights pass the same criteria in 95.5% of draws (mean Spearman 0.92 / 0.93); plain equal weights already give 0.935 / 0.963 with the right top-2 and last. The five weight sets all rank the 12 hypotheses nearly the same way, so almost any positive weighting reproduces the ranking. The PASS therefore shows only that the machinery runs end to end (data -> plugin -> unchanged GA arm -> train/final split -> verdict). It carries no evidence that the swarm can find good businesses, and the criteria are too weak to catch a broken search. A discriminating E3 would need a hidden ranking that random weights cannot reproduce (e.g. leave-one-hypothesis-out, or real outcome data in Phase 1).

## Phase 1 calibration (run 38371302136, 2026-10-13): automated layer F vs the manual H01-H12 verdicts

Frozen queries (commit 819c55f, before the first probe). 49 probe facts, all `ok` (HN 25, GitHub 12, Stack Exchange 12). Raw data: `data/probes/run1_2026-10-13.jsonl`, summary: `reports/phase1-summaries/`.

**Verdict: FAIL.** Spearman rho = -0.178 (95% CI -0.77..+0.44), one-sided permutation p = 0.71; pass needed rho >= 0.5 and p <= 0.05. Negative control (shuffled probe results) gave rho = +0.447 (p = 0.07): with n = 12 pure noise alone can produce correlations of that size, so the test could only have been passed by a strong signal, and there was none.

Notable: the probes put H03 (all three manual tracks negative) first and H05, H08, H10 last. The automated layer does not reproduce the manual research; it measures how much the tech-audience sources mention a topic and how many open-source repos exist, which is not what the manual verdicts weighed (willingness to pay, competition, legal blockers).

Consequence under the pre-registered stop rule (docs/PHASE1_SPEC.md section 6): the probes are NOT used for ranking. Phase 1 ranks from layer C (curated, cited features and gates) alone and reports that automation added no information. Low power (n = 12) means "not shown", not "proven useless". Changing queries or the score after seeing this would be a new, separately pre-registered attempt (v2) and must be counted as such.

## Phase 1 layer C: first idea ranking (2026-10-15) — curated priors, NOT evidence

Idea space: `data/taxonomy_v4.json` (21 customers x 20 problems x 10 solutions x 7 revenue mechanisms x 4 channels = 117 600 tuples after removing 'own existing network' because the owner has no known audience) plus 19 named seeds (H01-H12 researched; N1-N7 unresearched priors in `data/seeds_new.csv`). Fitness = weighted mean of the 13 synthesis criteria under the five weight sets (the layer-C plugin `flyfoundry/phase1/ideaspace.py`); hard gates and forbidden pairs remove 5 860 tuples. Output: `reports/phase1-ideas/ideas_rank.md`.

What the swarm did, honestly: 10 islands x 100 x 60 generations recovered only 19% of the exact top-50 (worst 12%) vs 37% for random sampling with the same budget (the budget is already half the space). The space is small enough to enumerate, so the exhaustive ranking is the authoritative one; the swarm adds no ideas (it can only recombine the components I wrote) and found less of the top than random sampling, because the top is a plateau of near-ties that the GA's diversity mechanisms spread over other niches. In this task the swarm is not the useful part; the useful part is the curated table and the research that will test it.

What the ranking shows, and its limits: the top generated combinations are dominated by my own component priors (customers I scored as easy to reach, 'monthly subscription', 'partner referral'); averaged components are less extreme than the hand-scored seeds, so seeds and generated tuples are not on one scale. Inside the owner's domain (payments/reconciliation/accounting) the best combinations are reconciliation and report/validation tools for accountants and bookkeeping firms. Among the seeds, H07 (0.717) and H01 (0.645) stay on top, then the unresearched priors N7 (niche tender alerts) and N1 (PSP fee audit). Nothing here is evidence; the next step is a research round that checks each top candidate against sources and replaces priors by cited values.
