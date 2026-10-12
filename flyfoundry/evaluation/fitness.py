"""Fitness sharing (niche capacity / controlled resource competition) and diversity metrics."""
from __future__ import annotations

import numpy as np


def pairwise(X: np.ndarray, Y: np.ndarray | None = None) -> np.ndarray:
    Y = X if Y is None else Y
    d2 = (X * X).sum(1)[:, None] + (Y * Y).sum(1)[None, :] - 2.0 * X @ Y.T
    return np.sqrt(np.maximum(d2, 0.0))


def shared_fitness(f: np.ndarray, X: np.ndarray, sigma: float) -> np.ndarray:
    """Goldberg-style sharing: reward at a location is divided among agents crowding it."""
    sh = np.maximum(0.0, 1.0 - pairwise(X) / sigma)
    count = sh.sum(axis=1)  # >= 1 (self)
    return np.where(f > 0, f / count, f)


def diversity(X: np.ndarray) -> float:
    n = len(X)
    if n < 2:
        return 0.0
    d = pairwise(X)
    return float(d.sum() / (n * (n - 1)) / np.sqrt(X.shape[1]))


def novelty(X: np.ndarray, archive_X: np.ndarray | None, k: int = 5) -> float:
    ref = X if archive_X is None or len(archive_X) == 0 else np.vstack([X, archive_X])
    d = np.sort(pairwise(X, ref), axis=1)[:, 1:k + 1]  # drop self (distance 0)
    return float(d.mean() / np.sqrt(X.shape[1]))
