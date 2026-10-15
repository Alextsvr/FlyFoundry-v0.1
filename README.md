# FlyFoundry v0.1 — evolutionary venture discovery lab

An experimental, EUR 0, CPU-only research system. It asks:

> Can a population of biologically inspired, evolving agents discover a more diverse and valuable set of
> business opportunities than conventional optimisation algorithms under comparable resource constraints?

**This is an experimental search/optimisation system. It makes no claim of conscious digital organisms, and nothing
it produces is evidence of real demand, customers or revenue** (real revenue is EUR 0 / unknown).

## What v0.1 actually is

| Arm | What it is | Status |
|---|---|---|
| A `A_fly_plastic` | Mushroom-body-**inspired** sparse network (PN→KC→output, top-k "APL" inhibition) with dopamine-like reward-modulated plasticity, evolved | runs |
| A `A_fly_noplast` | same circuit, plasticity off (ablation) | runs |
| A `A_fly_shuffled` | same circuit, degree-preserving shuffled PN→KC wiring (ablation) | runs |
| B `B_evolved_ann` | tanh MLP, same input/output/parameter budget, same evolutionary engine | runs |
| C `C_genetic` | conventional GA (tournament, crossover, mutation, elitism, fitness sharing, random immigrants) on raw candidate vectors | runs |
| D `D_random` | random search, same candidate representation and evaluation budget | runs |
| E `E_llm_baseline` | adapter implemented (`flyfoundry/agents/llm_baseline.py`), **NOT RUN**: no LLM endpoint is configured; no responses are ever simulated | not run |

### Biological fidelity (honest statement)
No FlyWire or hemibrain connectivity is downloaded or used. The mushroom-body network has a **synthetic, seeded PN→KC wiring**; it is
a documented circuit-motif abstraction, not a connectome, and it must not be called one. Model type, neuron/synapse counts, the
learning equations, references and limitations are written into every checkpoint and the dashboard
(`flyfoundry/biology/mushroom_body.py` docstring, "Provenance & model cards" tab). A scientifically grounded FlyWire sub-connectome
model was not feasible within v0.1's time/resource budget (codex.flywire.ai and zenodo.org were not reachable from the build sandbox;
and full-connectome simulation is far beyond a free CPU runner). Next step: load a published MB sub-connectome and replace the synthetic wiring.

## Experimental design

* **Candidate** = 12 numbers in [0,1] decoded into a structured opportunity (customer, problem, solution, revenue mechanism, capital,
  effort, evidence strength, differentiation, claimed demand, channel, automation, risk) — see `flyfoundry/research/opportunities.py`.
  Customer/problem labels come from a **synthetic taxonomy** (`data/taxonomy.json`), not from market data.
* **Hidden synthetic landscape** (`environments/benchmark.py`): 6 real peaks (valuable and feasible) + 2 decoys (look valuable, need
  unrealistic capital). Peak locations shift with a 4-number market context through a hidden map. Penalties: capital above a small budget, effort,
  unsupported claims (claimed demand above evidence), duplicates (fitness sharing).
* **Train / held-out split**: training feedback is noisy and only on 16 training contexts; held-out reporting is noise-free on 16 different
  contexts, computed from each arm's archive of *training-selected* elites. Held-out values never touch selection
  (static test `test_agents_cannot_reach_heldout`).
* **Fairness**: every arm gets exactly `pop_size` evaluations per generation (enforced by a budgeted `Evaluator`; invariant checked and
  stored), identical world, identical per-seed scenario/noise stream across arms (paired seeds), CPU time and allocation tracked per arm.
  CPU-time accounting separates *search* cost from *monitoring* (held-out/metrics) cost.
* **Diversity**: MAP-Elites archive (64 niches), fitness sharing (controlled resource competition), niche-aware parent sampling for A/B,
  random immigrants for C, elitism everywhere. Novelty and diversity tracked per generation.
* **Statistics**: percentile bootstrap CIs over seeds, paired differences. With fewer than `min_seeds_for_claim` (10) seeds the report
  never declares significance and says so.
* **Real-world evidence fitness**: *not implemented in v0.1* (no public dataset is wired in; nothing is invented). The evidence-tier ladder
  (synthetic score → evidence-supported hypothesis → validated demand → paying customer → collected revenue) is carried through the report;
  everything is at the lowest tier. See `docs/EVIDENCE_LAYER.md`.

## Persistence (durable, €0)

State (population genomes, learned weights, RNG states, archives, lineage, fitness history, hypotheses, metadata, dataset/code versions) is
stored as versioned, SHA-256-checked checkpoints (`ckpt_NNNNNN.json.gz` + `manifest.json`), restored at the start of every run and
persisted at the end to a **single-commit orphan branch `flyfoundry-state`** of this repository (force-pushed, so repository size stays bounded;
three checkpoints are kept). GitHub Actions cache/artifacts are *not* relied on (they expire).
Missing state is never silently turned into generation 0: a fresh start needs `--allow-fresh`, and the workflow only permits it for the
very first run or an explicit `fresh_start=true`. A corrupt newest checkpoint falls back to the newest valid one with a loud warning; if none
is valid the run fails (exit 3). Details and privacy trade-offs: `docs/PERSISTENCE.md`. **The state branch is public in a public
repository** — fine here because it contains only synthetic benchmark data; do not put real business data into it (use a private repo).

