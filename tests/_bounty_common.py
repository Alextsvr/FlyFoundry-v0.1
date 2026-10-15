"""Shared helpers for the Bounty Factory tests. All fixtures are SYNTHETIC (shaped like the Devpost list API) and never presented as real."""
import json
from datetime import datetime, timezone

from flyfoundry.bounty_factory import pipeline as P
from flyfoundry.bounty_factory.gate import participant_hash, evidence_hash, REQUIRED
from flyfoundry.bounty_factory.http import Fetcher
from flyfoundry.bounty_factory.model import Opportunity

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
CFG = P.load_cfg("data/bounty_config.json")
RULES_HASH = "a" * 64


def item(i, title, dates="Oct 1 - Nov 30, 2026", prize="$<span data-currency-value>5,000</span>", **kw):
    d = {"id": i, "title": title, "url": f"https://h{i}.devpost.com/", "organization_name": f"Org{i}", "displayed_location": "Online",
         "submission_period_dates": dates, "prize_amount": prize, "prizes_counts": {"cash": 2, "other": 0}, "registrations_count": 120,
         "themes": [{"name": "Machine Learning/AI"}, {"name": "Open Ended"}], "invite_only": False,
         "start_a_submission_url": f"https://h{i}.devpost.com/register"}
    d.update(kw)
    return d


def page(items, total=None, per_page=24, current=1):
    return {"hackathons": items, "meta": {"total_count": len(items) if total is None else total, "per_page": per_page, "current_page": current}}


def make_transport(pages=None, robots="User-agent: *\nDisallow:\n", list_status=200, list_body=None, detail=None):
    """pages: list of page dicts (page N -> pages[N-1]); detail: callable(url)->(status, body) or str body."""
    calls = []

    def t(url, headers):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return 200, robots
        if "/api/hackathons" in url:
            if list_status != 200:
                return list_status, "err"
            if list_body is not None:
                return 200, list_body
            n = int(url.split("page=")[1].split("&")[0])
            return 200, json.dumps(pages[n - 1] if n <= len(pages) else page([], total=(pages[-1]["meta"]["total_count"] if pages else 0)))
        if callable(detail):
            return detail(url)
        return 200, detail or "<html><body><p>Entry is free. Build a Python dashboard. Submit a demo video and a GitHub repo.</p></body></html>"
    t.calls = calls
    return t


def fetcher(t, **kw):
    return Fetcher(transport=t, min_interval=0, sleep=lambda s: None, **kw)


def opp(**facts):
    o = Opportunity(id="bf-test", source="manual", source_key="k", url="https://x.example/a", title="T", organizer="O")
    for k, v in facts.items():
        o.set(k, v, "source_claim", "test")
    return o


def listed(**over):
    """An opportunity with all auto-confirmable source claims (open deadline, online, not invite-only)."""
    base = dict(deadline_date="2026-11-30", location="Online", invite_only=False)
    base.update(over)
    return opp(**base)


def review(o, cfg=None, at="2026-10-14", conditions=None, rules_ref="sha256:" + RULES_HASH, **kw):
    cfg = cfg or CFG
    conds = {c: {"status": "ok", "note": f"checked official rules for {c}"} for c in REQUIRED}
    conds.update(conditions or {})
    rv = {"id": o.id, "schema": 2, "reviewed_at": at, "reviewer": "tester", "evidence_url": "https://x.example/rules",
          "rules_ref": rules_ref, "participant_hash": participant_hash(cfg), "minutes_spent": 20, "label": "ELIGIBLE", "conditions": conds, "acknowledged_signals": []}
    rv.update(kw)
    return {o.id: rv}
