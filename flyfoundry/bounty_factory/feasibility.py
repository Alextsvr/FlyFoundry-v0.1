"""Planning estimate of production effort. Rule-based and deliberately coarse; always carries a confidence and assumptions.
Estimates are planning aids, not promises."""
from __future__ import annotations

from .model import Opportunity
from .templates import match_templates, by_id

CLASSES = (("MICRO", 3.0), ("SMALL", 8.0), ("MEDIUM", 24.0), ("LARGE", float("inf")))   # upper bound of mid-estimate, hours
RESEARCH_HINTS = ("research", "report", "whitepaper", "essay", "analysis", "study")
PRODUCTION_HINTS = ("production", "mainnet", "scalable", "enterprise", "full-stack", "full stack", "multi-chain", "mobile app", "backend")


def opportunity_text(o: Opportunity) -> str:
    themes = o.fact("themes").value or []
    return " ".join([o.title, o.organizer, " ".join(themes) if isinstance(themes, list) else str(themes), str(o.fact("description_text").value or "")]).lower()


def estimate(o: Opportunity) -> dict:
    text = opportunity_text(o)
    matches = match_templates(text)
    assumptions, risks, human = [], [], ["read the official rules and confirm eligibility", "register/submit manually (the system never submits)"]
    if matches:
        tpl = by_id(matches[0]["id"])
        lo, hi = tpl["effort_hours"]
        assumptions.append(f"primary template '{tpl['id']}' typical effort {lo}-{hi} h")
        tid = tpl["id"]
    else:
        lo, hi, tid = 6, 20, None
        assumptions.append("no template keywords matched: generic 6-20 h prior")
        risks.append("scope unknown: no template matched the listing text")
    mid = (lo + hi) / 2
    kind = "prototype"
    if any(h in text for h in RESEARCH_HINTS) and tid == "research_report":
        kind = "research_deliverable"
    if any(h in text for h in PRODUCTION_HINTS):
        kind = "production_app"
        mid *= 1.8
        risks.append("text suggests production-grade scope")
    deliv = o.fact("deliverables").value or []
    video = 1.0 if "demo_video" in deliv or not deliv else 0.5
    if "demo_video" in deliv or not deliv:
        human.append("record demo video")
    if "deployed_app" in deliv:
        human.append("deploy and keep a public URL alive")
    parts = {"research": round(mid * 0.12, 1), "development": round(mid * 0.55, 1), "testing": round(mid * 0.15, 1),
             "deployment": round(mid * 0.08, 1), "video_docs": round(mid * 0.10 + video, 1)}
    total = round(sum(parts.values()), 1)
    cls = next(n for n, ub in CLASSES if total <= ub)
    if o.fact("token_or_wallet_required").value is True:
        risks.append("wallet/on-chain steps need a human and may involve costs")
    conf = "low"
    if o.detail_fetched_at and deliv:
        conf = "medium"
    else:
        assumptions.append("only list-level metadata is known: deliverables/judging unseen, so confidence is low")
    return {"class": cls, "hours": parts, "total_hours": total, "deliverable_kind": kind, "template": tid,
            "template_matches": matches, "confidence": conf, "assumptions": assumptions, "risks": risks,
            "human_actions": human, "human_minutes_estimate": 45 + 15 * len(human)}
