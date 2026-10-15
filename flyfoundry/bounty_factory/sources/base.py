"""Source registry. Status is one of: supported | unsupported | manual_review. Nothing is guessed: a source we have not
verified is not 'supported'. See docs/BOUNTY_SOURCES.md for the evidence behind each status."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceInfo:
    name: str
    status: str
    access: str
    reason: str
    checked: str


SOURCES = {
    "devpost": SourceInfo("devpost", "supported", "public JSON list endpoint https://devpost.com/api/hackathons",
                          "robots.txt allows generic agents (verified 2026-10-15, see docs). No separate API terms were found; the "
                          "adapter is conservative (robots check at runtime, 2 s between requests, bounded pages). Terms of Service "
                          "have NOT been legally reviewed: a human should read them before relying on this source.", "2026-10-15"),
    "superteam_earn": SourceInfo("superteam_earn", "unsupported", "listing API requires registering an agent account (Bearer key)",
                                 "Account creation is forbidden by the task constraints; robots.txt allows page crawling but no public "
                                 "documented read API exists, and HTML scraping was not assessed. Use manual intake instead.", "2026-10-15"),
    "dorahacks": SourceInfo("dorahacks", "manual_review", "not assessed",
                            "Not assessed in this iteration: robots.txt/terms/API not verified. Add listings via manual intake.", "2026-10-15"),
    "gitcoin": SourceInfo("gitcoin", "manual_review", "not assessed",
                          "Not assessed in this iteration. Add listings via manual intake.", "2026-10-15"),
    "colosseum": SourceInfo("colosseum", "manual_review", "not assessed",
                            "Not assessed in this iteration. Add listings via manual intake.", "2026-10-15"),
    "manual": SourceInfo("manual", "supported", "data/bounty_manual_intake.json (typed in by a human)",
                         "Entries are human-entered; facts not typed in stay unknown.", "2026-10-15"),
}


def source_status_table() -> list:
    return [vars(s) for s in SOURCES.values()]