## Running

```bash
pip install -r requirements.lock && pip install -e . --no-deps      # Python 3.12
python -m pytest -q                                                 # tests
python -m flyfoundry smoke                                          # ~4 s end-to-end self-check
python -m flyfoundry fresh  --config configs/nightly.json --state-dir state --out reports/latest --generations 20
python -m flyfoundry resume --config configs/nightly.json --state-dir state --out reports/latest --generations 20
python -m flyfoundry run    --state-dir state --allow-fresh         # resume, or start fresh only if nothing exists
python -m flyfoundry report   --state-dir state --out reports/latest   # regenerate dashboard from checkpoint
python -m flyfoundry validate --state-dir state                         # integrity check (exit 3 if newest is invalid)
python -m flyfoundry export   --state-dir state --out out/              # results.json, history.csv, hypotheses.json
```

Outputs in `--out`: `index.html` (self-contained dashboard, no external requests), `summary.md`, `results.json`, `history.csv`, `hypotheses.json`.

## GitHub Actions

* `ci.yml` — tests + smoke experiment on every push/PR.
* `experiment.yml` — `workflow_dispatch` (inputs: generations, seeds, pop_size, fresh_start) and a nightly schedule at **01:30 Europe/Riga**
  (two UTC crons + a guard that allows exactly one run per Riga calendar date at any hour, handling the EEST/EET switch; GitHub may start scheduled runs hours late). `concurrency` prevents
  overlap; 60-minute timeout; artifacts kept 14 days; the run summary shows the report; optional GitHub Pages deployment when the repository
  variable `ENABLE_PAGES=true`. Standard hosted CPU runner only; no paid features.

## Layout

`flyfoundry/{agents,biology,evolution,environments,evaluation,research,storage,reporting,cli}`, `tests/`, `configs/`, `data/`, `docs/`,
`scripts/` (state sync + local workflow simulation), `.github/workflows/`, `reports/`.

## Where results live

1. **Run summary** — GitHub → Actions → the run → "Summary" (tables, conclusions, resume test).
2. **Artifact** `flyfoundry-report-<run id>` (full dashboard `index.html`; kept 14 days).
3. **Branch `flyfoundry-state`** (permanent, overwritten each run): `latest-report/` (`summary.md`, `results.json`, `history.csv`,
   `hypotheses.json`, `index.html` of the most recent run), `runs.csv` (one row per run: generations, evaluations, CPU, held-out score per arm,
   run URL) and the checkpoints. Raw view: `https://raw.githubusercontent.com/<owner>/<repo>/flyfoundry-state/runs.csv`.
4. `docs/RESULTS.md` — hand-written interpretation; update it after meaningful runs.

Note: GitHub disables scheduled workflows after 60 days without repository activity; if the nightly runs stop, re-enable the workflow in the Actions tab.

## Results

See `docs/RESULTS.md` (kept in sync with the latest verified run) and the dashboard artifact of the latest workflow run.

## Limitations

Single synthetic world; stationary landscape (little for plasticity to exploit); 5 seeds (<10, no significance claims); held-out QD gives
partial credit by distance so it is lenient — read it together with held-out discovery rate; MB model is not a connectome; no real-world
evidence layer; no LLM arm; archive elites are ranked by a single noisy evaluation. Defaults were fixed before results were seen; the small
exploratory parameter sweep in `docs/EXPLORATORY_SENSITIVITY.md` was *not* used to tune the main comparison.

## Swarm (v0.2, in progress)

`flyfoundry run --shard i/N` runs only shard *i* of *N* contiguous seed blocks (0-based); `flyfoundry merge --shard-dir ...` combines
shard state directories into one full experiment and writes the normal report. A merged result equals the unsharded run
state-for-state (see `tests/test_shards.py`). `.github/workflows/swarm.yml` runs the shards as parallel jobs (max 10 at once, manual
trigger only) and is disabled until the repository variable `SWARM_ENABLED` is `true`. Plan and pre-registered criteria: `docs/V0_2_SPEC.md`.

E4 (drifting world): `drift_amp > 0` makes peak centres oscillate with the generation clock; arms additionally log `track_qd` (current population on held-out contexts). Verdict rules: `docs/V0_2_SPEC.md`, analysis: `scripts/analyze_e4.py`.


## Bounty Factory (v0.2 extension)
Discovers, gates, ranks and prepares hackathon/bounty opportunities with no paid APIs and no submissions (a human approves everything).
Start with `docs/BOUNTY_FACTORY.md` (architecture, operation, manual review, limitations) and `docs/BOUNTY_SOURCES.md`.
Run: `python -m flyfoundry bounty run --state-dir state_bounty --out out/bounty`. Workflow: `.github/workflows/bounty_discovery.yml`.
Research experiments and results (E1-E4, Phase 1) are unchanged.
