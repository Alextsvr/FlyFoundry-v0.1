"""Aggregation, bootstrap statistics and the conservative auto-generated conclusions."""
from __future__ import annotations

import numpy as np

from ..evaluation.stats import bootstrap_mean_ci, paired_diff_ci

METRICS = [  # key, label, higher_is_better, kind
    ("heldout_qd", "Held-out quality-diversity score", True, "heldout"),
    ("heldout_best", "Held-out best candidate score", True, "heldout"),
    ("heldout_discovery", "Held-out peak discovery rate", True, "heldout"),
    ("f_best", "Train best-of-generation fitness", True, "train"),
    ("f_mean", "Train mean fitness", True, "train"),
    ("discovered", "Distinct real peaks discovered (train)", True, "train"),
    ("niches_viable", "Viable niches (archive)", True, "train"),
    ("diversity", "Population diversity", True, "diversity"),
    ("novelty", "Novelty", True, "diversity"),
]
PRIMARY = "heldout_qd"
BASE_ARM = "A_fly_plastic"


def series(exp, arm: str, key: str) -> np.ndarray:
    """(n_seeds, n_gens) array of a history metric."""
    rows = [[h[key] for h in r.history] for r in exp.runners.values() if r.arm_name == arm]
    return np.array(rows, dtype=float)


def final_values(exp, arm: str, key: str, last_k: int = 5) -> np.ndarray:
    """Per-seed value averaged over the last `last_k` generations (smooths single-generation noise)."""
    s = series(exp, arm, key)
    return s[:, -last_k:].mean(axis=1) if s.size else np.array([])


def analyze(exp) -> dict:
    cfg = exp.cfg
    n_res = cfg.bootstrap_resamples
    out: dict = {"generation": exp.generation, "n_seeds": cfg.n_seeds, "arms": {}, "paired": [], "metrics": METRICS}
    for arm in cfg.arms:
        a: dict = {"metrics": {}}
        for key, *_ in METRICS:
            v = final_values(exp, arm, key)
            m, lo, hi = bootstrap_mean_ci(v, n_res, seed=1)
            a["metrics"][key] = {"mean": m, "lo": lo, "hi": hi, "median": float(np.median(v)), "per_seed": v.tolist()}
        rs = [r for r in exp.runners.values() if r.arm_name == arm]
        evals = rs[0].evaluator.n_evals
        cpu = np.array([r.cpu_search_total for r in rs])
        ho = np.array(a["metrics"][PRIMARY]["per_seed"])
        a.update({
            "evals_per_seed": int(evals), "cpu_search_s_mean": float(cpu.mean()),
            "cpu_monitor_s_mean": float(np.mean([r.cpu_monitor_total for r in rs])),
            "mem_peak_kb_max": float(max(r.peak_mem_kb for r in rs)),
            "heldout_qd_per_1k_evals": float(ho.mean() / (evals / 1000.0)) if evals else float("nan"),
            "heldout_qd_per_cpu_s": float(ho.mean() / cpu.mean()) if cpu.mean() > 0 else float("nan"),
            "auc_heldout_qd": float(np.mean(series(exp, arm, PRIMARY))),
        })
        out["arms"][arm] = a
    pairs = [("A_fly_plastic", "B_evolved_ann"), ("A_fly_plastic", "A_fly_noplast"),
             ("A_fly_plastic", "A_fly_shuffled"), ("A_fly_plastic", "C_genetic"), ("A_fly_plastic", "D_random"),
             ("B_evolved_ann", "C_genetic"), ("B_evolved_ann", "D_random"), ("C_genetic", "D_random")]
    for a_, b_ in pairs:
        if a_ not in cfg.arms or b_ not in cfg.arms:
            continue
        for key in ("heldout_qd", "heldout_best", "heldout_discovery"):
            m, lo, hi = paired_diff_ci(final_values(exp, a_, key), final_values(exp, b_, key), n_res, seed=2)
            out["paired"].append({"a": a_, "b": b_, "metric": key, "diff": m, "lo": lo, "hi": hi})
    out["conclusions"] = conclusions(exp, out)
    return out


def _ci_excludes_zero(p) -> bool:
    return not (np.isnan(p["lo"]) or np.isnan(p["hi"])) and (p["lo"] > 0 or p["hi"] < 0)


