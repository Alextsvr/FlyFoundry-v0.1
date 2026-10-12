"""Bootstrap statistics over independent seeds (percentile CI, paired differences)."""
from __future__ import annotations

import numpy as np


def bootstrap_mean_ci(values, n_resamples: int = 2000, alpha: float = 0.05, seed: int = 0):
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    if len(v) == 1:
        return float(v[0]), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), (n_resamples, len(v)))
    means = v[idx].mean(axis=1)
    return float(v.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_diff_ci(a, b, n_resamples: int = 2000, alpha: float = 0.05, seed: int = 0):
    """CI for mean(a - b) with seeds paired by index."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = min(len(a), len(b))
    return bootstrap_mean_ci(a[:n] - b[:n], n_resamples, alpha, seed)
