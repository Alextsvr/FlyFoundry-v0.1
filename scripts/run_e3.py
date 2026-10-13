"""E3 plumbing backtest (docs/V0_2_SPEC.md, E3): GA over criterion weights, trained on 3 weight sets, judged once on 2.

usage: python scripts/run_e3.py [--repeats 30] [--generations 60] [--out reports/e3]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from flyfoundry.agents.registry import build_arm
from flyfoundry.config import ExperimentConfig
from flyfoundry.evaluation.plugins import ContextEvaluator, TabularBacktest
from flyfoundry.evaluation.stats import bootstrap_mean_ci

RHO_PASS = 0.8
PASS_SHARE = 0.9


def run_repeat(fit: TabularBacktest, rep: int, generations: int) -> dict:
    cfg = ExperimentConfig(n_dims=fit.n_dims, pop_size=100, survivors=30, elites=5, archive_dims=(0, 1, 3))
    seed = cfg.seed_base + rep
    arm = build_arm("C_genetic", cfg, seed)
    ev = ContextEvaluator(fit, np.random.default_rng(np.random.SeedSequence([seed, 7777])))
    for g in range(generations):
        ev.allowed_evals += cfg.pop_size
        arm.step(ev, g)
    fl = arm.archive.filled
    E = arm.archive.X[fl]
    train_mean = np.mean([fit.rho(E, s) for s in fit.train_sets], axis=0)   # selection uses TRAIN sets only
    champ = E[int(np.argmax(train_mean))]
    final = {s: float(fit.rho(champ[None], s)[0]) for s in fit.final_sets}
    top2, last = fit.top_and_last(champ)
    ok = all(v >= RHO_PASS for v in final.values()) and set(top2) == {"H07", "H01"} and last == "H03"
    return {"rep": rep, "train_rho": float(train_mean.max()), "final_rho": final, "top2": top2, "last": last,
            "pass": bool(ok), "champion_weights": [round(float(v), 3) for v in champ]}


def baselines(fit: TabularBacktest) -> dict:
    rng = np.random.default_rng(0)
    eq = np.ones((1, fit.n_dims))
    mean_train = np.mean([fit.W[s] / fit.W[s].sum() for s in fit.train_sets], axis=0)[None]
    rnd = rng.random((2000, fit.n_dims))
    out = {}
    for name, X in (("equal_weights", eq), ("mean_of_train_weight_sets", mean_train)):
        out[name] = {s: float(fit.rho(X, s)[0]) for s in fit.final_sets}
        t2, last = fit.top_and_last(X[0])
        out[name].update({"top2": t2, "last": last})
    out["random_weights_mean"] = {s: float(fit.rho(rnd, s).mean()) for s in fit.final_sets}
    out["random_weights_share_pass"] = float(np.mean([
        (fit.rho(x[None], fit.final_sets[0])[0] >= RHO_PASS and fit.rho(x[None], fit.final_sets[1])[0] >= RHO_PASS
         and set(fit.top_and_last(x)[0]) == {"H07", "H01"} and fit.top_and_last(x)[1] == "H03") for x in rnd]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--generations", type=int, default=60)
    ap.add_argument("--out", default="reports/e3")
    a = ap.parse_args()
    fit = TabularBacktest()
    rows = [run_repeat(fit, r, a.generations) for r in range(a.repeats)]
    share = float(np.mean([r["pass"] for r in rows]))
    fr = {s: [r["final_rho"][s] for r in rows] for s in fit.final_sets}
    res = {"repeats": a.repeats, "generations": a.generations, "train_sets": list(fit.train_sets),
           "final_sets": list(fit.final_sets), "pass_share": share, "verdict": "PASS" if share >= PASS_SHARE else "FAIL",
           "final_rho_mean_ci": {s: bootstrap_mean_ci(v, 2000, seed=0) for s, v in fr.items()},
           "baselines": baselines(fit), "rows": rows}
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "e3_results.json").write_text(json.dumps(res, indent=1))
    L = ["## E3 plumbing backtest (NOT validation)", "",
         f"{a.repeats} repeats, {a.generations} generations, GA over 13 criterion weights. Train weight sets: "
         f"{', '.join(fit.train_sets)}; judged once on: {', '.join(fit.final_sets)}.", "",
         f"**Verdict: {res['verdict']}** - {share:.0%} of repeats satisfy all of: Spearman >= {RHO_PASS} on both final sets, "
         f"top-2 = {{H07, H01}}, last = H03 (pass needs >= {PASS_SHARE:.0%}).", "",
         "| Final weight set | Spearman mean [95% CI] |", "|---|---|"]
    for s, (m, lo, hi) in res["final_rho_mean_ci"].items():
        L.append(f"| {s} | {m:.3f} [{lo:.3f}, {hi:.3f}] |")
    b = res["baselines"]
    L += ["", "Baselines (no search): " + "; ".join(
        f"{k}: " + ", ".join(f"{s}={v[s]:.3f}" for s in fit.final_sets) + f", top2={v['top2']}, last={v['last']}"
        for k, v in b.items() if k in ("equal_weights", "mean_of_train_weight_sets")),
        f"Random weights: mean Spearman " + ", ".join(f"{s}={v:.3f}" for s, v in b["random_weights_mean"].items())
        + f"; share of random weight vectors passing all criteria: {b['random_weights_share_pass']:.1%}.", "",
        "Mandatory caveat: the inputs are the same scores that define the reference ranking, so a pass shows that the "
        "machinery (plugin interface, search, train/final split) works - not that the swarm can find good businesses."]
    (out / "e3_verdict.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
