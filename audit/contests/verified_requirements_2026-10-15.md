# Official-rules requirement check: 4 real contests (2026-10-15)

**Method and limits (read first).** Each official `/rules` page was fetched once with a web-fetch tool that returns a *model-written extract*, not the raw page. It is therefore NOT raw evidence (no stored hash), and every item below must be re-read by a human on the official page before any decision. Nothing was registered, submitted or signed. No access restriction was bypassed (all four pages answered normally). Participant facts (age, residency, team, employer relations) are NOT known to the system; **no contest is declared eligible for the participant.** PayPal-type contests were skipped on purpose (employer conflict gate).

Status key: STATED = the official rules state it; NOT STATED = the rules do not say (a human must decide or ask the organizer); BLOCKER = stated condition that may exclude the participant.

| Condition | Qloo Agentic (qloo.devpost.com) | Nebius x NVIDIA (nebiusglobalaihackathon.devpost.com) | AWS CDS Agentic AI (aws-cds-partner.devpost.com) | Life After Code (gitlab-transcend.devpost.com) |
|---|---|---|---|---|
| Deadline | STATED: 2026-10-30 23:45 US Eastern | STATED: 2026-10-30 10:00 US Pacific | STATED: 2026-10-28 13:00 US Pacific | STATED: 2026-10-27 13:00 UTC |
| Geography (Latvia/EU) | NOT STATED; excludes where US/local law prohibits + named list (Brazil, Quebec, Russia, Crimea, Cuba, Iran, N. Korea) | NOT STATED (same style of exclusion list) | NOT STATED (same list + Syria) | NOT STATED (list incl. China, Syria, Donetsk/Luhansk + catch-all) |
| Age | STATED: age of majority where resident | same | same | same |
| Team size | NOT STATED (one Representative per team) | NOT STATED | NOT STATED | NOT STATED |
| Entrant type | any eligible individual/team | individuals, teams, organizations; sponsor/administrator staff excluded | **BLOCKER:** must be employed by / authorised for an AWS Partner Network (APN) registered organization | any eligible individual |
| Entry fee | STATED: none | STATED: none | STATED: none | STATED: none |
| Mandatory tools / costs | Qloo API (access via a Google form); API price NOT STATED | **Must run on Nebius Token Factory/AI Cloud and use an NVIDIA open model**; usage cost NOT STATED, optional credits via Builder Program | **Must use a CDS service (End User Messaging SMS/RCS/WhatsApp or SES); entrant pays AWS usage; $50 credits on request**; needs a Partner Central (ACE) opportunity ID | **Must be built on GitLab Duo Agent Platform**; cost NOT STATED |
| Hardware | NOT STATED | Physical AI track only needs hardware/robot video; other tracks NOT STATED | NOT STATED (video shows project on its target device) | NOT STATED (video on target device) |
| Wallet / crypto | NOT STATED | NOT STATED | NOT STATED | NOT STATED |
| Online format | implied online (NOT explicit) | entry online; city events exist for a bonus award | implied online | implied online |
| Employer conflict | not applicable on its face; human confirmation needed | same | same | same |
| Declared prize pool | $25,000 (15k/6k/4k) | up to $50,000 incl. bonuses; **overall prizes are $20k/10k/6k, track prizes are hardware (Jetson), so attainable cash is much smaller than the list figure** | $40,000 incl. Meta WhatsApp prize $10,000; main $18k/8k/4k | $45,000 across paths/special prizes |
| Deliverables | working project using the Qloo API, demo link, public open-source repo, text description, free judge access | working project, demo URL, text, public OSS repo + README, <3 min YouTube video, track, feedback, update explanation for old projects | repo, architecture diagram, ~3 min video, deployed URL, ACE opportunity ID; project must be new | MIT-licensed public GitLab repo with CI history, <3 min YouTube video, text; Path B needs a live deployed URL |

## What this check changed in the picture
* AWS CDS: a likely **hard exclusion** (APN employment) that the list data could never show; it should move to INELIGIBLE after the participant confirms they have no APN affiliation. Ranking from list data alone had it 4th.
* Nebius x NVIDIA: the headline $50,000 is not attainable cash (bonus/swag/hardware items); the mandatory platform is a named dependency, so the generic estimate (previously 5 h) was far too optimistic; the system now shows 10-60 h at very low confidence and flags the platform.
* Life After Code, Qloo: no blocker found in the extracts, but a platform/API dependency exists (GitLab Duo, Qloo API).
* Geography is **NOT STATED for Latvia in all four**: the rules exclude by US law/named list, so Latvia is "not named as excluded", which is not the same as confirmed eligible. A human decides.

## Questions only the participant can answer (for a schema-2 review)
1. Are you of legal age where you live and may you take part as an individual (not as an employee of the sponsor)? 2. Do you accept that "not named as excluded" is enough for Latvia, or do you want the organizer to confirm? 3. Is using the mandatory platform (Nebius / GitLab Duo / Qloo API) free for you in practice (credits, free tier)? Check the pricing page. 4. Any contact with your employer's merchants or confidential data needed? (none expected). 5. Wallet/hardware: none stated; confirm after reading the full rules.

## Brief status
No confirmed brief can be produced: all four have 0 of 10 mandatory conditions confirmed by a human review. Provisional briefs exist in `audit/reeval48/` (top review-priority items) and are labelled PROVISIONAL / UNVERIFIED.
