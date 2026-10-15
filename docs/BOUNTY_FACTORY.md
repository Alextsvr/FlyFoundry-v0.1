# Bounty Factory (FlyFoundry v0.2 extension)

Semi-autonomous pipeline that discovers, verifies, ranks and prepares hackathon / bounty opportunities. EUR 0, no paid APIs, no
LLM needed. It never registers, signs, pays or submits anything: a human approves and performs every external step.
It is independent of the research code (`flyfoundry/bounty_factory/`); research experiments, results and workflows are untouched.

## Pipeline
`discover` (sources -> raw observations + merged records) -> `detail` (public event pages, robots-checked, bounded) -> `gate`
(ELIGIBLE / INELIGIBLE / NEEDS_REVIEW) -> `feasibility` (MICRO..LARGE) -> `scoring` (baseline A, experimental B, sensitivity) ->
`report` (HTML, JSON, CSV) -> `brief` (development brief + Claude Code prompt).

| Module | Role |
|---|---|
| `model.py` | `Opportunity` with `Fact(value, basis, evidence)`; basis is `source_claim`, `inferred`, `human_confirmed`, `human_entered` or `unknown`. Stable id = hash of canonical URL. |
| `store.py` | SQLite: `observations` keep raw responses + SHA-256 + fetch time; `opportunities` merged records; `changes` field-level history; `source_runs` accessibility log. |
| `sources/` | Source registry (status per source) and adapters: `devpost` (live), `manual` (human intake). |
| `http.py` | User agent, runtime robots.txt check, min interval, retry with exponential backoff, run time budget. |
| `detail.py` | Pattern signals from page text (fees, paid tools, wallets, geography wording, hardware, merchant keywords, deliverables). |
| `gate.py` | Deterministic eligibility. |
| `feasibility.py`, `templates.py` | Effort class + hours breakdown, confidence, assumptions; 8 template metadata entries. |
| `scoring.py` | Criteria, weights, sensitivity, Kendall tau. |
| `report.py`, `brief.py`, `cli.py`, `pipeline.py` | Outputs and orchestration. |

## Key rules
* **Unknown stays unknown.** A missing field is `None` with basis `unknown`; it is excluded from scoring (and listed as unknown), never guessed.
* **ELIGIBLE needs positive evidence**: deadline known and in the future in every time zone, fees confirmed absent, geography confirmed,
  no unresolved employer-conflict signal. Today only a human record in `data/bounty_reviews.json` (or human-entered manual intake) supplies
  that evidence, so list data alone yields NEEDS_REVIEW at best. This is intentional.
* **Deadlines**: Devpost gives a calendar date with no time zone. The gate computes the window UTC+14..UTC-12: past the whole window = expired
  (INELIGIBLE); inside it = `deadline_ambiguous` (NEEDS_REVIEW); before it = open.
* **Hard rejects** (INELIGIBLE): expired, invite-only, fee/deposit/token purchase signal, paid tool required, wallet/on-chain spend, unavailable hardware,
  exclusion wording that names the configured geography. Regex-detected signals are inferences; a human review can override with explicit fields.
* **Employer safety**: payment/merchant keywords quarantine an item (`possible_employer_conflict`). The system uses no employer knowledge, data or code,
  and the Claude prompt forbids it. Whether a given activity conflicts with an employment contract is NOT assessed here.
* **Geography is configuration** (`data/bounty_config.json`, `participant`), never inferred from IP.
* **No win probabilities.** Competition intensity is the registration count when present (a participant count, not a probability) or unknown.

## Scoring
Baseline A: planning-USD prize per estimated hour; unknown prize ranks last; ties by id. Experimental B: weighted mean of known criteria
(weights in config: reward 0.22, technical fit 0.17, time 0.12, deadline 0.12, prize count 0.05, intensity 0.06, complexity 0.06, reusability 0.06,
human involvement 0.06, free resources 0.04, requirements quality 0.04), multiplied by `0.5 + 0.5 * coverage` so thin evidence is visible, not hidden.
Sensitivity: 300 seeded weight perturbations (x U(0.5,1.5)); reports rank ranges and top-3 frequency; items with 0.2 <= freq < 0.8 are marked unstable.
GA / neural ranking is NOT used (no evidence of improvement over A/B yet; the research code is available for later comparison on the same set).

## Operation
Local (Windows PowerShell):
```
cd C:\Extra\flyfoundry; python -m pip install -r requirements.lock; python -m pip install -e . --no-deps
cd C:\Extra\flyfoundry; python -m pytest -q
cd C:\Extra\flyfoundry; python -m flyfoundry bounty run --state-dir state_bounty --out out\bounty --provisional-briefs 3
cd C:\Extra\flyfoundry; start out\bounty\report.html
```
`evaluate` re-ranks from stored data without network (`--now 2026-10-15T12:00:00Z` for exact reproduction).

GitHub: workflow `bounty-discovery` (daily 05:17 UTC, manual dispatch). State lives on orphan branch `flyfoundry-bounty-state` (sqlite + latest report);
the report is also an artifact (30 days). Disable: `gh variable set BOUNTY_ENABLED --body false`. Concurrency group `flyfoundry-bounty`, 25 min timeout,
in-run time budget 15 min, a failed source is recorded and skipped. No secrets are used.

## Manual review (the only route to ELIGIBLE)
1. Open the official rules from the report. 2. Add to `data/bounty_reviews.json`:
`{"id":"bf-...","fees":"none","geo":"ok","employer_conflict":"none","reviewed_at":"YYYY-MM-DD","minutes_spent":10,"evidence_url":"...","label":"ELIGIBLE"}`
(`geo` may be `excluded`; `label` is your own verdict and feeds the precision metric). 3. Re-run `evaluate`. 4. Only then build; submit manually; record the outcome in `data/bounty_history.json`.
Opportunities from sources the system cannot access go to `data/bounty_manual_intake.json`.

## Metrics
Valid opportunities, decisions, source coverage, duplicate rate (per process run), evidence freshness, eligibility precision (needs human labels; n/a until then),
estimated vs actual hours (needs history), review minutes, ranking stability, A-vs-B agreement. No significance is claimed on small samples; submission-level
metrics (acceptance, prizes, revenue/hour, reuse %) start after real submissions.

## Limitations
* Devpost is the only live automated source; its Terms of Service were not legally reviewed. Detail parsing is heuristic and was validated on synthetic HTML only until a live run exists.
* The Devpost list has no eligibility, fee or time-zone data; those need the detail pass or a human.
* Effort estimates are keyword/template priors (confidence low without detail). Technical-fit is a keyword heuristic.
* FX rates in config are static planning values; '$' is assumed USD.
* Superteam Earn, DoraHacks, Gitcoin, Colosseum are not automated (see BOUNTY_SOURCES.md).
