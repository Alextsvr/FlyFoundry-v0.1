"""Phase 1 layer-C idea ranking: exhaustive scoring of the idea space + island swarm search + named seeds.

The idea space (147 000 tuples) is small enough to enumerate, so the exhaustive ranking is authoritative; the swarm is run
(a) to measure how much of the exact top it recovers vs random sampling with the same evaluation budget, and (b) because
the same machinery is needed once candidate evaluation becomes expensive.

usage: python scripts/run_ideas.py [--out reports/phase1-ideas] [--repeats 20]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from flyfoundry.agents.registry import build_arm
from flyfoundry.config import ExperimentConfig
from flyfoundry.evaluation.plugins import ContextEvaluator
from flyfoundry.phase1.ideaspace import CRITERIA, GATE_SCORE, TYPES, IdeaSpace, load_seeds

N_ISLANDS, POP, GENS, TOPK = 10, 100, 60, 50


def run_swarm(space: IdeaSpace, rep: int):
    cfg = ExperimentConfig(n_dims=space.n_dims, pop_size=POP, survivors=30, elites=5, archive_dims=(0, 1, 2), archive_bins=4)
    held = []
    for i in range(N_ISLANDS):
        seed = cfg.seed_base + 1000 * rep + i
        arm = build_arm("C_genetic", cfg, seed)
        ev = ContextEvaluator(space, np.random.default_rng(np.random.SeedSequence([seed, 7777])))
        for g in range(GENS):
            ev.allowed_evals += POP
            arm.step(ev, g)
        held.append(arm.archive.X[arm.archive.filled])
        held.append(arm.X)
    idx = np.unique(space.decode_indices(np.concatenate(held)), axis=0)
    return idx


def flat_id(space: IdeaSpace, idx: np.ndarray) -> np.ndarray:
    return np.ravel_multi_index(idx.T, space.sizes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/phase1-ideas")
    ap.add_argument("--repeats", type=int, default=20)
    a = ap.parse_args()
    sp = IdeaSpace()
    idx, F, gated, legal, S = sp.exhaustive()
    mean = S.mean(axis=1)
    ok = ~gated
    order = np.argsort(-np.where(ok, mean, -9))
    n_ok = int(ok.sum())
    # rank under each weight set among non-gated
    ranks = np.zeros_like(S, dtype=int)
    for k in range(S.shape[1]):
        o = np.argsort(-np.where(ok, S[:, k], -9))
        ranks[o, k] = np.arange(1, len(o) + 1)
    top_ids = set(order[:TOPK].tolist())
    # swarm vs random recall of the exact top-50 at equal evaluation budget
    rng = np.random.default_rng(0)
    rec_sw, rec_rnd, n_unique = [], [], []
    first = None
    for rep in range(a.repeats):
        found = run_swarm(sp, rep)
        if first is None:
            first = found
        fid = set(flat_id(sp, found).tolist())
        n_unique.append(len(fid))
        rec_sw.append(len(fid & top_ids) / TOPK)
        rnd = rng.integers(0, sp.n_total, N_ISLANDS * POP * GENS)
        rec_rnd.append(len(set(rnd.tolist()) & top_ids) / TOPK)
    # named seeds under the same fitness
    seeds = load_seeds()
    SF = np.array([s["f"] for s in seeds])
    SS = ((SF @ sp.W.T) / sp.W.sum(axis=1)[None, :] - 1) / 4
    seed_rows = []
    for s, row in zip(seeds, SS):
        pct = float(np.mean(mean[ok] < row.mean()))
        seed_rows.append({"id": s["id"], "name": s["name"], "confidence": s["confidence"], "scores": row.round(3).tolist(),
                          "mean": float(row.mean()), "percentile_vs_generated": pct})
    seed_rows.sort(key=lambda r: -r["mean"])
    # per-problem best (diversity view)
    best_by_problem = {}
    for i in order[:20000]:
        p = int(idx[i, 1])
        if p not in best_by_problem:
            best_by_problem[p] = int(i)
    def row(i):
        d = sp.describe(idx[i])
        return {**d, "mean": float(mean[i]), "min_over_sets": float(S[i].min()), "rank_range": [int(ranks[i].min()), int(ranks[i].max())],
                "legal_check_needed": bool(legal[i])}
    of = sp.meta["owner_fit"]
    ci = [sp.names["customer"].index(x) for x in of["customers"]]
    pi = [sp.names["problem"].index(x) for x in of["problems"]]
    fit_mask = ok & np.isin(idx[:, 0], ci) & np.isin(idx[:, 1], pi)
    fit_order = [i for i in order if fit_mask[i]][:25]
    res = {"n_total": sp.n_total, "n_gated_or_forbidden": int(gated.sum()), "n_scored": n_ok, "sets": sp.set_names,
           "top": [row(i) for i in order[:TOPK]],
           "best_per_problem": [row(i) for i in sorted(best_by_problem.values(), key=lambda i: -mean[i])],
           "owner_fit_top": [row(i) for i in fit_order], "owner_fit_basis": of["basis"],
           "swarm": {"islands": N_ISLANDS, "pop": POP, "gens": GENS, "evals": N_ISLANDS * POP * GENS, "repeats": a.repeats,
                     "recall_top50_mean": float(np.mean(rec_sw)), "recall_top50_min": float(np.min(rec_sw)),
                     "random_recall_top50_mean": float(np.mean(rec_rnd)), "unique_candidates_mean": float(np.mean(n_unique))},
           "seeds": seed_rows}
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ideas_rank.json").write_text(json.dumps(res, indent=1))
    L = ["## Phase 1 idea ranking (layer C: curated priors, NOT evidence)", "",
         f"{sp.n_total:,} candidate tuples ({res['n_gated_or_forbidden']:,} removed by hard gates / forbidden pairs). Score = weighted mean of 13 criteria under 5 weight sets, rescaled 0..1. "
         "Component values are judgement priors written once and not yet checked against sources.", "",
         "### Exact top 25 (exhaustive; mean over the 5 weight sets)", "",
         "| # | customer | problem | solution | revenue | channel | mean | worst set | rank range | legal check |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(res["top"][:25], 1):
        L.append(f"| {n} | {r['customer']} | {r['problem']} | {r['solution']} | {r['revenue']} | {r['channel']} | {r['mean']:.3f} | {r['min_over_sets']:.3f} | {r['rank_range'][0]}-{r['rank_range'][1]} | {'yes' if r['legal_check_needed'] else ''} |")
    L += ["", "### Owner-fit overlay: top 25 inside the owner's domain (" + of["basis"] + ")", "",
          "| # | customer | problem | solution | revenue | channel | mean | legal check |", "|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(res["owner_fit_top"], 1):
        L.append(f"| {n} | {r['customer']} | {r['problem']} | {r['solution']} | {r['revenue']} | {r['channel']} | {r['mean']:.3f} | {'yes' if r['legal_check_needed'] else ''} |")
    L += ["", "### Best candidate per problem type (diversity view)", "", "| problem | best combination | mean |", "|---|---|---|"]
    for r in res["best_per_problem"]:
        L.append(f"| {r['problem']} | {r['customer']} / {r['solution']} / {r['revenue']} / {r['channel']} | {r['mean']:.3f} |")
    sw = res["swarm"]
    L += ["", "### What the swarm added", "",
          f"{sw['islands']} islands x {sw['pop']} x {sw['gens']} gens = {sw['evals']:,} evaluations, {sw['repeats']} repeats. Recall of the exact top-{TOPK}: swarm {sw['recall_top50_mean']:.0%} (worst {sw['recall_top50_min']:.0%}) vs random sampling with the same budget {sw['random_recall_top50_mean']:.0%}. "
          "The space is small enough to enumerate, so enumeration is the authoritative ranking; the swarm is a consistency check, not a source of new ideas: it can only recombine the components written into the taxonomy.", "",
          "### Named seed ideas under the same fitness", "",
          "Seeds carry their own criterion vectors (H01-H12: three-track research; N1-N7: unresearched priors), so their scores are NOT on the same footing as averaged components. Compare seeds with seeds.", "",
          "| id | idea | confidence | mean | percentile vs generated |", "|---|---|---|---|---|"]
    for r in seed_rows:
        L.append(f"| {r['id']} | {r['name']} | {r['confidence']} | {r['mean']:.3f} | {r['percentile_vs_generated']:.0%} |")
    (out / "ideas_rank.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
