"""Deterministic eligibility gate.

ELIGIBLE requires POSITIVE, current evidence for EVERY required condition (REQUIRED below). Unknown never becomes eligible.
A human review (schema 2) can confirm conditions; it is bound to the rules it checked (rules_ref), the participant
configuration (participant_hash) and expires (review_valid_days). A source fact that contradicts a review never disappears:
the decision becomes NEEDS_REVIEW and both sides are listed. Heuristic (weak) text signals only ever cause review, never rejection."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .model import Opportunity, HUMAN, sha256_text

ELIGIBLE, INELIGIBLE, NEEDS_REVIEW = "ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"
REQUIRED = ("deadline", "geography", "participation_format", "access", "age_team", "fees", "tools_and_costs", "hardware", "wallet", "conflicts")
REVIEW_STATUSES = ("ok", "not_applicable", "excluded")
SCHEMA = 2


def participant_hash(cfg: dict) -> str:
    """Hash of the configured participant (geography, hardware). A review is valid only for the configuration it was made under."""
    blob = json.dumps({"participant": cfg.get("participant", {}), "available_hardware": sorted(cfg.get("available_hardware", []))}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def evidence_hash(evidence: str) -> str:
    return sha256_text(evidence or "")[:16]


def parse_dt(s: str):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def deadline_window(o: Opportunity):
    """(earliest_utc, latest_utc) the deadline can be, or None. Date-only deadlines with unknown tz span UTC+14 .. UTC-12."""
    f = o.fact("deadline_date")
    if not f.known():
        return None
    s = str(f.value)
    d = parse_dt(s)
    if d is None:
        return None
    if len(s) == 10:
        day = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        end = day + timedelta(days=1)
        return end - timedelta(hours=14), end + timedelta(hours=12)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
        return d - timedelta(hours=14), d + timedelta(hours=12)
    return d.astimezone(timezone.utc), d.astimezone(timezone.utc)


def deadline_status(o: Opportunity, now: datetime) -> str:
    w = deadline_window(o)
    if w is None:
        return "unknown"
    lo, hi = w
    return "expired" if now > hi else ("ambiguous" if now > lo else "open")


def load_reviews(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8")).get("reviews", []) if r.get("id")}


def review_problems(rv: dict, o: Opportunity, cfg: dict, now: datetime) -> list:
    """Reasons a review cannot be relied on (list of (code, detail)). Empty = the review is current and linked to the right rules/participant."""
    out = []
    if rv.get("schema") != SCHEMA:
        return [("review_legacy_incomplete", "legacy review format (fees/geo flags without linked rules, participant or per-condition evidence); kept on file, a new review is required")]
    t = parse_dt(rv.get("reviewed_at", ""))
    if t is None:
        out.append(("review_incomplete", "reviewed_at missing or unparsable"))
    else:
        t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        days = cfg.get("review_valid_days", 14)
        if now - t > timedelta(days=days):
            out.append(("review_stale", f"reviewed {rv.get('reviewed_at')}, older than review_valid_days={days}"))
    if not str(rv.get("evidence_url", "")).strip():
        out.append(("review_incomplete", "evidence_url missing"))
    ref = str(rv.get("rules_ref", "")).strip()
    if not ref:
        out.append(("review_incomplete", "rules_ref (rules hash or version/date of the rules that were read) missing"))
    if rv.get("participant_hash") != participant_hash(cfg):
        out.append(("review_participant_changed", f"review made for participant config {rv.get('participant_hash')}, current is {participant_hash(cfg)}"))
    cur_hash = o.fact("rules_hash")
    if cur_hash.known() and ref and cur_hash.value not in ref:
        out.append(("review_rules_changed", f"rules text hash now {cur_hash.value[:12]}..., review references '{ref[:60]}'"))
    return out


def _conditions(o: Opportunity, cfg: dict, now: datetime, rv: dict | None, rv_ok: bool) -> dict:
    """Per-condition state: {cond: {status, detail}}; status in confirmed|not_applicable|unknown|violated|contradicted."""
    st = {}
    hw_avail = set(cfg.get("available_hardware", []))
    rc = (rv or {}).get("conditions", {}) if rv_ok else {}
    ack = {(a.get("fact"), a.get("evidence_sha256")) for a in (rv or {}).get("acknowledged_signals", [])} if rv_ok else set()

    def signal(name):
        f = o.fact(name)
        return f if f.known() and f.strength != "weak" else None       # weak text signals prompt a review but never contradict one

    def human_fact(name, expect):
        f = o.fact(name)
        return f.known() and f.basis in HUMAN and f.value == expect

    def review_cond(cond):
        c = rc.get(cond)
        if not c:
            return None
        if c.get("status") not in REVIEW_STATUSES:
            return None
        if c["status"] == "not_applicable" and len(str(c.get("note", "")).strip()) < 10:
            return ("incomplete", "not_applicable needs a justification note (>= 10 chars)")
        return (c["status"], str(c.get("note", "")))

    def contradiction(fact_names, bad):
        """first source fact (not acknowledged by the review) that contradicts a confirmation"""
        for n in fact_names:
            f = signal(n)
            if f is not None and bad(f) and (n, evidence_hash(f.evidence)) not in ack:
                return n, f
        return None

    def decide(cond, fact_names, bad, auto=None, human_ok=None):
        rcond = review_cond(cond)
        bad_hit = contradiction(fact_names, bad)
        conflicts = [(n, c) for n in fact_names for c in o.fact(n).conflicts] if human_ok else []
        if rcond and rcond[0] == "excluded":
            return {"status": "violated", "detail": f"review says excluded: {rcond[1]}"}
        if human_ok and human_ok():
            if conflicts:
                return {"status": "contradicted", "detail": "human-entered fact vs newer source claim: " + "; ".join(f"{n}: human={o.fact(n).value!r} source={c['value']!r} ({c['evidence'][:100]})" for n, c in conflicts)}
            return {"status": "confirmed", "detail": "human fact"}
        if rcond and rcond[0] in ("ok", "not_applicable"):
            if bad_hit:
                n, f = bad_hit
                return {"status": "contradicted", "detail": f"review ({rv.get('reviewed_at')}) says {rcond[0]}: '{rcond[1][:80]}' BUT source fact {n}={f.value!r} [{f.basis}/{f.strength or 'explicit'}, observed {f.observed_at}] evidence: {f.evidence[:160]}"}
            return {"status": "confirmed" if rcond[0] == "ok" else "not_applicable", "detail": f"review {rv.get('reviewed_at')}: {rcond[1][:120]}"}
        if rcond and rcond[0] == "incomplete":
            return {"status": "unknown", "detail": rcond[1]}
        if auto:
            r = auto()
            if r:
                return r
        return {"status": "unknown", "detail": "no valid confirmation on record"}

    ds = deadline_status(o, now)
    rd = (rv or {}).get("conditions", {}).get("deadline", {}).get("value") if rv_ok else None
    if ds == "open":
        st["deadline"] = {"status": "confirmed", "detail": f"source claim {o.fact('deadline_date').value}, in the future in every time zone"}
        if rd and str(rd)[:10] != str(o.fact("deadline_date").value)[:10]:
            st["deadline"] = {"status": "contradicted", "detail": f"review confirmed deadline {rd}, source now says {o.fact('deadline_date').value}"}
    elif ds == "expired":
        st["deadline"] = {"status": "violated", "detail": f"deadline {o.fact('deadline_date').value} has passed in every time zone"}
    elif ds == "ambiguous":
        st["deadline"] = {"status": "unknown", "detail": "deadline falls on today/yesterday and the time zone is unknown"}
    else:
        st["deadline"] = {"status": "unknown", "detail": "no deadline recorded"}

    def geo_bad(f):
        return f.value is False if f is o.fact("geo_eligible") else f.value is True
    st["geography"] = decide("geography", ("geo_eligible", "geo_excludes_participant"), geo_bad, human_ok=lambda: human_fact("geo_eligible", True))
    loc = o.fact("location")
    lv = loc.value.get("location") if isinstance(loc.value, dict) else loc.value
    st["participation_format"] = decide("participation_format", ("location",), lambda f: str((f.value.get("location") if isinstance(f.value, dict) else f.value)).strip().lower() not in ("online", ""),
                                        auto=lambda: {"status": "confirmed", "detail": "source claim: location 'Online'"} if loc.known() and str(lv).strip().lower() == "online" else None)
    inv = o.fact("invite_only")
    st["access"] = decide("access", ("invite_only",), lambda f: f.value is True,
                          auto=lambda: {"status": "confirmed", "detail": "source claim: not invite-only"} if inv.known() and inv.value is False else None)
    st["age_team"] = decide("age_team", (), lambda f: False)
    st["fees"] = decide("fees", ("fees_required",), lambda f: f.value is True, human_ok=lambda: human_fact("fees_required", False))
    st["tools_and_costs"] = decide("tools_and_costs", ("paid_tool_required",), lambda f: f.value is True, human_ok=lambda: human_fact("paid_tool_required", False))

    def hw_bad(f):
        return isinstance(f.value, list) and bool(set(f.value) - hw_avail)
    st["hardware"] = decide("hardware", ("hardware_required",), hw_bad, human_ok=lambda: human_fact("hardware_required", False))
    st["wallet"] = decide("wallet", ("token_or_wallet_required",), lambda f: f.value is True, human_ok=lambda: human_fact("token_or_wallet_required", False))
    st["conflicts"] = decide("conflicts", (), lambda f: False)
    return st


def evaluate(o: Opportunity, cfg: dict, now: datetime, reviews: dict | None = None) -> dict:
    """-> {decision, reasons[{code,level,detail}], conditions, conditions_confirmed, conditions_total, review_status, verified}.
    level: hard (reject) | review (quarantine) | ok."""
    reasons = []

    def add(code, level, detail):
        reasons.append({"code": code, "level": level, "detail": detail})

    rv = (reviews or {}).get(o.id)
    problems = review_problems(rv, o, cfg, now) if rv else []
    rv_ok = bool(rv) and not problems
    review_status = "none" if not rv else ("complete" if rv_ok else problems[0][0])
    for code, detail in problems:
        add(code, "review", detail)
    cond = _conditions(o, cfg, now, rv, rv_ok)

    # ---- hard rejects (firm evidence only; a valid review that acknowledged the exact signal clears it)
    ack = {(a.get("fact"), a.get("evidence_sha256")) for a in (rv or {}).get("acknowledged_signals", [])} if rv_ok else set()

    def firm(name):
        f = o.fact(name)
        return f if f.known() and f.strength != "weak" else None

    def weak(name):
        f = o.fact(name)
        return f if f.known() and f.strength == "weak" else None

    def acked(name):
        f = o.fact(name)
        return (name, evidence_hash(f.evidence)) in ack

    if cond["deadline"]["status"] == "violated":
        add("deadline_expired", "hard", cond["deadline"]["detail"])
    if o.fact("invite_only").value is True:
        add("invite_only", "hard", "listing says invite only")
    if o.status == "unlisted":
        add("unlisted", "review", "no longer present in the latest complete source listing")
    if cond["geography"]["status"] == "violated":
        add("geo_excluded", "hard", cond["geography"]["detail"])
    for name, code, msg, bad in (("fees_required", "fee_required", "fee/deposit/token purchase required", lambda f: f.value is True),
                                 ("paid_tool_required", "paid_tool_required", "requires a paid tool/subscription/API", lambda f: f.value is True),
                                 ("token_or_wallet_required", "wallet_or_token_required", "requires wallet signing / on-chain spend", lambda f: f.value is True)):
        f = firm(name)
        w = weak(name)
        if f is not None and bad(f) and not acked(name):
            if rv_ok and cond[{"fees_required": "fees", "paid_tool_required": "tools_and_costs", "token_or_wallet_required": "wallet"}[name]]["status"] == "contradicted":
                continue            # handled as a review conflict below (both sides kept)
            add(code, "hard", f"{msg} ({f.basis}, {f.origin or 'structured'}): {f.evidence[:200]}")
        elif w is not None and bad(w) and not acked(name):
            add("weak_signal_" + name, "review", f"unreliable text signal, needs a human read: {w.evidence[:200]}")
    hw = o.fact("hardware_required")
    if hw.known() and isinstance(hw.value, list) and not acked("hardware_required"):
        missing = sorted(set(hw.value) - set(cfg.get("available_hardware", [])))
        if missing and hw.strength != "weak" and cond["hardware"]["status"] != "contradicted":
            add("hardware_unavailable", "hard", f"requires {missing}, not in available_hardware {cfg.get('available_hardware')}: {hw.evidence[:160]}")
        elif missing:
            add("weak_signal_hardware_required", "review", f"hardware mentioned {missing}; unclear whether mandatory: {hw.evidence[:200]}")
    g_ex, g_in = o.fact("geo_excludes_participant"), o.fact("geo_includes_participant")
    if g_ex.known() and g_ex.value is True and not acked("geo_excludes_participant") and cond["geography"]["status"] != "contradicted":
        if g_ex.strength != "weak" and not g_in.known():
            add("geo_excluded", "hard", f"exclusion wording names the configured geography: {g_ex.evidence[:200]}")
        else:
            add("geo_contradictory_or_unclear", "review", f"exclusion wording vs inclusion/exception wording about the configured geography: {g_ex.evidence[:160]}" + (f" || {g_in.evidence[:100]}" if g_in.known() else ""))

    # ---- review conflicts, unknowns, quarantines
    for c, s in cond.items():
        if s["status"] == "contradicted":
            add(f"review_conflict:{c}", "review", s["detail"])
    if cond["deadline"]["status"] == "unknown":
        add("deadline_ambiguous" if o.fact("deadline_date").known() else "deadline_unknown", "review", cond["deadline"]["detail"])
    elif cond["deadline"]["status"] == "confirmed":
        add("deadline_ok", "ok", cond["deadline"]["detail"])
    for c in ("geography", "participation_format", "access", "age_team", "fees", "tools_and_costs", "hardware", "wallet", "conflicts"):
        s = cond[c]
        if s["status"] == "unknown":
            add({"fees": "fees_unverified", "geography": "geo_unverified"}.get(c, f"unconfirmed:{c}"), "review", f"{c}: {s['detail']}")
        elif s["status"] in ("confirmed", "not_applicable") and c in ("fees", "geography"):
            add({"fees": "fees_confirmed_none", "geography": "geo_confirmed_ok"}[c], "ok", s["detail"])
    fm = o.fact("location")
    if cond["participation_format"]["status"] == "contradicted":
        pass
    elif fm.known() and cond["participation_format"]["status"] == "unknown":
        lv = fm.value.get("location") if isinstance(fm.value, dict) else fm.value
        add("location_not_online", "review", f"listing location is '{lv}': may be in-person or hybrid (needs a human check)")
    head = (o.title + " " + o.organizer).lower()
    hit = [k for k in cfg.get("payments_domain_keywords", []) if re.search(r"\b" + re.escape(k), head)]
    ec = o.fact("employer_conflict")
    if (hit or ec.known()) and cond["conflicts"]["status"] != "confirmed" and cond["conflicts"]["status"] != "not_applicable":
        add("possible_employer_conflict", "review", f"payments-domain signal ({hit[0] if hit else ec.value}): confirm no merchant contact or employer data is needed")
    for n, f in o.facts.items():
        if f.conflicts and f.basis in HUMAN:
            add(f"fact_conflict:{n}", "review", f"human fact {f.value!r} [{f.basis}] vs source claims {[c['value'] for c in f.conflicts]}")
    if o.possible_duplicates:
        add("possible_duplicate", "review", f"may be the same event as {o.possible_duplicates[:3]} (title+organizer match without matching deadline); not merged")

    hard = [r for r in reasons if r["level"] == "hard"]
    review = [r for r in reasons if r["level"] == "review"]
    not_confirmed = [c for c, s in cond.items() if s["status"] not in ("confirmed", "not_applicable")]
    decision = INELIGIBLE if hard else (NEEDS_REVIEW if (review or not_confirmed) else ELIGIBLE)
    confirmed = sum(1 for s in cond.values() if s["status"] in ("confirmed", "not_applicable"))
    return {"decision": decision, "reasons": reasons, "conditions": cond, "conditions_confirmed": confirmed, "conditions_total": len(REQUIRED),
            "review_status": review_status, "verified": decision == ELIGIBLE}
