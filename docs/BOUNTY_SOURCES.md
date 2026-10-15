# Source adapters (verified 2026-10-15)

| Source | Status | Evidence | Notes |
|---|---|---|---|
| Devpost | **supported** | `robots.txt` (`User-agent: *`, empty `Disallow`) retrieved 2026-10-15; `GET https://devpost.com/api/hackathons?status[]=open&order_by=deadline&page=N` returned JSON with keys `hackathons`, `meta` (checked through a fetch tool that summarises pages; raw capture happens in the Actions run). | Fields used: id, title, url, organization_name, displayed_location, submission_period_dates (date range, no time/zone), prize_amount (HTML-wrapped, currency symbol), prizes_counts, registrations_count, themes, invite_only, start_a_submission_url. Runtime: robots check, 2 s spacing, <=5 pages, retry/backoff. ToS not legally reviewed. |
| Superteam Earn | unsupported | Its `skill.md` documents listing endpoints under `/api/agents/` that require registering an agent account and a Bearer key. `robots.txt` allows page crawling except dashboard/auth/sign-in paths. | Creating accounts is prohibited by the task; no public documented read API; HTML scraping not assessed. Use manual intake. |
| DoraHacks | manual_review | Not assessed: robots/terms/API not verified. | Manual intake. |
| Gitcoin | manual_review | Not assessed. | Manual intake. |
| Colosseum | manual_review | Not assessed. | Manual intake. |
| Manual intake | supported | `data/bounty_manual_intake.json` | Human-entered facts only. |

Adding an adapter: implement `to_opportunity()` returning `Opportunity` objects with `Fact` bases, verify robots/terms first, register the status in `sources/base.py`,
add offline fixture tests. A source that cannot be accessed compliantly stays `unsupported`/`manual_review`; stale data is never substituted.
