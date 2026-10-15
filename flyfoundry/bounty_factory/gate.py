"""Deterministic eligibility gate. ELIGIBLE requires *positive* evidence; unknown never becomes eligible.

ELIGIBLE needs all of: deadline known and definitely in the future, fees confirmed absent, geography confirmed OK
(a human review record, or a human-entered fact). Hard rejects are INELIGIBLE with explicit reason codes."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .model import Opportunity

ELIGIBLE, INELIGIBLE, NEEDS_REVIEW = "ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"


def parse_dt(s: str):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d


def deadline_window(o: Opportunity):
    """(earliest_utc, latest_utc) the deadline can be, or None. Date-only deadlines with unknown tz span UTC+14 .. UTC-12."""
    f = o.fact("deadline_date")
    if not f.known():
        return None
    s = str(f.value)
    d = parse_dt(s)
    if d is None:
        return None
    if len(s) == 10:   # date only
        day = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        end_of_day_utc = day + timedelta(days=1)
        return end_of_day_utc - timedelta(hours=14), end_of_day_utc + timedelta(hours=12)
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc) - timedelta(hours=14), d.replace(tzinfo=timezone.utc) + timedelta(hours=12)
    return d.astimezone(timezone.utc), d.astimezone(timezone.utc)


def deadline_status(o: Opportunity, now: datetime) -> str:
    w = deadline_window(o)
    if w is None:
        return "unknown"
    lo, hi = w
    if now > hi:
        return "expired"
    if now > lo:
        return "ambiguous"
    return "open"


def _mentions(text: str, cfg: dict) -> bool:
    t = (text or "").lower()
    p = cfg["participant"]
    names = p["country_names"] + p["region_names"]
    return any(re.search(r"\b" + re.escape(n) + r"\b", t) for n in names) or bool(re.search(r"\b" + p["country_code"].lower() + r"\b", t))


def evaluate(o: Opportunity, cfg: dict, now: datetime, reviews: dict | None = None) -> dict:
    """Returns {'decision','reasons':[{code,level,detail}],'verified':bool}. level: hard (reject) | review (quarantine) | ok."""
    reasons = []

    def add(code, level, detail):
        reasons.append({"code": code, "level": level, "detail": detail})

    rv = (reviews or {}).get(o.id) or {}
    # --- deadline
    ds = deadline_status(o, now)
    if ds == "expired":
        add("deadline_expired", "hard", f"deadline {o.fact('deadline_date').value} is before the earliest possible end in any time zone ({o.fact('deadline_date').basis})")
    elif ds == "ambiguous":
        add("deadline_ambiguous", "review", "deadline falls on today/yesterday and the time zone is unknown: may or may not have passed")
    elif ds == "unknown":
        add("deadline_unknown", "review", "no deadline recorded")
    else:
        add("deadline_ok", "ok", f"deadline {o.fact('deadline_date').value} is in the future in every time zone")
    # --- invitation / closed
    if o.fact("invite_only").value is True:
        add("invite_only", "hard", "listing says invite only")
    if o.status == "unlisted":
        add("unlisted", "review", "no longer present in the latest complete source listing")
    # --- fees, paid tools, tokens
    fees = o.fact("fees_required")
    if rv.get("fees") == "none":
        add("fees_confirmed_none", "ok", f"human review {rv.get('reviewed_at', '?')}: no fees")
    elif fees.value is True and fees.basis != "unknown":
        add("fee_required", "hard", f"{fees.basis}: {fees.evidence[:200]}")
    elif fees.value is False and fees.basis in ("human_confirmed", "human_entered"):
        add("fees_confirmed_none", "ok", f"{fees.basis}: no fees")
    else:
        add("fees_unverified", "review", "no explicit evidence that participation is free")
    for name, code, msg in (("paid_tool_required", "paid_tool_required", "requires a paid tool/subscription/API"),
                            ("token_or_wallet_required", "wallet_or_token_required", "requires wallet signing / tokens / on-chain spend")):
        f = o.fact(name)
        if f.value is True and rv.get("override_" + name) is not True:
            add(code, "hard", f"{msg} ({f.basis}): {f.evidence[:200]}")
    # --- hardware
    hw = o.fact("hardware_required")
    if hw.known() and rv.get("hardware") != "available":
        add("hardware_unavailable", "hard", f"mentions hardware '{hw.value}', not in configured available_hardware {cfg.get('available_hardware')}")
    # --- employer conflict / merchants
    ec = o.fact("employer_conflict")
    head = (o.title + " " + o.organizer).lower()
    hit = [k for k in cfg.get("payments_domain_keywords", []) if re.search(r"\b" + re.escape(k), head)]
    if hit and not ec.known():
        from .model import Fact
        ec = Fact("title/organizer:" + hit[0], "inferred", "payments-domain keyword in title/organizer")
    if rv.get("employer_conflict") == "none":
        add("employer_conflict_cleared", "ok", "human review: no merchant contact or confidential employer data needed")
    elif ec.known():
        add("possible_employer_conflict", "review", f"keyword signal '{ec.value}' (payments/merchant domain): confirm no merchant contact or employer data is needed")
    # --- physical location
    loc = o.fact("location")
    lv = loc.value.get("location") if isinstance(loc.value, dict) else loc.value
    if loc.known() and str(lv).strip().lower() not in ("online", "") and rv.get("location") != "remote_ok":
        add("location_not_online", "review", f"listing location is '{lv}': may be in-person or hybrid (needs a human check; 'online' is the only value accepted without review)")
    # --- geography
    gtxt = o.fact("geo_restriction_text")
    if rv.get("geo") == "ok":
        add("geo_confirmed_ok", "ok", f"human review {rv.get('reviewed_at', '?')}: participant geography eligible")
    elif rv.get("geo") == "excluded" or o.fact("geo_eligible").value is False:
        add("geo_excluded", "hard", "human-recorded: configured geography is excluded")
    elif o.fact("geo_eligible").value is True and o.fact("geo_eligible").basis in ("human_confirmed", "human_entered"):
        add("geo_confirmed_ok", "ok", "human-entered: eligible")
    elif gtxt.known():
        excl = re.search(r"(not\s+open\s+to|void\s+in|excluded|ineligible|may\s+not|not\s+eligible)", str(gtxt.value), re.I)
        if excl and _mentions(str(gtxt.value), cfg):
            add("geo_excluded", "hard", f"exclusion wording mentions the configured geography: {str(gtxt.value)[:250]}")
        else:
            add("geo_unverified", "review", f"geographic wording present, needs a human read: {str(gtxt.value)[:250]}")
    else:
        add("geo_unverified", "review", "no statement about who may participate was recorded (location 'Online' is not an eligibility statement)")

    hard = [r for r in reasons if r["level"] == "hard"]
    review = [r for r in reasons if r["level"] == "review"]
    decision = INELIGIBLE if hard else (NEEDS_REVIEW if review else ELIGIBLE)
    return {"decision": decision, "reasons": reasons, "verified": decision == ELIGIBLE and bool(rv)}


def load_reviews(path) -> dict:
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return {}
    return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8")).get("reviews", []) if r.get("id")}
