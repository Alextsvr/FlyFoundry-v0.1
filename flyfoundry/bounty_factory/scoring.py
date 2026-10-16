"""Explainable ranking. Three separate things are reported and must not be conflated:
  * criteria_fill      - share of ranking-criteria weight that has a value (heuristics included). NOT evidence completeness.
  * conditions         - how many REQUIRED eligibility conditions are confirmed (gate.py).
  * provenance/effort  - which facts are source claims vs inferred, and the confidence of the effort estimate.
Baseline A = declared prize pool per estimated hour (a ratio, not expected income). Experimental B = weighted criteria.
review_priority orders human review work; development_priority exists only for ELIGIBLE opportunities."""
from __future__ import annotations

import math
import re
import random
from datetime import datetime

from .gate import deadline_window
from .model import Opportunity
from .templates import match_templates

CRITERIA = ("reward_amount", "prize_count", "technical_fit", "estimated_time", "deadline_feasibility", "competition_intensity",
            "deliverable_complexity", "free_resources", "reusability", "requirements_quality", "human_involvement")
A_DEFINITION = "declared prize pool (planning USD) divided by the mid effort estimate in hours; a ratio of claims, NOT expected income or win probability"


def prize_usd(o: Opportunity, cfg: dict):
    a, c = o.fact("prize_amount"), o.fact("prize_currency")
    if not a.known():
        return None
    rate = cfg["fx_to_usd_planning"].get(c.value) if c.known() else None
    return None if rate is None else float(a.value) * rate


def criteria(o: Opportunity, est: dict, cfg: dict, now: datetime, hours: float | None = None) -> dict:
    """crit[name] = (value in [0,1] or None, note, basis) with basis in source_claim|heuristic|estimate|unknown.
    None = unknown (excluded from the weighted mean, never guessed). `hours` overrides the mid estimate (scenario analysis)."""
    out = {}
    h = hours if hours is not None else est["hours_mid"]
    usd = prize_usd(o, cfg)
    out["reward_amount"] = (None, "prize unknown or currency not convertible", "unknown") if usd is None else (min(1.0, math.log10(1 + usd) / math.log10(1 + 10000)), f"{usd:.0f} USD planning value of the declared pool", "source_claim")
    pc = o.fact("prize_count")
    out["prize_count"] = (None, "unknown", "unknown") if not pc.known() else (min(1.0, float(pc.value) / 5.0), f"{pc.value} cash prize(s)", "source_claim")
    text = " ".join([o.title, str(o.fact("themes").value or ""), str(o.fact("description_text").value or "")]).lower()
    pos = [k for k in cfg["tech_keywords"] if k in text]
    neg = [k for k in cfg["tech_negative_keywords"] if k in text]
    out["technical_fit"] = (max(0.0, min(1.0, 0.3 + 0.15 * len(pos) - 0.25 * len(neg))), f"+{pos[:5]} -{neg[:5]} (keyword heuristic)", "heuristic")
    out["estimated_time"] = (max(0.0, 1 - min(1.0, math.log10(max(h, 1.0)) / math.log10(80))), f"~{h} h (range {est['hours_low']}-{est['hours_high']}, confidence {est['confidence']})", "estimate")
    w = deadline_window(o)
    if w is None:
        out["deadline_feasibility"] = (None, "no deadline", "unknown")
    else:
        days = max(0.0, (w[0] - now).total_seconds() / 86400)
        need = h / max(0.5, cfg["hours_per_day_available"])
        out["deadline_feasibility"] = (max(0.0, min(1.0, (days / need - 1.0) / 2.0)) if need else 1.0, f"{days:.1f} days left (earliest case) vs {need:.1f} working days at ~{h} h (uses the same hour estimate as estimated_time)", "estimate")
    rc = o.fact("registrations_count")
    out["competition_intensity"] = (None, "unknown", "unknown") if not rc.known() else (1 - min(1.0, math.log10(1 + float(rc.value)) / math.log10(1 + 5000)), f"{rc.value} registrations (participant count, NOT a win probability)", "source_claim")
    deliv = o.fact("deliverables").value or []
    if est["requirements_read"] == "none":
        out["deliverable_complexity"] = (None, "requirements not read", "unknown")
    else:
        n = len(deliv) + len(est["platform_mentions"])
        out["deliverable_complexity"] = (max(0.0, 1.0 - n / 6.0), f"{len(deliv)} deliverable signals + {len(est['platform_mentions'])} platform mentions", "heuristic")
    out["free_resources"] = (None, "a free template match does not prove the contest's mandatory stack is free; unknown", "unknown")
    m = match_templates(text)
    out["reusability"] = (min(1.0, (m[0]["overlap"] * 3) if m else 0.0), f"best template overlap {m[0]['id'] if m else 'none'} (hypothesis)", "heuristic")
    known = sum(1 for n in ("deadline_date", "prize_amount", "geo_restriction_text", "deliverables", "submission_method") if o.fact(n).known())
    out["requirements_quality"] = (known / 5.0, f"{known}/5 key requirement fields known", "source_claim")
    out["human_involvement"] = (max(0.0, 1.0 - len(est["human_actions"]) / 8.0), f"{len(est['human_actions'])} human actions", "estimate")
    return out


def score_b(crit: dict, weights: dict) -> dict:
    known = {k: v[0] for k, v in crit.items() if v[0] is not None and weights.get(k, 0) > 0}
    wsum, allw = sum(weights[k] for k in known), sum(weights.values())
    if wsum <= 0:
        return {"score": 0.0, "criteria_fill": 0.0, "contributions": {}, "unknown": sorted(crit), "basis_share": {}}
    fill = wsum / allw
    base = sum(weights[k] * v for k, v in known.items()) / wsum
    share = {}
    for k in known:
        share[crit[k][2]] = round(share.get(crit[k][2], 0.0) + weights[k] / wsum, 4)
    return {"score": round(base * (0.5 + 0.5 * fill), 6), "criteria_fill": round(fill, 4),
            "contributions": {k: round(weights[k] * v / wsum, 6) for k, v in known.items()},
            "unknown": sorted(k for k in crit if k not in known), "basis_share": share}


