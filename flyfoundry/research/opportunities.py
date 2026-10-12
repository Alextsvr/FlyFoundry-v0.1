"""Decode genomes into structured opportunity hypotheses and build the ranked, traceable list.

Everything produced here is a HYPOTHESIS from a synthetic benchmark. No sources,
competitors, customers or revenue are invented: those fields say "none" / "not
assessed" until a real evidence dataset is wired in (see docs/EVIDENCE_LAYER.md).
"""
from __future__ import annotations

import json
import math

import numpy as np

from ..evolution.lineage import OP_NAMES
from ..evaluation.fitness import pairwise
from .provenance import taxonomy_path

EVIDENCE_TIERS = ("synthetic_benchmark_score", "evidence_supported_hypothesis", "validated_customer_demand",
                  "actual_paying_customer", "real_collected_revenue")


def load_taxonomy() -> dict:
    return json.loads(taxonomy_path().read_text())


def _pick(values: list, x: float) -> str:
    return values[min(int(x * len(values)), len(values) - 1)]


def decode(x: np.ndarray, tax: dict) -> dict:
    capital = int(round(2000 * (math.exp(4 * x[4]) - 1) / (math.exp(4) - 1)))
    effort = round(40 * float(x[5]), 1)
    risk = "low" if x[11] < 0.33 else ("medium" if x[11] < 0.66 else "high")
    cust, prob, sol, rev = (_pick(tax[k], x[i]) for i, k in enumerate(("customer", "problem", "solution", "revenue")))
    return {
        "customer": cust, "problem": prob, "solution": sol, "revenue_mechanism": rev,
        "required_capital_eur_model_estimate": capital,
        "operational_effort_hours_per_week_model_estimate": effort,
        "claimed_demand_signal": round(float(x[8]), 2),
        "evidence_strength_in_genome": round(float(x[6]), 2),
        "differentiation_score": round(float(x[7]), 2),
        "channel": _pick(tax["channel"], x[9]),
        "automation_share_pct": int(round(100 * float(x[10]))),
        "risk_level": risk,
        "testable_assumptions": [
            f"A1: '{cust}' experience '{prob}' often enough to pay for a fix (frequency unknown).",
            f"A2: '{sol}' resolves it at an effort of ~{effort} h/week and ~EUR {capital} upfront.",
            f"A3: '{rev}' is an acceptable way for this customer to pay (willingness to pay unknown).",
        ],
        "principal_risks": [f"overall risk level in genome: {risk}",
                            "demand is an assumption, not an observation",
                            "competition not assessed"],
        "key": f"{cust}|{prob}|{sol}|{rev}",
    }


def next_validation_step(d: dict) -> str:
    return (f"Define one falsifiable test for A1 ('{d['customer']}' / '{d['problem']}'): find a public, "
            "legitimately accessible dataset or published source that measures how often this problem occurs "
            "(none identified yet), log it in the evidence registry with its URL and access date, and only then "
            "consider any customer contact (this system never performs outreach).")


def build_hypotheses(exp, top_n: int = 20) -> list[dict]:
    tax = load_taxonomy()
    world = exp.world
    cand: list[dict] = []
    for key, r in exp.runners.items():
        arch = r.arm.archive
        for n in arch.filled:
            x = arch.X[n].copy()
            owner, gen = int(arch.owner[n]), int(arch.gen[n])
            lin = r.arm.lineage
            row = lin.rows.get(owner)
            chain = lin.ancestry(owner)
            cand.append({
                "id": f"HYP-{r.arm_name.split('_')[0]}{r.arm_name.split('_')[1][:3].upper()}-s{r.seed_idx}-a{owner}-g{gen}",
                "arm": r.arm_name, "seed_idx": r.seed_idx, "agent_id": owner, "generation_found": gen + 1,
                "train_fitness": float(arch.fit[n]),
                "heldout_fixed_score": world.static_candidate_heldout(x),
                "x": x,
                "parent_agent_id": (row[0] if row else None),
                "creation_operator": (OP_NAMES.get(row[3]) if row else "pruned"),
                "ancestry_chain_length": len(chain), "ancestry_ids_head": chain[:6],
                "decoded": decode(x, tax),
            })
    cand.sort(key=lambda c: -c["heldout_fixed_score"])
    seen: dict[str, str] = {}
    out: list[dict] = []
    for c in cand:
        k = c["decoded"]["key"]
        if k in seen:
            continue
        seen[k] = c["id"]
        out.append(c)
        if len(out) >= top_n:
            break
    X = np.array([c["x"] for c in out]) if out else np.zeros((0, 12))
    dm = pairwise(X) if len(X) > 1 else np.zeros((len(X), len(X)))
    dup_counts: dict[str, int] = {}
    for c in cand:
        dup_counts[c["decoded"]["key"]] = dup_counts.get(c["decoded"]["key"], 0) + 1
    for i, c in enumerate(out):
        d = c["decoded"]
        others = np.delete(dm[i], i) if len(X) > 1 else np.array([])
        c.update({
            "evidence_tier": "synthetic_benchmark_score",
            "confidence": "LOW - synthetic benchmark score only; not real-world evidence",
            "sources": "none (synthetic benchmark; no external sources were consulted)",
            "competition": "not assessed (no competitive data in v0.1)",
            "novelty_assessment": (f"nearest other listed candidate at distance {others.min():.2f} (genome units); "
                                   f"the same decoded business model appeared {dup_counts[d['key']]}x across all arms/seeds"
                                   if len(others) else "single candidate"),
            "next_validation_step": next_validation_step(d),
            "hypothesis_vs_fact": "HYPOTHESIS. Verified facts: none. Revenue: EUR 0 / unknown.",
        })
        c["x"] = [round(float(v), 4) for v in c["x"]]
    return out
