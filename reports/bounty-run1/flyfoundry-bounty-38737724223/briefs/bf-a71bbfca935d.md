# Development brief: Qloo Agentic Hackathon

> **PROVISIONAL.** Eligibility is NOT verified (decision: NEEDS_REVIEW). Do not invest build time before the review items below are resolved.

- Opportunity id: `bf-a71bbfca935d`  |  source: devpost  |  generated: 2026-10-15T12:50:43Z
- Official URL: https://qloo.devpost.com/
- Organizer: Qloo
- Reward: prize 25000.0 [source_claim] currency 'USD' [source_claim], cash prizes 3 [source_claim]
- Deadline: '2026-10-30' [source_claim]; precision 'date' [inferred]; time zone UNKNOWN
- Gate decision: **NEEDS_REVIEW**  |  priority score (B): 0.720  |  evidence coverage: 100%

## Verified requirements and eligibility evidence
- [ok] `deadline_ok`: deadline 2026-10-30 is in the future in every time zone
- [review] `fees_unverified`: no explicit evidence that participation is free
- [review] `geo_unverified`: no statement about who may participate was recorded (location 'Online' is not an eligibility statement)

Facts on record (value [basis]):
- location: {'icon': 'globe', 'location': 'Online'} [source_claim]
- geo_restriction_text: UNKNOWN
- invite_only: False [source_claim]
- fees_required: UNKNOWN
- deliverables: UNKNOWN
- submission_method: 'devpost_submission_form' [source_claim]
- themes: ['Machine Learning/AI'] [source_claim]
- registrations_count: 1472 [source_claim]

## Suggested solution (inferred, to be validated against the official rules)
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
- Class **MEDIUM**, ~15.9 h total, confidence **low**, deliverable kind: prototype
- Breakdown (h): {'research': 1.8, 'development': 8.2, 'testing': 2.2, 'deployment': 1.2, 'video_docs': 2.5}
- Assumption: primary template 'ml_eval' typical effort 6-24 h
- Assumption: only list-level metadata is known: deliverables/judging unseen, so confidence is low

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
- record demo video

## Known uncertainties
- fees_unverified: no explicit evidence that participation is free
- geo_unverified: no statement about who may participate was recorded (location 'Online' is not an eligibility statement)
- unknown scoring inputs: none
