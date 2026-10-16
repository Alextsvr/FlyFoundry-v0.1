# Development brief: Qloo Agentic Hackathon

> **PROVISIONAL.** Eligibility is NOT verified (decision: NEEDS_REVIEW). Do not invest build time before the review items below are resolved.

- Opportunity id: `bf-a71bbfca935d`  |  source: devpost  |  generated: 2026-10-15T14:09:58Z
- Official URL: https://qloo.devpost.com/
- Organizer: Qloo
- Reward: prize 25000.0 [source_claim] currency 'USD' [source_claim], cash prizes 3 [source_claim]
- Deadline: '2026-10-30' [source_claim]; precision 'date' [inferred]; time zone UNKNOWN
- Gate decision: **NEEDS_REVIEW**  |  priority score (B): 0.633  |  criteria filled: 93% (heuristics included; not evidence completeness)  |  required conditions confirmed: 3/10

## Verified requirements and eligibility evidence
- [ok] `deadline_ok`: source claim 2026-10-30, in the future in every time zone
- [review] `geo_unverified`: geography: no valid confirmation on record
- [review] `unconfirmed:age_team`: age_team: no valid confirmation on record
- [review] `fees_unverified`: fees: no valid confirmation on record
- [review] `unconfirmed:tools_and_costs`: tools_and_costs: no valid confirmation on record
- [review] `unconfirmed:hardware`: hardware: no valid confirmation on record
- [review] `unconfirmed:wallet`: wallet: no valid confirmation on record
- [review] `unconfirmed:conflicts`: conflicts: no valid confirmation on record
- Required condition `deadline`: **confirmed** (source claim 2026-10-30, in the future in every time zone)
- Required condition `geography`: **unknown** (no valid confirmation on record)
- Required condition `participation_format`: **confirmed** (source claim: location 'Online')
- Required condition `access`: **confirmed** (source claim: not invite-only)
- Required condition `age_team`: **unknown** (no valid confirmation on record)
- Required condition `fees`: **unknown** (no valid confirmation on record)
- Required condition `tools_and_costs`: **unknown** (no valid confirmation on record)
- Required condition `hardware`: **unknown** (no valid confirmation on record)
- Required condition `wallet`: **unknown** (no valid confirmation on record)
- Required condition `conflicts`: **unknown** (no valid confirmation on record)

Facts on record (value [basis]):
- location: 'Online' [source_claim]
- geo_restriction_text: UNKNOWN
- invite_only: False [source_claim]
- fees_required: UNKNOWN
- deliverables: UNKNOWN
- submission_method: 'devpost_submission_form' [source_claim]
- themes: ['Machine Learning/AI'] [source_claim]
- registrations_count: 1480 [source_claim]

## Suggested solution (hypothesis from keywords; validate against the official rules)
- Primary template: **Lightweight AI/ML evaluation project** (`ml_eval`). Intended use: Small reproducible evaluation of models/prompts using free or local resources.
- Reuse: flyfoundry.research (benchmark discipline, bootstrap CIs)

## Minimum viable deliverable
- Exactly the artifacts the official rules require (read them first). Defaults when the rules are silent: public repository with README, working demo, short demo video.
- Do not add scope beyond the stated judging criteria.

## Architecture
- Inputs: public dataset, local model or free tier
- Outputs: evaluation notebook/script, results table, report
- Dependencies: numpy, optional local model
- Keep dependencies minimal; prefer the Python standard library; no paid services; secrets never committed.

## Effort estimate (planning aid, not a promise)
- Range **SMALL-LARGE**: 7.0-50.0 h (mid 28.5 h), confidence **very_low**, requirements read: **none**, deliverable kind: prototype
- Indicative split of the mid estimate (h): {'research': 3.4, 'development': 15.7, 'testing': 4.3, 'deployment': 2.3, 'video_docs': 2.9}
- Assumption: requirements NOT read (none): generic prior 4.0-40.0 h; keyword template match is only a hypothesis and does not narrow the range

## Acceptance criteria
- Every requirement in the official rules maps to a checked item below.
- A fresh clone runs with documented commands and no paid API.
- Tests pass locally and in CI.
- Demo, README and submission text contain no claim that cannot be backed by evidence.

## Testing plan
- determinism test
- metric unit tests

## Deployment plan
- repo + report page

## Submission checklist (a human performs every external step)
- [ ] Official rules re-read on the day of submission; deadline and time zone confirmed
- [ ] Eligibility (country, age, team, fees) confirmed by a human and recorded in data/bounty_reviews.json
- [ ] Confirmed: no employer-confidential data/code used and no contact with payment-system merchants required
- [ ] Repository public, license present, no secrets in history
- [ ] Demo URL / video reachable from a logged-out browser
- [ ] Submission entered manually by the human; outcome and any prize recorded in data/bounty_history.json

## Human actions required
- read the official rules and confirm eligibility
- register/submit manually (the system never submits)
- record demo video (typical requirement; unverified)

## Known uncertainties
- geo_unverified: geography: no valid confirmation on record
- unconfirmed:age_team: age_team: no valid confirmation on record
- fees_unverified: fees: no valid confirmation on record
- unconfirmed:tools_and_costs: tools_and_costs: no valid confirmation on record
- unconfirmed:hardware: hardware: no valid confirmation on record
- unconfirmed:wallet: wallet: no valid confirmation on record
- unconfirmed:conflicts: conflicts: no valid confirmation on record
- risk: template hypothesis 'ml_eval' comes from theme/title words only
- risk: deliverables (video, deployment, repository, write-up) unknown until the rules are read
- risk: names platform 'qloo': mandatory use of its stack/API/credits is possible but unverified (accounts, credits, learning time)
- unknown scoring inputs: deliverable_complexity, free_resources
