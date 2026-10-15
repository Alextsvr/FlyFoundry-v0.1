"""Explainable ranking. Baseline A: prize per estimated hour (deterministic). Experimental B: weighted criteria with unknowns
excluded and reported. Sensitivity analysis perturbs weights; no win probabilities are ever produced."""
from __future__ import annotations

import math
import random
from datetime import datetime

from .gate import deadline_window
from .model import Opportunity
from .templates import match_templates

CRITERIA = ("reward_amount", "prize_count", "technical_fit", "estimated_time", "deadline_feasibility", "competition_intensity",
            "deliverable_complexity", "free_resources", "reusability", "requirements_quality", "human_involvement")
CLASS_TIME = {"MICRO": 1.0, "SMALL": 0.75, "MEDIUM": 0.4, "LARGE": 0.1}
CLASS_COMPLEX = {"MICRO": 0.9, "SMALL": 0.7, "MEDIUM": 0.4, "LARGE": 0.1}


def prize_usd(o: Opportunity, cfg: dict):
    a, c = o.fact("prize_amount"), o.fact("prize_currency")
    if not a.known():
        return None
    rate = cfg["fx_to_usd_planning"].get(c.value) if c.known() else None
    return None if rate is None else float(a.value) * rate


def criteria(o: Opportunity, est: dict, cfg: dict, now: datetime) -> dict:
    """Each criterion -> (value in [0,1] or None, note). None = unknown (excluded, never guessed)."""
    out = {}
    usd = prize_usd(o, cfg)
    out["reward_amount"] = (None, "prize unknown or currency not convertible") if usd is None else (min(1.0, math.log10(1 + usd) / math.log10(1 + 10000)), f"{usd:.0f} USD planning value")
    pc = o.fact("prize_count")
    out["prize_count"] = (None, "unknown") if not pc.known() else (min(1.0, float(pc.value) / 5.0), f"{pc.value} cash prize(s)")
    text = " ".join([o.title, str(o.fact("themes").value or ""), str(o.fact("description_text").value or "")]).lower()
    has_text = bool(o.fact("themes").known() or o.fact("description_text").known() or o.title)
    if not has_text:
        out["technical_fit"] = (None, "no text")
    else:
        pos = [k for k in cfg["tech_keywords"] if k in text]
        neg = [k for k in cfg["tech_negative_keywords"] if k in text]
        out["technical_fit"] = (max(0.0, min(1.0, 0.3 + 0.15 * len(pos) - 0.25 * len(neg))), f"+{pos[:5]} -{neg[:5]} (keyword heuristic)")
    out["estimated_time"] = (CLASS_TIME[est["class"]], f"{est['class']} ~{est['total_hours']} h (confidence {est['confidence']})")
    w = deadline_window(o)
    if w is None:
        out["deadline_feasibility"] = (None, "no deadline")
    else:
        days = max(0.0, (w[0] - now).total_seconds() / 86400)
        need_days = est["total_hours"] / max(0.5, cfg["hours_per_day_available"])
        ratio = days / need_days if need_days else 9
        out["deadline_feasibility"] = (max(0.0, min(1.0, (ratio - 1.0) / 2.0)), f"{days:.1f} days left (earliest case) vs {need_days:.1f} working days needed")
    rc = o.fact("registrations_count")
    out["competition_intensity"] = (None, "unknown") if not rc.known() else (1 - min(1.0, math.log10(1 + float(rc.value)) / math.log10(1 + 5000)), f"{rc.value} registrations (participant count, NOT a win probability)")
    out["deliverable_complexity"] = (CLASS_COMPLEX[est["class"]], f"derived from class {est['class']}")
    fr = None
    if o.fact("paid_tool_required").value is True or o.fact("hardware_required").known():
        fr = 0.0
    elif has_text and est.get("template"):
        fr = 0.8
    out["free_resources"] = (fr, "template matches free stack" if fr == 0.8 else ("paid tool/hardware signal" if fr == 0.0 else "unknown"))
    m = match_templates(text or "")
    out["reusability"] = (None, "no text") if not has_text else (min(1.0, (m[0]["overlap"] * 3) if m else 0.0), f"best template overlap {m[0]['id'] if m else 'none'}")
    known = sum(1 for n in ("deadline_date", "prize_amount", "geo_restriction_text", "deliverables", "submission_method") if o.fact(n).known())
    out["requirements_quality"] = (known / 5.0, f"{known}/5 key requirement fields known")
    out["human_involvement"] = (max(0.0, 1.0 - len(est["human_actions"]) / 8.0), f"{len(est['human_actions'])} human actions")
    return out


def score_b(crit: dict, weights: dict) -> dict:
    known = {k: v[0] for k, v in crit.items() if v[0] is not None}
    wsum = sum(weights[k] for k in known)
    allw = sum(weights.values())
    if wsum <= 0:
        return {"score": 0.0, "coverage": 0.0, "contributions": {}, "unknown": sorted(crit)}
    cov = wsum / allw
    base = sum(weights[k] * v for k, v in known.items()) / wsum
    return {"score": round(base * (0.5 + 0.5 * cov), 6), "coverage": round(cov, 4),
            "contributions": {k: round(weights[k] * v / wsum, 6) for k, v in known.items()},
            "unknown": sorted(k for k in crit if k not in known)}


def baseline_a(o: Opportunity, est: dict, cfg: dict) -> float | None:
    usd = prize_usd(o, cfg)
    return None if usd is None else usd / max(est["total_hours"], 0.5)


def rank(ids_scores: dict) -> list:
    """Deterministic ordering: score desc (None last), id asc."""
    return sorted(ids_scores, key=lambda i: (ids_scores[i] is None, -(ids_scores[i] or 0.0), i))


def sensitivity(crits: dict, weights: dict, n: int = 300, seed: int = 20261015, k: int = 3, spread: float = 0.5) -> dict:
    """Multiply each weight by U(1-spread, 1+spread); record rank ranges and top-k membership frequency."""
    ids = sorted(crits)
    if not ids:
        return {"n": n, "per_opportunity": {}, "top_k": k, "stable_top": [], "unstable": []}
    rng = random.Random(seed)
    ranks = {i: [] for i in ids}
    topk = {i: 0 for i in ids}
    base_rank = {i: r for r, i in enumerate(rank({i: score_b(crits[i], weights)["score"] for i in ids}), 1)}
    for _ in range(n):
        w = {c: weights[c] * rng.uniform(1 - spread, 1 + spread) for c in weights}
        order = rank({i: score_b(crits[i], w)["score"] for i in ids})
        for r, i in enumerate(order, 1):
            ranks[i].append(r)
            if r <= k:
                topk[i] += 1
    per = {i: {"base_rank": base_rank[i], "min_rank": min(ranks[i]), "max_rank": max(ranks[i]), "top_k_freq": round(topk[i] / n, 3)} for i in ids}
    stable = [i for i in ids if per[i]["top_k_freq"] >= 0.8]
    unstable = [i for i in ids if 0.2 <= per[i]["top_k_freq"] < 0.8]
    return {"n": n, "seed": seed, "spread": spread, "top_k": k, "per_opportunity": per, "stable_top": stable, "unstable": unstable}


def kendall_tau(a: list, b: list) -> float | None:
    common = [x for x in a if x in set(b)]
    if len(common) < 2:
        return None
    pa = {x: i for i, x in enumerate(a)}
    pb = {x: i for i, x in enumerate(b)}
    c = d = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            s = (pa[common[i]] - pa[common[j]]) * (pb[common[i]] - pb[common[j]])
            c += s > 0
            d += s < 0
    return round((c - d) / (c + d), 4) if c + d else None
