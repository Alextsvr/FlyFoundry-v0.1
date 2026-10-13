# FlyFoundry v0.2 — Specification (pre-registered)

Status: DRAFT. Nothing below is a result.
Implementation log (updated as pieces land):
- 2026-10-13: sharding step implemented (section 3, items 1-2): `--shard i/N`, `flyfoundry merge`, `swarm.yml`
  (manual, kill switch `SWARM_ENABLED`, <= 10 parallel jobs), 16 new tests (merged shards == unsharded run, state-for-state).
  Local rehearsal: 100 seeds / 10 shards / 3 generations ran in ~45 s of shard time + 35 s merge.
  Sizing finding: one 10-seed shard checkpoint is ~24 MB and a merged 100-seed checkpoint ~235 MB, which exceeds GitHub's
  100 MB per-file push limit, so the swarm does NOT persist the merged checkpoint in the state branch (shard artifacts
  live 1 day; the report is the product). - 2026-10-13: E1 executed on GitHub Actions (run 38361995321). H1 REFUTED, H2 and H3 INCONCLUSIVE, H4 SUPPORTED (see docs/RESULTS.md).
- 2026-10-13: E4 pre-registered (section 4) and implemented: drifting world (`drift_amp`, `drift_period`), tracking metrics,
  `configs/e4_drift_*.json`, `scripts/analyze_e4.py`, `swarm.yml` config input. Regression: with `drift_amp = 0` a tiny run is
  state-identical to the pre-change code and the world fingerprint equals the E1 one. 41 tests pass. A 6-seed pipeline rehearsal
  was run only to test the plumbing; its numbers are not used for any decision.
  Done in code (2026-10-13): islands, migration, three-way split, final tournament (E2 protocol frozen, run pending). Fitness plugin and E3 backtest implemented. Not yet done: shard kill/resume test on Actions, first scheduled nightly run, Phase 1 spec.
Language note: repo docs are English; the project owner discusses in Russian.

## 0. Purpose and phases

- **Phase 0 (this spec): build the swarm.** A reproducible, resumable, budget-capped
  population of many independent evolutionary runs ("islands") executed as parallel
  GitHub Actions jobs, with a pluggable fitness interface.
- **Phase 1 (later, separate spec): task the swarm** with producing a *ranked list of
  business models* from an idea space wider than the original project. Phase 1 starts only
  after Phase 0 exit criteria are met.

Non-goals of v0.2: real-world actions (outreach, payments, publishing), a connectome,
any claim that a winner is a proven income source.

## 1. Terminology (for the project owner)

- workflow run = one launch of the whole pipeline; job = one task inside it, on its own
  virtual machine (runner); matrix = one job definition fanned out into many parallel jobs;
  shard = the slice of seeds/islands one job computes; island = one independent evolving
  population; swarm = all islands plus the merge/tournament step.

## 2. Resource and policy envelope (hard limits)

- Single GitHub account, single repository. No multiplication of accounts to raise limits
  (GitHub ToS: one free account per person).
- Public repo => standard runners free. Documented limits used: 20 concurrent jobs (Free),
  256 jobs per matrix, 6 h per job, 500 MB artifact storage, GITHUB_TOKEN 1000 API req/h.
- v0.2 self-imposed caps: `max-parallel <= 10`; at most ONE large matrix run per 24 h;
  total runner time per day <= 120 job-minutes unless the owner raises it; artifacts
  retention 7 days; reports small (<20 MB). Compute must stay tied to the project's own
  test/report cycle (Actions terms forbid unrelated compute use, mining, CDN/serverless use).
- Budget: EUR 0. No paid API, no rented server.
- Kill switch: repository variable `SWARM_ENABLED` must equal `true`; every workflow checks
  it first.

## 3. Architecture changes vs v0.1

1. **Sharded execution.** `flyfoundry run --shard i/N` computes only seeds/islands of shard i.
   Seed streams stay index-based, so results do not depend on N (tested: N=1 == N=10).
2. **Merge job.** One job downloads shard artifacts, verifies checksums, merges histories,
   runs the final tournament, writes the report.
3. **Three-way context split** (new): `train` (noisy, used by arms), `select` (used by
   islands for migration/survivor decisions), `final` (touched ONLY by the final tournament).
   A static test must prove that no island code path can read `final`.
4. **Island model.** K islands per arm, ring migration every M generations (elites only).
5. **Final tournament.** Island champions meet on `final` contexts, noise-free,
   round-robin by held-out score; ties broken by archive coverage. Winner's score is
   reported with a bootstrap CI over contexts AND is compared to a no-island baseline with
   an identical evaluation budget (otherwise "tournament" proves nothing).
