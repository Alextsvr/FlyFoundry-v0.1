"""v0.2 E2 final tournament: the ONLY place that touches the `final` contexts.

Input: populations (islands or one pool). Each niche's entry is chosen on `select` (islands/merge), then every
chosen entry is judged once, noise-free, on the `final` contexts. The champion is the entry with the best
`select` score (no peeking at `final`); its select-minus-final gap measures the winner's curse.
"""
from __future__ import annotations

import numpy as np

from ..environments.benchmark import BenchmarkWorld
from .islands import Population, merge_by_select


def final_tournament(pops: list[Population], world: BenchmarkWorld) -> dict:
    select, judge = world.select_view(), world.final_judge()
    chosen = merge_by_select(pops, select)
    if not chosen:
        return {"final_qd": 0.0, "final_best": 0.0, "final_discovery": 0.0, "champ_select": 0.0,
                "champ_final": 0.0, "gap": 0.0, "n_entries": 0, "n_evals": sum(p.n_evals for p in pops)}
    by_pop: dict[int, list[int]] = {}
    for n, (_, pi) in chosen.items():
        by_pop.setdefault(pi, []).append(n)
    blocks, sel_scores = [], []
    for pi, niches in sorted(by_pop.items()):
        niches = np.array(sorted(niches))
        blocks.append(pops[pi].arm.deploy(niches, judge.ctx))
        sel_scores.extend(chosen[int(n)][0] for n in niches)
    Xh = np.concatenate(blocks, axis=0)
    sel = np.array(sel_scores)
    m = judge.metrics(Xh)
    fin = judge.score(Xh)
    c = int(np.argmax(sel))
    return {"final_qd": m["heldout_qd"], "final_best": m["heldout_best"], "final_discovery": m["heldout_discovery"],
            "champ_select": float(sel[c]), "champ_final": float(fin[c]), "gap": float(sel[c] - fin[c]),
            "n_entries": int(len(sel)), "n_evals": int(sum(p.n_evals for p in pops))}