def conclusions(exp, res: dict) -> list[dict]:
    cfg = exp.cfg
    n = cfg.n_seeds
    claim_ok = n >= cfg.min_seeds_for_claim
    items: list[dict] = []
    gen = exp.generation
    items.append({"title": "Scope", "text": (
        f"Results cover {gen} generations x {cfg.pop_size} agents per arm and {n} paired seeds on a SYNTHETIC "
        "benchmark. Nothing here is evidence about real markets, customers or revenue (real revenue: EUR 0 / unknown). "
        + ("Seed count is sufficient for formal comparisons." if claim_ok else
           f"With n={n} < {cfg.min_seeds_for_claim} seeds, no statistical-significance claim is made; intervals are indicative only."))})
    # best arm per metric
    lines = []
    for key, label, hib, kind in METRICS:
        ranked = sorted(res["arms"].items(), key=lambda kv: kv[1]["metrics"][key]["mean"], reverse=hib)
        (b1, d1), (b2, d2) = ranked[0], ranked[1]
        gap = d1["metrics"][key]["mean"] - d2["metrics"][key]["mean"]
        overlap = d1["metrics"][key]["lo"] <= d2["metrics"][key]["hi"] if not np.isnan(d1["metrics"][key]["lo"]) else True
        lines.append(f"{label}: highest mean = {b1} ({d1['metrics'][key]['mean']:.3f}); lead over {b2} = {gap:+.3f}; "
                     f"{'bootstrap intervals overlap (no clear separation)' if overlap else 'intervals do not overlap'}"
                     f"{'' if kind != 'train' else ' [training metric - not a basis for declaring a winner]'}.")
    items.append({"title": "Best arm per measured metric (mean of last 5 generations, across seeds)", "list": lines})
    # headline: held-out only
    prim = sorted(res["arms"].items(), key=lambda kv: -kv[1]["metrics"][PRIMARY]["mean"])
    top, second = prim[0], prim[1]
    gp = next((p for p in res["paired"] if p["a"] == top[0] and p["b"] == second[0] and p["metric"] == PRIMARY), None)
    if gp is None:
        gp = next((p for p in res["paired"] if p["a"] == second[0] and p["b"] == top[0] and p["metric"] == PRIMARY), None)
        if gp:
            gp = {**gp, "diff": -gp["diff"], "lo": -gp["hi"], "hi": -gp["lo"]}
    txt = (f"On the held-out quality-diversity score the highest-scoring arm is {top[0]} "
           f"({top[1]['metrics'][PRIMARY]['mean']:.3f}) ahead of {second[0]} ({second[1]['metrics'][PRIMARY]['mean']:.3f}).")
    if gp and not np.isnan(gp["lo"]):
        txt += (f" Paired difference {gp['diff']:+.3f} (95% bootstrap CI {gp['lo']:+.3f} to {gp['hi']:+.3f}, n={n}). "
                + ("The CI excludes zero" if _ci_excludes_zero(gp) else "The CI includes zero") +
                (", but with this few seeds this is preliminary and is not declared a winner." if not claim_ok else "."))
    else:
        txt += " No paired interval available for this pair."
    items.append({"title": "Headline (held-out only)", "text": txt})
    # biology
    bio = []
    for b_, label in (("B_evolved_ann", "an evolved ANN with the same parameter budget and evolutionary engine"),
                      ("A_fly_noplast", "the same circuit without plasticity"),
                      ("A_fly_shuffled", "the same circuit with shuffled PN->KC wiring")):
        p = next((p for p in res["paired"] if p["a"] == "A_fly_plastic" and p["b"] == b_ and p["metric"] == PRIMARY), None)
        if p is None:
            continue
        verdict = ("CI excludes zero (preliminary)" if _ci_excludes_zero(p) else "CI includes zero: no measurable difference")
        bio.append(f"Mushroom-body-inspired controller with plasticity vs {label}: held-out QD diff {p['diff']:+.3f} "
                   f"[{p['lo']:+.3f}, {p['hi']:+.3f}] - {verdict}.")
    bio.append("Even a positive difference would show value of a sparse, plastic architecture on THIS synthetic task, "
               "not of real Drosophila connectivity (none is used).")
    items.append({"title": "Did the biologically inspired architecture add measurable value?", "list": bio})
    items.append({"title": "Uncertainty", "text": (
        f"Intervals are percentile bootstrap CIs over {n} seeds ({cfg.bootstrap_resamples} resamples); a single world "
        "(fixed hidden landscape) is used, so results do not generalise across worlds. Metrics are averaged over the last "
        "5 generations to reduce evaluation noise.")})
    items.append({"title": "What remains unverified", "list": [
        "Any real-world validity: no public evidence dataset is wired in yet; all hypotheses are synthetic-tier.",
        "Arm E (LLM baseline): " + exp.llm["status"] + " - " + exp.llm["reason"],
        "Biological fidelity: no FlyWire/hemibrain connectivity is used; the controller is a documented mushroom-body-inspired model.",
        "Robustness across different hidden worlds and benchmark difficulty levels.",
        "Seeds: " + (f"n={n} meets the configured minimum." if claim_ok else f"n={n} is below the configured minimum of {cfg.min_seeds_for_claim}.")]})
    nxt = []
    if not claim_ok:
        nxt.append(f"Increase seeds to >= {cfg.min_seeds_for_claim} (cheap: ~minutes of CPU) and re-test the paired differences.")
    nxt.append("Add a second, non-stationary benchmark world (peaks drift over generations) where lifetime plasticity "
               "should matter; the current stationary task gives plasticity little to exploit.")
    nxt.append("Wire in one public, legitimately accessible evidence dataset (evidence-tier fitness) with recorded provenance.")
    nxt.append("Run arm E when a free LLM endpoint is available, at a matched evaluation budget.")
    items.append({"title": "Suggested next experiments", "list": nxt})
    return items