6. **Fitness plugin interface** `Fitness.evaluate(candidates, contexts) -> scores`
   with registered implementations: `synthetic_landscape` (v0.1) and `tabular_backtest`
   (section 5). Swapping fitness must not touch the swarm code.
7. **State and resume.** Reuse v0.1 checkpoint format; per-shard checkpoints; the merge job
   refuses to merge shards from different config hashes or code revisions.
8. **Guard rails.** Action allowlist file `swarm/allowed_actions.json`
   (v0.2 contents: read-only data access, write to own branch/artifacts); append-only audit
   log `audit.jsonl` in the state branch; any non-allowlisted action aborts the run.

## 4. Pre-registered experiments

All thresholds below are fixed BEFORE the first v0.2 run. Changing them afterwards requires
a dated amendment section; results must report the original thresholds.

### E1 — Scale test (does more seeds change the v0.1 picture?)
- Config: v0.1 nightly config, 100 seeds, 6 arms, 60 generations, 10 shards of 10 seeds.
- Metric: heldout_qd (lenient). Paired differences per seed index.
- H1: A_fly_plastic >= B_evolved_ann. SUPPORTED if the 95% percentile-bootstrap CI of the
  paired difference (A - B) has lower bound > 0; REFUTED if the upper bound < 0;
  otherwise INCONCLUSIVE.
- H2 (plasticity matters): A_fly_plastic - A_fly_noplast, same decision rule.
- H3 (wiring matters): A_fly_plastic - A_fly_shuffled, same decision rule.
- H4 (baselines): C_genetic - D_random, same rule (sanity check; expected SUPPORTED).
- Prior expectation (stated now, from v0.1 n=5): H1 REFUTED or INCONCLUSIVE.
  Reporting "REFUTED" is a valid, useful outcome.
- Significance statements are allowed because n=100 >= 10 seeds.

### E2 — Island model (does structure beat the same compute in one pool?)
- Compare, at identical total evaluations: (a) 10 islands x pop P with migration + final
  tournament on `final`; (b) one population of size 10P without islands, evaluated on
  the same `final` contexts. Arms: the best two arms from E1 plus C_genetic.
- SUPPORTED if (a) beats (b) on `final` with paired-bootstrap CI lower bound > 0 over
  >= 30 repeated swarm runs; otherwise report as not supported.
- Winner's-curse check: the champion's `select` score minus its `final` score is reported
  (expected > 0); a swarm whose gap is much larger than the no-island baseline's gap is
  flagged as over-selecting.

#### E2 — frozen protocol (written 2026-10-13, BEFORE the official run)

Disclosure: before freezing, the code was smoke-tested on 2 repeats at 60 generations and 4 repeats at 20 generations
(plumbing only; the numbers were glanced at and are not used for any decision). The official run is a fresh run of the
frozen code below with 100 repeats.

- **Why this experiment.** E4 stopping rule: the fly-inspired arms are dropped; E2 uses `C_genetic` and `B_evolved_ann`.
- **World.** Stationary E1 world (`configs/swarm_e1.json`, fingerprint unchanged). Two NEW context sets, `select` and
  `final` (16 contexts each, own RNG stream, disjoint from `train` and `held-out`), do not change the fingerprint.
- **Conditions per repeat and arm** (all with 60 generations and exactly 60 000 training evaluations in total):
  `islands_mig` = 10 islands x pop 100, ring migration every 10 generations (not after the last one), the 3 best archive
  elites (ranked on `select`) of each island replace the 3 newest population slots of the next island;
  `islands_nomig` = the same 10 islands (same seeds) without migration;
  `single_pool` = one population of 1000 (survivors 300, elites 50: counts scaled with the population).
- **Merge and tournament.** The swarm's output is a merged archive: per niche the island elite with the best `select` score
  (noise-free mean net score over the 16 `select` contexts; same rule applied to the single pool, which has one elite per
  niche). The merged archive is judged ONCE on the `final` contexts, noise-free: `final_qd` (primary metric, same definition
  as held-out QD), plus `final_best`. Champion = merged entry with the best `select` score; winner's-curse gap = champion
  `select` score minus its `final` score. (Simplification vs section 3.5: no round-robin, ranking is by `select` score,
  and nothing is ever re-selected on `final`.)