def baseline_a(o: Opportunity, est: dict, cfg: dict):
    usd = prize_usd(o, cfg)
    return None if usd is None else usd / max(est["hours_mid"], 0.5)


def review_priority(o: Opportunity, est: dict, gate: dict, cfg: dict, now: datetime) -> dict:
    """Which opportunity deserves a human's review time FIRST (not which to build).
    rp = (0.6 * reward + 0.4 * time_slack) * blockers; reward = log-scaled declared pool (unknown -> 0); time_slack = days left
    (earliest case) / 14 capped at 1, and 0.3 * days/3 when fewer than 3 days remain; blockers multiply by 0.5 for each of: not-online
    location signal, possible employer conflict, possible duplicate, hardware/engine keyword in title or themes (tech_negative_keywords). Rejected opportunities get None."""
    if gate["decision"] == "INELIGIBLE":
        return {"value": None, "formula": "n/a (rejected)"}
    usd = prize_usd(o, cfg)
    reward = 0.0 if usd is None else min(1.0, math.log10(1 + usd) / math.log10(1 + 10000))
    w = deadline_window(o)
    days = 0.0 if w is None else max(0.0, (w[0] - now).total_seconds() / 86400)
    slack = min(1.0, days / 14) if days >= 3 else 0.3 * days / 3
    codes = {r["code"] for r in gate["reasons"]}
    n_block = sum(1 for c in ("location_not_online", "possible_employer_conflict", "possible_duplicate") if c in codes)
    head = (o.title + " " + str(o.fact("themes").value or "")).lower()
    neg = [k for k in cfg.get("tech_negative_keywords", []) if re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", head)]
    if neg:
        n_block += 1                       # title/themes point at hardware or an engine the participant does not use (hypothesis, needs a read)
    mult = 0.5 ** n_block
    return {"value": round((0.6 * reward + 0.4 * slack) * mult, 4), "reward": round(reward, 3), "days_left_earliest": round(days, 1), "multiplier": mult, "tech_mismatch_keywords": neg}


def rank(ids_scores: dict) -> list:
    """Deterministic ordering: score desc (None last), id asc."""
    return sorted(ids_scores, key=lambda i: (ids_scores[i] is None, -(ids_scores[i] or 0.0), i))


def sensitivity(crits: dict, weights: dict, n: int = 300, seed: int = 20261015, k: int = 3, spread: float = 0.5) -> dict:
    """Weight perturbation only: checks how fragile the ordering is to the chosen weights. It does NOT validate that the ranking is good."""
    ids = sorted(crits)
    if not ids:
        return {"n": n, "per_opportunity": {}, "top_k": k, "stable_top": [], "unstable": [], "scope": "weights only"}
    rng = random.Random(seed)
    ranks, topk = {i: [] for i in ids}, {i: 0 for i in ids}
    base_rank = {i: r for r, i in enumerate(rank({i: score_b(crits[i], weights)["score"] for i in ids}), 1)}
    for _ in range(n):
        w = {c: weights[c] * rng.uniform(1 - spread, 1 + spread) for c in weights}
        for r, i in enumerate(rank({i: score_b(crits[i], w)["score"] for i in ids}), 1):
            ranks[i].append(r)
            if r <= k:
                topk[i] += 1
    per = {i: {"base_rank": base_rank[i], "min_rank": min(ranks[i]), "max_rank": max(ranks[i]), "top_k_freq": round(topk[i] / n, 3)} for i in ids}
    return {"n": n, "seed": seed, "spread": spread, "top_k": k, "per_opportunity": per, "stable_top": [i for i in ids if per[i]["top_k_freq"] >= 0.8],
            "unstable": [i for i in ids if 0.2 <= per[i]["top_k_freq"] < 0.8], "scope": "weights only; does not validate ranking quality"}


def effort_scenarios(items: dict, cfg: dict, now: datetime, k: int = 3) -> dict:
    """items: id -> (opp, est). Re-ranks under low / mid / high effort. Unknown eligibility-critical conditions are NOT scenario-tested
    here (they are handled by the gate and by review_priority)."""
    if not items:
        return {"scenarios": [], "per_opportunity": {}, "top_k": k, "top_set_stable": None}
    res = {}
    for name, key in (("effort_low", "hours_low"), ("effort_mid", "hours_mid"), ("effort_high", "hours_high")):
        sc = {i: score_b(criteria(o, e, cfg, now, hours=e[key]), cfg["weights"])["score"] for i, (o, e) in items.items()}
        res[name] = {i: r for r, i in enumerate(rank(sc), 1)}
    per = {i: {"ranks": {s: res[s][i] for s in res}, "min_rank": min(res[s][i] for s in res), "max_rank": max(res[s][i] for s in res)} for i in items}
    tops = [frozenset(i for i, r in res[s].items() if r <= k) for s in res]
    return {"scenarios": list(res), "per_opportunity": per, "top_k": k, "top_set_stable": len(set(tops)) == 1}


def kendall_tau(a: list, b: list) -> float | None:
    common = [x for x in a if x in set(b)]
    if len(common) < 2:
        return None
    pa, pb = {x: i for i, x in enumerate(a)}, {x: i for i, x in enumerate(b)}
    c = d = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            s = (pa[common[i]] - pa[common[j]]) * (pb[common[i]] - pb[common[j]])
            c += s > 0
            d += s < 0
    return round((c - d) / (c + d), 4) if c + d else None
