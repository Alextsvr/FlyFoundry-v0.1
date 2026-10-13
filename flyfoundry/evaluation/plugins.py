"""v0.2 fitness plugin interface and the tabular backtest fitness (E3).

A ``Fitness`` scores candidates in training contexts. ``ContextEvaluator`` wraps any Fitness behind the same
interface the arms already use (``sample_scenarios`` / ``evaluate``), so swapping the fitness does not touch the arms
or the swarm code. NOTE: the v0.1 synthetic landscape still uses its own ``Evaluator``; it has not been ported onto
this protocol (it works unchanged and its golden fingerprint is pinned by tests).

``TabularBacktest``: candidate = a non-negative weight vector over the 13 project criteria; for a context (a weight set)
the fitness is the Spearman rank correlation between the ranking the candidate induces on H01-H12 and the reference
ranking of that weight set. This is a PLUMBING test: inputs and reference come from the same table.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TRAIN_SETS = ("base", "equal", "money_first")             # pre-registered split (docs/V0_2_SPEC.md, E3)
FINAL_SETS = ("automation_first", "risk_averse")


class Fitness(Protocol):
    n_dims: int
    n_contexts: int

    def train(self, X: np.ndarray, ctx_idx: np.ndarray) -> np.ndarray: ...


def rank_rows(M: np.ndarray) -> np.ndarray:
    """Average ranks (1 = smallest) along the last axis, ties averaged."""
    M = np.atleast_2d(M)
    out = np.zeros(M.shape, dtype=float)
    for i, row in enumerate(M):
        order = np.argsort(row, kind="stable")
        r = np.empty(len(row))
        r[order] = np.arange(1, len(row) + 1)
        for v in np.unique(row):
            m = row == v
            if m.sum() > 1:
                r[m] = r[m].mean()
        out[i] = r
    return out


def spearman_rows(A: np.ndarray, ref_ranks: np.ndarray) -> np.ndarray:
    """Spearman rho of each row of A (scores) against a reference rank vector. Constant rows give 0."""
    ra = rank_rows(A)
    rb = ref_ranks - ref_ranks.mean()
    ra = ra - ra.mean(axis=1, keepdims=True)
    den = np.sqrt((ra ** 2).sum(axis=1) * (rb ** 2).sum())
    return np.where(den > 0, (ra @ rb) / np.where(den > 0, den, 1.0), 0.0)


def load_table(root: Path = ROOT):
    with open(root / "data/h01_h12_scores.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    names = [r["h"] for r in rows]
    crit = list(rows[0])[2:]
    S = np.array([[float(r[c]) for c in crit] for r in rows])
    with open(root / "data/h01_h12_weights.csv", newline="", encoding="utf-8") as f:
        wr = list(csv.DictReader(f))
    sets = [k for k in wr[0] if k != "criterion"]
    assert [r["criterion"] for r in wr] == crit
    W = {s: np.array([float(r[s]) for r in wr]) for s in sets}
    return names, crit, S, W


class TabularBacktest:
    def __init__(self, root: Path = ROOT):
        self.names, self.crit, self.S, self.W = load_table(root)
        self.n_dims = len(self.crit)
        self.train_sets, self.final_sets = TRAIN_SETS, FINAL_SETS
        self.n_contexts = len(self.train_sets)
        self.ref_scores = {k: self.S @ w / w.sum() for k, w in self.W.items()}
        self.ref_ranks = {k: rank_rows(-v)[0] for k, v in self.ref_scores.items()}  # 1 = best

    def rho(self, X: np.ndarray, set_name: str) -> np.ndarray:
        """Spearman of the ranking induced by each candidate (higher weighted score = better) vs the reference."""
        sc = np.asarray(X, dtype=float) @ self.S.T
        return spearman_rows(-sc, self.ref_ranks[set_name])

    def train(self, X: np.ndarray, ctx_idx: np.ndarray) -> np.ndarray:
        f = np.zeros(len(X))
        for j, name in enumerate(self.train_sets):
            m = ctx_idx == j
            if m.any():
                f[m] = self.rho(X[m], name)
        return f

    def top_and_last(self, x: np.ndarray) -> tuple[list[str], str]:
        sc = self.S @ np.asarray(x, dtype=float)
        order = np.argsort(-sc, kind="stable")
        return [self.names[i] for i in order[:2]], self.names[order[-1]]


class ContextEvaluator:
    """Arm-facing evaluator for any Fitness (same interface as environments.benchmark.Evaluator)."""

    def __init__(self, fitness: Fitness, rng: np.random.Generator, allowed_evals: int = 0):
        self._f, self.env_rng = fitness, rng
        self.n_evals, self.allowed_evals = 0, allowed_evals
        self.discovered = np.zeros(1, dtype=bool)
        self.t = 0

    def sample_scenarios(self, n: int):
        idx = self.env_rng.integers(0, self._f.n_contexts, n)
        return idx, idx.reshape(-1, 1).astype(float)

    def evaluate(self, X: np.ndarray, scen_idx: np.ndarray) -> np.ndarray:
        if self.n_evals + len(X) > self.allowed_evals:
            raise RuntimeError("evaluation budget exceeded")
        self.n_evals += len(X)
        return self._f.train(np.clip(np.asarray(X, dtype=float), 0.0, 1.0), scen_idx)
