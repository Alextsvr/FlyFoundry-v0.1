"""MAP-Elites style niche archive (quality-diversity container)."""
from __future__ import annotations

import numpy as np


class MapElitesArchive:
    def __init__(self, n_dims: int, bins: int, desc_dims: tuple, genome_size: int = 0, pheno_size: int = 0):
        self.n_dims, self.bins, self.desc_dims = n_dims, bins, tuple(desc_dims)
        n = bins ** len(self.desc_dims)
        self.n_niches = n
        self.fit = np.full(n, -np.inf)
        self.X = np.zeros((n, n_dims))
        self.owner = np.full(n, -1, dtype=np.int64)
        self.gen = np.full(n, -1, dtype=np.int64)
        self.genome = np.zeros((n, genome_size), dtype=np.float32) if genome_size else None
        self.pheno = np.zeros((n, pheno_size), dtype=np.float32) if pheno_size else None

    def niche_of(self, X: np.ndarray) -> np.ndarray:
        b = np.minimum((np.clip(X[:, list(self.desc_dims)], 0, 1) * self.bins).astype(np.int64), self.bins - 1)
        idx = np.zeros(len(X), dtype=np.int64)
        for j in range(b.shape[1]):
            idx = idx * self.bins + b[:, j]
        return idx

    def add_batch(self, X, f, ids, gen, genome=None, pheno=None) -> int:
        nich = self.niche_of(X)
        improved = 0
        for i in np.argsort(f):  # ascending: the best per niche is written last
            n = nich[i]
            if f[i] > self.fit[n]:
                self.fit[n], self.X[n], self.owner[n], self.gen[n] = f[i], X[i], ids[i], gen
                if self.genome is not None:
                    self.genome[n] = genome[i]
                if self.pheno is not None:
                    self.pheno[n] = pheno[i]
                improved += 1
        return improved

    @property
    def filled(self) -> np.ndarray:
        return np.where(np.isfinite(self.fit))[0]

    def stats(self, viable_threshold: float) -> dict:
        fl = self.filled
        fit = self.fit[fl]
        return {"niches_filled": int(len(fl)), "niches_viable": int((fit >= viable_threshold).sum()),
                "qd_score": float(np.maximum(fit, 0).sum()), "n_niches": self.n_niches}

    def get_state(self):
        s = {"fit": self.fit, "X": self.X, "owner": self.owner, "gen": self.gen}
        if self.genome is not None:
            s["genome"] = self.genome
        if self.pheno is not None:
            s["pheno"] = self.pheno
        return s

    def set_state(self, s):
        self.fit, self.X, self.owner, self.gen = (np.asarray(s[k]).copy() for k in ("fit", "X", "owner", "gen"))
        if "genome" in s:
            self.genome = np.asarray(s["genome"]).copy()
        if "pheno" in s:
            self.pheno = np.asarray(s["pheno"]).copy()
