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

## Key rules (v0.2.1, after the independent audit)
* **Unknown stays unknown.** A missing field is `None` with basis `unknown`; it is excluded from scoring and listed as unknown.
* **ELIGIBLE requires positive, current evidence for ALL 10 mandatory conditions**: deadline, geography, participation_format, access, age_team, fees,
  tools_and_costs, hardware, wallet, conflicts. Only deadline (future in every time zone), participation_format ("Online") and access (not invite-only) can be
  confirmed from a source claim. The other seven need a schema-2 human review (or human-entered facts). `verified` means exactly this. A future deadline
  plus "no fee" plus "geography ok" is NOT enough.
* **Reviews are bound, not permanent** (`data/bounty_reviews.json`, schema 2): each review has `rules_ref` (rules hash or version/date read), `participant_hash`
  (geography + hardware config), `evidence_url`, `reviewed_at` and per-condition status `ok | not_applicable (note >= 10 chars) | excluded`. It expires after
  `review_valid_days` (14), is invalidated when the rules text hash or the participant config changes, and a newer contradicting source fact is never hidden: the
  decision becomes NEEDS_REVIEW (`review_conflict:<condition>`) with both sides in the reasons. `acknowledged_signals` (fact + evidence hash) lets a human clear one specific signal.
  Legacy reviews (`fees`/`geo` flags) are kept but give `review_legacy_incomplete`. `python -m flyfoundry bounty review-template --id <id>` prints a skeleton.
* **Text analysis is sentence-level** (negation, zero amounts, alternatives, requirement cues, inclusion vs exclusion of the configured geography, hardware vs `available_hardware`).
  Weak (heuristic) signals only trigger a review, never a hard reject. GPUs are always weak (often provided as credits).
* **Hard rejects** (INELIGIBLE): expired, invite-only, firm fee / paid tool / wallet signal, firm unavailable hardware, firm exclusion naming the configured geography.
* **Listing safety**: a response must pass schema validation (`{}` is an error, not an empty listing); a listing is complete only if the last page was reached and distinct
  records >= `meta.total_count`; repeated pages stop the run; `unlisted` is set only after a complete listing and never for a suspicious shrink (> max(5, 50%)).
* **Identity**: canonical URL is the strong key; title+organizer is only a candidate (merged only with the same known deadline, otherwise both kept and flagged `possible_duplicates`). Unicode-aware, empty keys are never created.
* **Per-fact freshness**: each fact has `observed_at` (last confirmed), `changed_at`, `observation_id`, `parser_version`, `history`; a vanished value becomes `withdrawn` (with `last_value`), never "fresh".
* **Evidence**: every list page, overview and rules fetch is stored as an observation (URL, time, HTTP status, hash, raw body, parser version); facts link to them. Retention: raw bodies dropped
  after 30 days (latest 2 per URL and referenced ones kept), unreferenced metadata after 180 days, change log capped at 20000, VACUUM.
* **Detail pass**: per-page schedule (200/404/410 -> 7 days, 401/403 -> 3 days, transient -> next run); one 401/403 stops requests to that host for the run; robots.txt is respected; nothing is bypassed.
* **Employer safety, geography-as-configuration, no win probabilities**: unchanged.

## Scoring and effort
* Effort: before the rules are read, a wide generic range (4-40 h, confidence very_low); a keyword template is only a hypothesis. After the rules are read: template range plus deliverable adders. Platform hints (AWS, Nebius, GitLab ...) add 3-10 h each and a risk line.
* Baseline A = declared prize pool (planning USD) / mid hours; the pool is a total, NOT the attainable prize. Experimental B = weighted mean of known criteria x (0.5 + 0.5 x `criteria_fill`);
  `criteria_fill` is the share of weight with a known value and says NOTHING about evidence completeness (that is `conditions_confirmed/10`). `free_resources` has weight 0 (never inferable).
* Weight sensitivity covers weights only; `effort_scenarios` re-rank with low/mid/high hours. Neither proves the ranking is correct.
* **Two priorities**: `review_priority` (which candidate deserves human reading time first; blockers halve it) and `development_priority` (ELIGIBLE only).

## Run status, exit codes, outputs
`success` 0 | `partial` 3 | `source_unavailable` 4 | `no_data` 5 | internal error 6 | `verify-state` invalid 7. Outputs are generated in `<out>.new`, verified against `manifest.json`
(run id, times, code version, file list with SHA-256, source runs) and swapped in; on failure the last good set stays and `<out>-diagnostics/` is written. Stale briefs cannot survive. `state/latest` follows the same rule.

## Operation
```
cd C:\Extra\flyfoundry; python -m pip install -r requirements.lock; python -m pip install -e . --no-deps
cd C:\Extra\flyfoundry; python -m pytest -q
cd C:\Extra\flyfoundry; python -m flyfoundry bounty run --state-dir state_bounty --out out\bounty --provisional-briefs 3
```
`evaluate` re-ranks stored data without network (`--now` for exact reproduction). `bounty` is dispatched before the research CLI is imported, so it works on Windows (no `resource`, no numpy needed).

GitHub workflow `bounty-discovery` (daily 05:17 UTC, manual dispatch): job `discover` has a READ-ONLY token (restore with verification, offline tests, run, verify, upload artifacts); job `persist`
has `contents: write` and only runs `scripts/state_save.sh` (verification + compare-and-swap push with `--force-with-lease` of the base commit read at restore). NOTE: `contents: write` is repository-wide;
the narrowing comes from the job split. State branch: `flyfoundry-bounty-state`. Disable: `gh variable set BOUNTY_ENABLED --body false`. 4/5/6 fail the job (state and diagnostics are still saved), 3 warns.

## Manual review (the only route to ELIGIBLE)
Read the official rules, run `review-template`, fill every condition, commit to `data/bounty_reviews.json`, run `evaluate`. Only then build; submit manually; record outcomes in `data/bounty_history.json`.

## Limitations
* The scheduled GitHub run of the hardened workflow has NOT been observed (only local/synthetic tests); Windows was simulated, not run on Windows.
* Devpost is the only automated source; event pages/rules returned 403 to Actions earlier, so fees/geography etc. normally come from a human.
* Effort and technical-fit are priors. FX rates are static. ToS of Devpost not legally reviewed.

## Live verification (run 38737724223, 2026-10-15, GitHub Actions)
* Devpost list API: 3 requests, HTTP 200, 48 open hackathons, complete listing. All 48 carry prize, deadline date, registrations, themes.
* Decisions: 0 ELIGIBLE, 41 NEEDS_REVIEW, 7 INELIGIBLE (all invite-only). 0 duplicates. Fees and geography are unknown for all 48 (the list has neither).
* Event pages and /rules returned HTTP 403 to the Actions runner (the list API did not). They are not retried or bypassed; the detail pass now stops after the first 403.
  Consequence: fees/geography/deliverables cannot be read automatically from Devpost, so human review is the only route to ELIGIBLE.
* Defect found by this run and fixed afterwards: in-person events (e.g. location 'Fort Worth') were not flagged; the gate now raises `location_not_online`. Payments-domain titles
  (e.g. payment providers as organizers) now quarantine as `possible_employer_conflict`.
* Template matching is crude (keyword overlap): e.g. 'Robotic Process Automation' theme matched the scheduled-automation template. Treat suggestions as starting points.
