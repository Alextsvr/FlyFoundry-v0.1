# FlyFoundry v0.2 — Specification (pre-registered)

Status: DRAFT, written before any v0.2 code or run exists. Nothing below is a result.
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

### E3 — Plumbing backtest on the project's own hypotheses (NOT validation)
- Data: the H01-H12 criteria scores (1-5, 13 criteria) and 5 weight sets from
  `zero-capital-synthesis-v1`, stored as `data/h01_h12_scores.csv` with source citation.
- Procedure: weight sets split train (3) / final (2). The swarm ranks H01-H12 using train
  weight sets; evaluation on final weight sets.
- Pass criteria (necessary, not sufficient): Spearman rho with the synthesis ranking >= 0.8
  on the final weight sets; H07 and H01 are the top 2; H03 is last.
- Mandatory caveat in the report: inputs are the same scores that define the reference
  ranking, so a pass shows the machinery works, not that it can find good businesses.

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
