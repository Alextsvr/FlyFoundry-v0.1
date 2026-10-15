"""Phase 1 layer C: the idea space as a Fitness plugin (docs/PHASE1_SPEC.md sections 4-5).

A candidate is a tuple (customer, problem, solution, revenue, channel) from ``data/taxonomy_v4.json``. Each component carries
curated 1-5 priors for a few of the 13 synthesis criteria; a combination's criterion value is the mean over the components
that define it (min for reg_platform, the worst case). Fitness in a context = the weighted mean under one of the five
weight sets, rescaled to 0..1; hard gates and forbidden pairs score -0.5. These numbers are judgement priors, not evidence.
"""
from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("customer", "problem", "solution", "revenue", "channel")
CRITERIA = ("demand", "wtp_solo", "buyer", "data_access", "automation_leverage", "mvp", "delivery_economics",
            "acquisition", "competition", "reg_platform", "recurrence", "defensibility", "speed")
MIN_RULE = {"reg_platform"}
GATE_SCORE = -0.5


def load_weights(root: Path = ROOT):
    with open(root / "data/h01_h12_weights.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert tuple(r["criterion"] for r in rows) == CRITERIA
    sets = [k for k in rows[0] if k != "criterion"]
    return sets, np.array([[float(r[s]) for r in rows] for s in sets])      # (n_sets, 13)


class IdeaSpace:
    def __init__(self, root: Path = ROOT):
        t = json.loads((root / "data/taxonomy_v4.json").read_text(encoding="utf-8"))
        self.meta, comp = t["meta"], t["components"]
        self.names = {k: list(comp[k]) for k in TYPES}
        self.sizes = tuple(len(self.names[k]) for k in TYPES)
        self.n_total = int(np.prod(self.sizes))
        self.set_names, self.W = load_weights(root)
        self.n_dims, self.n_contexts = len(TYPES), len(self.set_names)
        # per component: {criterion: value}
        self._vals = {k: [dict(zip(self.meta["fields"][k], map(float, comp[k][n]))) for n in self.names[k]] for k in TYPES}
        self._forbidden = {(a, self.names[a].index(x), b, self.names[b].index(y)) for a, x, b, y in self.meta["forbidden_pairs"]}
        self._features = None
        oc = json.loads((root / "data/owner_constraints.json").read_text(encoding="utf-8"))
        self.owner_constraints = oc
        self._gated_customers = {self.names["customer"].index(c) for c in oc["hard_gate_customers"]}
        self._flag_customers = {self.names["customer"].index(c) for c in oc["flag_customers"]}

    # ------------------------------------------------------------------ decoding
    def decode_indices(self, X: np.ndarray) -> np.ndarray:
        X = np.clip(np.asarray(X, dtype=float), 0.0, 1.0)
        return np.minimum((X * np.array(self.sizes)).astype(np.int64), np.array(self.sizes) - 1)

    def describe(self, idx) -> dict:
        return {k: self.names[k][int(i)] for k, i in zip(TYPES, idx)}

    # ------------------------------------------------------------------ features (all combinations, vectorised)
    def all_indices(self) -> np.ndarray:
        return np.array(list(itertools.product(*[range(s) for s in self.sizes])), dtype=np.int64)

    def features_of(self, idx: np.ndarray):
        """idx (N,5) -> features (N,13) in 1..5, gate mask (N,) bool (True = gated out), legal-flag mask."""
        N = len(idx)
        F = np.zeros((N, len(CRITERIA)))
        for ci, c in enumerate(CRITERIA):
            cols = []
            for ti, tname in enumerate(TYPES):
                if c in self.meta["fields"][tname]:
                    table = np.array([v[c] for v in self._vals[tname]])
                    cols.append(table[idx[:, ti]])
            S = np.stack(cols, axis=1)
            F[:, ci] = S.min(axis=1) if c in MIN_RULE else S.mean(axis=1)
        reg = F[:, CRITERIA.index("reg_platform")]
        gated = reg <= self.meta["hard_gate_reg_at_most"]
        for a, i, b, j in self._forbidden:
            gated |= (idx[:, TYPES.index(a)] == i) & (idx[:, TYPES.index(b)] == j)
        gated |= np.isin(idx[:, 0], list(self._gated_customers))      # owner's conflict-of-interest gate
        legal = (reg <= self.meta["legal_flag_reg_at_most"]) | np.isin(idx[:, 0], list(self._flag_customers))
        return F, gated, legal

    def scores_from_features(self, F: np.ndarray, gated: np.ndarray) -> np.ndarray:
        """(N,13) features -> (N, n_sets) scores in 0..1 (gated -> -0.5)."""
        s = (F @ self.W.T) / self.W.sum(axis=1)[None, :]
        s = (s - 1.0) / 4.0
        s[gated] = GATE_SCORE
        return s

    def exhaustive(self):
        idx = self.all_indices()
        F, gated, legal = self.features_of(idx)
        return idx, F, gated, legal, self.scores_from_features(F, gated)

    # ------------------------------------------------------------------ Fitness plugin protocol
    def train(self, X: np.ndarray, ctx_idx: np.ndarray) -> np.ndarray:
        idx = self.decode_indices(X)
        F, gated, _ = self.features_of(idx)
        S = self.scores_from_features(F, gated)
        return S[np.arange(len(S)), np.asarray(ctx_idx, dtype=int)]


def load_seeds(root: Path = ROOT):
    """Named seed ideas with their own 13-criterion vectors (H01-H12 from the synthesis; N1-N7 unresearched priors)."""
    out = []
    with open(root / "data/h01_h12_scores.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"id": r["h"], "name": r["name"], "confidence": "researched (3 tracks)",
                        "f": [float(r[k]) for k in r if k not in ("h", "name")]})
    with open(root / "data/seeds_new.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"id": r["id"], "name": r["name"], "confidence": r["confidence"],
                        "f": [float(r[c]) for c in CRITERIA]})
    return out