- **Known asymmetry (disclosed).** `select` evaluations are noise-free and not counted in the evaluation budget; islands use
  them for migration and merging, the single pool has nothing to choose between. A positive E2-H1 therefore means "the whole
  pipeline beats one pool", and E2-H3 (merge only) vs E2-H2 (migration) show where the benefit comes from.
- **Repeats.** 100 paired repeats (repeat r uses island seeds seed_base + 1000 r + i and pool seed seed_base + 1000 r + 99).
- **Tests.** Primary, one per arm, 97.5% CI each (two primaries): E2-H1 `final_qd(islands_mig) - final_qd(single_pool)`.
  Exploratory (95% CI): E2-H2 `islands_mig - islands_nomig`; E2-H3 `islands_nomig - single_pool`; E2-H4 the gap difference
  `gap(islands_mig) - gap(single_pool)`, flagged OVER-SELECTING if its CI lower bound > 0.
  Rule: SUPPORTED if CI lower bound > 0, REFUTED if upper bound < 0, otherwise INCONCLUSIVE.
- **Isolation tests.** `tests/test_islands.py`: islands code contains no reference to the final contexts; budgets equal;
  determinism; migration keeps population size. Command: `python -m flyfoundry islands`; workflow `islands.yml`;
  analysis `scripts/analyze_e2.py`.

### E3 — Plumbing backtest on the project's own hypotheses (NOT validation)
- Data: the H01-H12 criteria scores (1-5, 13 criteria) and 5 weight sets from
  `zero-capital-synthesis-v1`, stored as `data/h01_h12_scores.csv` with source citation.
- Procedure: weight sets split train (3) / final (2). The swarm ranks H01-H12 using train
  weight sets; evaluation on final weight sets.
- Pass criteria (necessary, not sufficient): Spearman rho with the synthesis ranking >= 0.8
  on the final weight sets; H07 and H01 are the top 2; H03 is last.
- Mandatory caveat in the report: inputs are the same scores that define the reference
  ranking, so a pass shows the machinery works, not that it can find good businesses.

#### E3 — frozen protocol and implementation (2026-10-13)

- Fitness plugin interface: `flyfoundry/evaluation/plugins.py` (`Fitness` protocol, `ContextEvaluator`, `TabularBacktest`).
  The unchanged `C_genetic` arm runs on it (test). The synthetic landscape was NOT ported onto the protocol (it keeps its
  own `Evaluator`; golden fingerprint pinned).
- Task: candidate = 13 non-negative criterion weights; context = a weight set; fitness = Spearman between the ranking
  induced by the candidate on H01-H12 and the reference ranking of that weight set. Data: `data/` (hand-transcribed from
  section 5 of `zero-capital-synthesis-v1`; a test re-computes the published weighted means).
- Split (fixed): train = base, equal, money_first; final = automation_first, risk_averse. Champion is selected on train
  sets only and judged once on the final sets. 30 repeats x 60 generations x pop 100, GA only.
- PASS if >= 90% of repeats satisfy all three: Spearman >= 0.8 on both final sets, top-2 = {H07, H01}, last = H03.
- Disclosure: the code was run once before this text was written (to see that it works).
  Result and its weakness are in docs/RESULTS.md. The criteria above were not changed after seeing it.

### E4 — Non-stationary world (does lifetime plasticity help when the task drifts?)
Added 2026-10-13 AFTER E1 and BEFORE any drifting-world code existed or ran. Purpose: give the mushroom-body-inspired arm one
fair chance on a task where its mechanism (within-lifetime reward-modulated learning that survivors carry across generations)
has something to exploit. E1 showed no benefit on a stationary task.
- World change: every real/decoy peak centre moves with time t (= generation index) by `drift_amp * u[p,d] * sin(2*pi*t/T + phi[p])`
  per dimension (u ~ N(0,1) and phi uniform, drawn from a separate RNG stream; capital and effort dimensions do not drift;
  centres are clipped to [0,1]). With `drift_amp = 0` the world, its fingerprint and every v0.1/E1 result are unchanged.
  Training fitness is evaluated at the current t. Peak values/penalties are unchanged.
- THREE conditions, all fixed now, all reported, none added or dropped after seeing data: drift_amp = 0.15 with period
  T = 120 (slow), 40 (medium, PRIMARY), 15 (fast) generations. 100 paired seeds, 6 arms, 60 generations, population 100,
  same config as E1 otherwise (`configs/e4_drift_{slow,medium,fast}.json`).
