"""E4 (non-stationary world) verdicts from a merged history.csv, exactly as pre-registered in docs/V0_2_SPEC.md.

Primary metric: track_qd, mean over generations 41-60 per seed (window fixed in the spec; do not change after seeing data).
Decision rule per contrast: paired percentile bootstrap (2000 resamples) of the per-seed difference;
SUPPORTED if CI lower bound > 0, REFUTED if upper bound < 0, otherwise INCONCLUSIVE.

usage: python scripts/analyze_e4.py history.csv [--out e4.md] [--json e4.json] [--condition medium]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict

import numpy as np

from flyfoundry.evaluation.stats import bootstrap_mean_ci

WINDOW = (41, 60)
CONTRASTS = [
    ("E4-H1", "A_fly_plastic", "B_evolved_ann", "fly+plasticity vs evolved ANN"),
    ("E4-H2", "A_fly_plastic", "A_fly_noplast", "plasticity itself"),
    ("E4-H3", "A_fly_plastic", "A_fly_shuffled", "PN->KC wiring"),
    ("E4-H4", "C_genetic", "D_random", "sanity: GA vs random search"),
]


def verdict(lo: float, hi: float) -> str:
    if lo > 0:
        return "SUPPORTED"
    if hi < 0:
        return "REFUTED"
    return "INCONCLUSIVE"


def per_seed_means(path: str, metric: str) -> dict:
    acc = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            g = int(r["gen"])
            if WINDOW[0] <= g <= WINDOW[1] and r.get(metric) not in (None, ""):
                acc[(r["arm"], int(r["seed"]))].append(float(r[metric]))
    return {k: float(np.mean(v)) for k, v in acc.items()}


def analyse(path: str, metric: str = "track_qd") -> dict:
    m = per_seed_means(path, metric)
    if not m:
        raise SystemExit(f"no '{metric}' values in generations {WINDOW[0]}-{WINDOW[1]}; was this a drifting-world run?")
    arms = sorted({a for a, _ in m})
    seeds = sorted({s for _, s in m})
    out = {"metric": metric, "window": list(WINDOW), "n_seeds": len(seeds), "arms": {}, "contrasts": []}
    for a in arms:
        mean, lo, hi = bootstrap_mean_ci([m[(a, s)] for s in seeds], 2000, seed=0)
        out["arms"][a] = {"mean": mean, "ci": [lo, hi]}
    for cid, a, b, desc in CONTRASTS:
        if a not in arms or b not in arms:
            continue
        d = [m[(a, s)] - m[(b, s)] for s in seeds]
        mean, lo, hi = bootstrap_mean_ci(d, 2000, seed=1)
        out["contrasts"].append({"id": cid, "a": a, "b": b, "what": desc, "diff": mean, "ci": [lo, hi],
                                 "verdict": verdict(lo, hi)})
    return out


def markdown(res: dict, condition: str) -> str:
    L = [f"## E4 verdicts ({condition})", "",
         f"Metric `{res['metric']}`, mean over generations {res['window'][0]}-{res['window'][1]}, n = {res['n_seeds']} paired seeds. "
         "Rule fixed in docs/V0_2_SPEC.md before any run. Only E4-H2 in the MEDIUM condition is the primary claim; "
         "everything else is exploratory (9 tests in total).", "",
         "| Arm | mean [95% CI] |", "|---|---|"]
    for a, v in res["arms"].items():
        L.append(f"| {a} | {v['mean']:.3f} [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}] |")
    L += ["", "| Hypothesis | Contrast | Paired diff [95% CI] | Verdict |", "|---|---|---|---|"]
    for c in res["contrasts"]:
        L.append(f"| {c['id']} | {c['a']} - {c['b']} ({c['what']}) | {c['diff']:+.3f} [{c['ci'][0]:+.3f}, {c['ci'][1]:+.3f}] | **{c['verdict']}** |")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("history")
    ap.add_argument("--out")
    ap.add_argument("--json")
    ap.add_argument("--condition", default="unspecified")
    ap.add_argument("--metric", default="track_qd")
    a = ap.parse_args()
    res = analyse(a.history, a.metric)
    md = markdown(res, a.condition)
    print(md)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
