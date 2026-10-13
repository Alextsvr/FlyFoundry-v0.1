"""E2 (island model) verdicts from the shard files, exactly as pre-registered in docs/V0_2_SPEC.md (section E2).

Metric: final_qd = quality-diversity of the swarm's merged archive judged ONCE on the `final` contexts (noise-free).
Primary (one per arm, alpha = 0.025 each, two-sided): E2-H1  islands_mig - single_pool.
Exploratory (alpha = 0.05): E2-H2 islands_mig - islands_nomig (migration), E2-H3 islands_nomig - single_pool (merge only),
E2-H4 winner's-curse gap: gap(islands_mig) - gap(single_pool); 'over-selecting' flag if the CI lower bound > 0.
Rule: SUPPORTED if CI lower bound > 0, REFUTED if upper < 0, else INCONCLUSIVE (paired over repeats, percentile bootstrap, 2000).

usage: python scripts/analyze_e2.py SHARD_DIR [--out e2.md] [--json e2.json] [--expect-repeats 100]
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

import numpy as np

from flyfoundry.evaluation.stats import bootstrap_mean_ci

CONDS = ("islands_mig", "islands_nomig", "single_pool")


def verdict(lo: float, hi: float) -> str:
    return "SUPPORTED" if lo > 0 else "REFUTED" if hi < 0 else "INCONCLUSIVE"


def load(shard_glob: str, expect_repeats: int | None) -> tuple[list[dict], dict]:
    files = sorted(glob.glob(shard_glob, recursive=True))
    if not files:
        raise SystemExit(f"no shard files match {shard_glob}")
    payloads = [json.load(open(f, encoding="utf-8")) for f in files]
    for k in ("config_hash", "world_fingerprint", "generations", "repeats", "n_islands", "migrate_every", "n_migrants", "pool_factor"):
        if len({json.dumps(p[k]) for p in payloads}) != 1:
            raise SystemExit(f"shards disagree on {k}: refusing to merge")
    rows = [r for p in payloads for r in p["rows"]]
    reps = sorted({r["rep"] for r in rows})
    want = expect_repeats or payloads[0]["repeats"]
    if reps != list(range(want)):
        raise SystemExit(f"incomplete or overlapping repeats: got {len(reps)} distinct, expected exactly 0..{want - 1}")
    if len(rows) != len(set((r["rep"], r["arm"], r["condition"]) for r in rows)):
        raise SystemExit("duplicate (rep, arm, condition) rows")
    return rows, {k: payloads[0][k] for k in ("config_hash", "world_fingerprint", "generations", "repeats", "n_islands",
                                              "migrate_every", "n_migrants", "pool_factor")}


def analyse(rows: list[dict]) -> dict:
    by = defaultdict(dict)
    for r in rows:
        by[(r["arm"], r["condition"])][r["rep"]] = r
    arms = sorted({a for a, _ in by})
    reps = sorted({r["rep"] for r in rows})
    col = lambda a, c, k: np.array([by[(a, c)][i][k] for i in reps])  # noqa: E731
    out = {"n_repeats": len(reps), "arms": {}, "contrasts": []}
    for a in arms:
        out["arms"][a] = {}
        for c in CONDS:
            m, lo, hi = bootstrap_mean_ci(col(a, c, "final_qd"), 2000, seed=0)
            g, glo, ghi = bootstrap_mean_ci(col(a, c, "gap"), 2000, seed=0)
            out["arms"][a][c] = {"final_qd": m, "ci": [lo, hi], "gap": g, "gap_ci": [glo, ghi],
                                 "final_best": float(col(a, c, "final_best").mean()),
                                 "n_evals": int(col(a, c, "n_evals")[0])}
    for a in arms:
        spec = [("E2-H1", "islands_mig", "single_pool", "final_qd", 0.025, "primary"),
                ("E2-H2", "islands_mig", "islands_nomig", "final_qd", 0.05, "exploratory"),
                ("E2-H3", "islands_nomig", "single_pool", "final_qd", 0.05, "exploratory"),
                ("E2-H4", "islands_mig", "single_pool", "gap", 0.05, "exploratory")]
        for cid, c1, c2, key, alpha, kind in spec:
            d = col(a, c1, key) - col(a, c2, key)
            m, lo, hi = bootstrap_mean_ci(d, 2000, alpha=alpha, seed=1)
            v = verdict(lo, hi)
            if cid == "E2-H4":
                v = "OVER-SELECTING" if lo > 0 else "NOT OVER-SELECTING" if hi < 0 else "INCONCLUSIVE"
            out["contrasts"].append({"id": cid, "arm": a, "a": c1, "b": c2, "metric": key, "alpha": alpha, "kind": kind,
                                     "diff": m, "ci": [lo, hi], "verdict": v})
    return out


def markdown(res: dict, meta: dict) -> str:
    L = ["## E2 verdicts (island model vs single pool)", "",
         f"{res['n_repeats']} paired repeats; {meta['n_islands']} islands x pop P vs one pool of {meta['pool_factor']}P; "
         f"{meta['generations']} generations; migration every {meta['migrate_every']} gens, {meta['n_migrants']} elites per event. "
         "Metric `final_qd` judged once on the `final` contexts. Rules fixed in docs/V0_2_SPEC.md before the run.", "",
         "| Arm | Condition | final_qd [95% CI] | winner's-curse gap [95% CI] | evals |", "|---|---|---|---|---|"]
    for a, cs in res["arms"].items():
        for c, v in cs.items():
            L.append(f"| {a} | {c} | {v['final_qd']:.3f} [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}] | "
                     f"{v['gap']:+.3f} [{v['gap_ci'][0]:+.3f}, {v['gap_ci'][1]:+.3f}] | {v['n_evals']} |")
    L += ["", "| Test | Arm | Contrast (metric) | Diff [CI] | Kind | Verdict |", "|---|---|---|---|---|---|"]
    for c in res["contrasts"]:
        ci = int(round((1 - c["alpha"]) * 1000)) / 10
        L.append(f"| {c['id']} | {c['arm']} | {c['a']} - {c['b']} ({c['metric']}) | {c['diff']:+.4f} "
                 f"[{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}] ({ci}% CI) | {c['kind']} | **{c['verdict']}** |")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("shard_dir")
    ap.add_argument("--out")
    ap.add_argument("--json")
    ap.add_argument("--expect-repeats", type=int, default=None)
    a = ap.parse_args()
    rows, meta = load(a.shard_dir.rstrip("/") + "/**/e2_shard_*.json" if "*" not in a.shard_dir else a.shard_dir,
                      a.expect_repeats)
    res = analyse(rows)
    md = markdown(res, meta)
    print(md)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump({"meta": meta, **res}, open(a.json, "w", encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
