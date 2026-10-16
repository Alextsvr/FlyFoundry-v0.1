"""Planning estimate of production effort. Coarse and rule-based; it states what it does NOT know.

Before the requirements (rules page) have been read, the estimate is a deliberately WIDE generic range with very low
confidence; the keyword-matched template is only a hypothesis and does not narrow it. After the rules were read, the template
range plus detected deliverables/platforms is used. Estimates are planning aids, not promises."""
from __future__ import annotations

import re

from .model import Opportunity
from .templates import match_templates, by_id

CLASSES = (("MICRO", 3.0), ("SMALL", 8.0), ("MEDIUM", 24.0), ("LARGE", float("inf")))   # upper bound (hours)
UNREAD_RANGE = (4.0, 40.0)        # generic prior used when requirements were not read (a prior, not a measurement)
RESEARCH_HINTS = ("research", "report", "whitepaper", "essay", "analysis", "study")
PRODUCTION_HINTS = ("production", "mainnet", "scalable", "enterprise", "full-stack", "full stack", "multi-chain", "mobile app", "backend")
DELIV_HOURS = {"demo_video": (1.0, 3.0), "deployed_app": (2.0, 6.0), "slides": (1.0, 3.0), "written_description": (0.5, 1.5), "public_repository": (0.5, 1.0)}
PLATFORM_HOURS = (3.0, 10.0)


def cls(hours: float) -> str:
    return next(n for n, ub in CLASSES if hours <= ub)


def opportunity_text(o: Opportunity) -> str:
    themes = o.fact("themes").value or []
    return " ".join([o.title, o.organizer, " ".join(themes) if isinstance(themes, list) else str(themes), str(o.fact("description_text").value or "")]).lower()


def requirements_read(o: Opportunity) -> str:
    """'rules' | 'overview' | 'none' (what was actually read from the official pages)"""
    if (o.detail.get("rules") or {}).get("ok"):
        return "rules"
    if (o.detail.get("overview") or {}).get("ok") or o.detail_fetched_at:
        return "overview"
    return "none"


def platforms(o: Opportunity, cfg: dict | None) -> list:
    hints = (cfg or {}).get("platform_hints", [])
    t = (o.title + " " + o.organizer + " " + str(o.fact("themes").value or "") + " " + str(o.fact("description_text").value or "")).lower()
    return [h for h in hints if re.search(r"\b" + re.escape(h) + r"\b", t)][:3]


def estimate(o: Opportunity, cfg: dict | None = None) -> dict:
    text = opportunity_text(o)
    matches = match_templates(text)
    read = requirements_read(o)
    assumptions, risks = [], []
    human = ["read the official rules and confirm eligibility", "register/submit manually (the system never submits)"]
    deliv = o.fact("deliverables").value or []
    if read == "rules" and matches:
        lo, hi = by_id(matches[0]["id"])["effort_hours"]
        assumptions.append(f"rules read; template hypothesis '{matches[0]['id']}' range {lo}-{hi} h, plus detected deliverables")
    else:
        lo, hi = UNREAD_RANGE
        assumptions.append(f"requirements NOT read ({read}): generic prior {lo}-{hi} h; keyword template match is only a hypothesis and does not narrow the range")
        if matches:
            risks.append(f"template hypothesis '{matches[0]['id']}' comes from theme/title words only")
    if read != "none":
        for d in deliv:
            dl, dh = DELIV_HOURS.get(d, (0, 0))
            lo, hi = lo + dl, hi + dh
        if "demo_video" in deliv:
            human.append("record demo video")
        if "deployed_app" in deliv:
            human.append("deploy and keep a public URL alive")
    else:
        human.append("record demo video (typical requirement; unverified)")
        risks.append("deliverables (video, deployment, repository, write-up) unknown until the rules are read")
    plats = platforms(o, cfg)
    for p in plats:
        lo, hi = lo + PLATFORM_HOURS[0], hi + PLATFORM_HOURS[1]
        risks.append(f"names platform '{p}': mandatory use of its stack/API/credits is possible but unverified (accounts, credits, learning time)")
    kind = "prototype"
    if any(h in text for h in RESEARCH_HINTS) and matches and matches[0]["id"] == "research_report":
        kind = "research_deliverable"
    if any(h in text for h in PRODUCTION_HINTS):
        kind, lo, hi = "production_app", lo * 1.3, hi * 1.8
        risks.append("text suggests production-grade scope")
    if o.fact("token_or_wallet_required").value is True:
        risks.append("wallet/on-chain steps need a human and may involve costs")
    lo, hi = round(lo, 1), round(hi, 1)
    mid = round((lo + hi) / 2, 1)
    conf = {"none": "very_low", "overview": "low", "rules": "medium" if deliv else "low"}[read]
    parts = {"research": 0.12, "development": 0.55, "testing": 0.15, "deployment": 0.08, "video_docs": 0.10}
    return {"class": cls(mid), "class_low": cls(lo), "class_high": cls(hi), "class_range": f"{cls(lo)}-{cls(hi)}" if cls(lo) != cls(hi) else cls(lo),
            "hours_low": lo, "hours_mid": mid, "hours_high": hi, "total_hours": mid,
            "hours": {k: round(mid * v, 1) for k, v in parts.items()}, "hours_note": "split is indicative, applied to the mid estimate",
            "requirements_read": read, "deliverable_kind": kind, "template": matches[0]["id"] if matches else None, "template_is_hypothesis": True,
            "template_matches": matches, "platform_mentions": plats, "confidence": conf, "assumptions": assumptions, "risks": risks,
            "human_actions": human, "human_minutes_estimate": 45 + 15 * len(human)}
