"""Phase 1 calibration (docs/PHASE1_SPEC.md section 6): does the automated F score reproduce the manual verdicts on H01-H12?

The reference y lives ONLY in this module (and data/calibration_reference.csv); scoring.py must never import it.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ..evaluation.plugins import rank_rows
from ..evaluation.stats import bootstrap_mean_ci

RHO_PASS, P_PASS, STABILITY_PASS = 0.5, 0.05, 0.8


def load_reference(path: str | Path = "data/calibration_reference.csv") -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        return {r["id"]: float(r["y"]) for r in csv.DictReader(f)}


def spearman(a, b) -> float:
    ra, rb = rank_rows(np.array([a], float))[0], rank_rows(np.array([b], float))[0]
    ra, rb = ra - ra.mean(), rb - rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return float((ra @ rb) / den) if den > 0 else 0.0


def calibrate(scores: dict, y: dict, n_perm: int = 10_000, seed: int = 0) -> dict:
    ids = sorted(set(scores) & set(y))
    a, b = [scores[i] for i in ids], [y[i] for i in ids]
    rho = spearman(a, b)
    rng = np.random.default_rng(seed)
    perm = np.array([spearman(rng.permutation(a), b) for _ in range(n_perm)])
    p = float((perm >= rho).mean())                      # one-sided: positive association expected
    idx = rng.integers(0, len(ids), (2000, len(ids)))
    boots = np.array([spearman(np.array(a)[i], np.array(b)[i]) for i in idx])
    ci = [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]
    return {"n": len(ids), "rho": rho, "p_one_sided": p, "ci95": ci,
            "verdict": "PASS" if rho >= RHO_PASS and p <= P_PASS else "FAIL"}


def stability(scores_a: dict, scores_b: dict) -> dict:
    ids = sorted(set(scores_a) & set(scores_b))
    rho = spearman([scores_a[i] for i in ids], [scores_b[i] for i in ids])
    return {"n": len(ids), "rho": rho, "verdict": "PASS" if rho >= STABILITY_PASS else "FAIL"}
