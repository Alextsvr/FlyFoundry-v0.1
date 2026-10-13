"""Phase 1 layer-F score for an idea from probe facts. Contains NO reference verdicts (see calibration.py).

Pre-registered (docs/PHASE1_SPEC.md sections 5-6): F = (z(pain) + z(question volume) - z(free alternatives)) / 3 with
equal weights; z-scores are taken over all ideas of the run; pain = mean log1p mentions over the idea's phrases;
free alternatives = log1p(repo total) + log1p(top-5 stars) averaged. Missing source -> that term is dropped for the idea.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


def raw_features(facts) -> dict:
    by = defaultdict(lambda: defaultdict(list))
    for f in facts:
        if f["status"] != "ok":
            continue
        i = f["idea"]
        if f["source"] == "hn":
            by[i]["pain"].append(math.log1p(f["value"]))
        elif f["source"] == "stackexchange":
            by[i]["qvol"].append(math.log1p(f["value"]))
        elif f["source"] == "github":
            by[i]["free"].append((math.log1p(f["value"]["total"]) + math.log1p(f["value"]["top5_stars"])) / 2)
    return {i: {k: float(np.mean(v)) for k, v in d.items()} for i, d in by.items()}


def f_scores(facts) -> dict:
    feats = raw_features(facts)
    ids = sorted(feats)
    z = {}
    for k in ("pain", "qvol", "free"):
        vals = np.array([feats[i].get(k, np.nan) for i in ids])
        ok = ~np.isnan(vals)
        sd = vals[ok].std() if ok.sum() > 1 else 0.0
        z[k] = {i: (v - vals[ok].mean()) / sd if (o and sd > 0) else None for i, v, o in zip(ids, vals, ok)}
    out = {}
    for i in ids:
        terms = [z["pain"][i], z["qvol"][i], None if z["free"][i] is None else -z["free"][i]]
        terms = [t for t in terms if t is not None]
        if terms:
            out[i] = float(np.sum(terms) / 3.0)
    return out


def shuffle_facts(facts, seed: int = 0):
    """Negative control: reassign each idea's probe results to another idea."""
    ids = sorted({f["idea"] for f in facts})
    perm = np.random.default_rng(seed).permutation(len(ids))
    mp = {ids[a]: ids[b] for a, b in enumerate(perm)}
    return [{**f, "idea": mp[f["idea"]]} for f in facts]