- Primary metric `track_qd`: the same quality-diversity score as held-out QD, computed on the arm's CURRENT population
  (what it would deploy now: survivors with their learned weights plus newly born agents; for context-blind arms the
  population genomes), on the 16 held-out contexts, noise-free, at time t+1. Per seed: mean over generations 41-60.
  (The archive-based `heldout_qd` is also logged, at time t+1, but it is secondary because old elites go stale.)
- Hypotheses and decision rule (paired percentile bootstrap, 2000 resamples, n = 100; SUPPORTED if the 95% CI lower bound > 0,
  REFUTED if the upper bound < 0, otherwise INCONCLUSIVE), each evaluated in each condition:
  - E4-H1: A_fly_plastic - B_evolved_ann (>= 0 expected only if the architecture helps under drift).
  - E4-H2: A_fly_plastic - A_fly_noplast (does lifetime plasticity itself help?). PRIMARY claim = E4-H2 in the medium condition.
  - E4-H3: A_fly_plastic - A_fly_shuffled.
  - E4-H4 (sanity): C_genetic - D_random.
- Multiplicity: 3 conditions x 3 contrasts = 9 tests. Only the PRIMARY (H2, medium) may be called a confirmed finding. Any other
  SUPPORTED result is reported as exploratory.
- Validity checks (must pass before the verdict counts): (a) unit test: with drift enabled a fixed candidate set scores differently at
  different t (the drift actually matters); (b) drift_amp = 0 reproduces the v0.1/E1 world fingerprint; (c) agents still cannot reference
  held-out data (static test).
- Stopping rule, fixed now: if E4-H1 is REFUTED in all three conditions, the fly-inspired controller is declared a dead end for
  tasks of this synthetic type and v0.2 continues with C_genetic and B_evolved_ann only (islands, E2). If E4-H2 is SUPPORTED in the
  medium condition, a follow-up is justified, and it would still say nothing about real flies or real markets.
- Not allowed: changing the drift parameters, the metric window or the contrasts after seeing E4 results to make an arm look
  better. A change requires a dated amendment and the original verdict stays in the record.

## 5. Optional module: Claude in the loop (OFF by default)

Purpose: add model judgement to Phase 1 fitness (e.g. score a candidate's plausibility).
- Mechanism: `anthropics/claude-code-action` in automation mode, authenticated with a
  repository secret (`ANTHROPIC_API_KEY`, or `CLAUDE_CODE_OAUTH_TOKEN` generated with
  `claude setup-token` for subscription usage).
- Documented behaviour: with an OAuth token, runs use the owner's Claude subscription
  instead of API billing. There is NO documented way to "reserve" part of a daily limit;
  usage draws from the same pool as the owner's normal use. v0.2 therefore enforces its own
  caps: `--max-turns` small, one invocation per day, workflow `timeout-minutes`, kill switch.
- UNVERIFIED: whether Anthropic policy permits scheduled automated use of a subscription
  token (a community question exists; not read). The owner must check the current terms
  before enabling. Default decision: do not enable until checked.
- Security: the secret must never be exposed to steps that process untrusted text
  (web pages, issue comments from others). Run only on `schedule`/`workflow_dispatch` of the
  default branch. Fork PRs get no secrets.
- Output labelling: every Claude-produced score is stored in a separate column
  `model_judgement` and flagged "unverified model opinion"; it is never mixed into
  verified-fact columns.

## 6. Exit criteria for Phase 0 (all must hold)

1. E1 completes on GitHub Actions within the caps, with a green workflow run URL.
2. Shard-independence test passes (N=1 vs N=10 identical aggregates).
3. Kill/resume test: a run interrupted mid-way resumes and equals an uninterrupted run
   (as v0.1 smoke, extended to shards).
4. Static test: islands cannot reach `final` contexts.
5. All test suites green (CI), docs updated, report generated with honest verdicts for
   H1-H4 even if refuted.
6. Resource report: job-minutes, peak RSS, artifact size, versus the section 2 caps.

## 7. Open items needing the owner

- Approve the caps in section 2 (especially 120 job-minutes/day).
- Decide whether to enable the Claude-in-the-loop module (section 5) after checking terms.
- v0.1 scheduled run still unverified (first cron expected 01:30 Europe/Riga, 2026-10-13).

## 8. Phase 1 outline (not binding yet)

Task: produce a ranked list of business models, idea space wider than the original
project, no dependence on a human closer, EUR 0, owner's profile constraints.
Fitness = verified-fact layer (sourced, machine-checkable: free competitors, price anchors,
licence/ToS blockers) + labelled model-judgement layer. Output: ranking with per-item
evidence links and robustness across weight sets. A winner is a hypothesis for real-world
testing, never a result.
