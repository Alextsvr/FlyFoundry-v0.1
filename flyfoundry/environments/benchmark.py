"""Synthetic business-opportunity benchmark (hidden landscape, train / held-out split).

A candidate is a vector x in [0,1]^12 decoded into a structured opportunity
(see ``research/opportunities.py``). The *hidden* landscape consists of a few
"real" peaks (valuable, feasible opportunities) and "decoys" (look valuable,
need unrealistic capital). Peak locations shift with an observable market
context z (4 numbers) through a hidden linear map, so a controller that reads
the context can in principle do better than a context-blind candidate.

Training feedback: noisy, only on 16 training contexts.
Held-out reporting: noise-free, on 16 *different* contexts; never used to
guide evolution (only ``Evaluator.evaluate`` is exposed to agents).

This is a synthetic benchmark: scores here are NOT evidence of real-world
demand or revenue.
"""
from __future__ import annotations

import hashlib

import numpy as np

from ..config import ExperimentConfig

# decoded-dimension roles (documented in docs/EXPERIMENT_DESIGN.md)
DIM_CUSTOMER, DIM_PROBLEM, DIM_SOLUTION, DIM_REVENUE = 0, 1, 2, 3
DIM_CAPITAL, DIM_EFFORT, DIM_EVIDENCE, DIM_DIFFERENTIATION = 4, 5, 6, 7
DIM_DEMAND_CLAIM, DIM_CHANNEL, DIM_AUTOMATION, DIM_RISK = 8, 9, 10, 11


class BudgetExceeded(RuntimeError):
    pass


class BenchmarkWorld:
    """Hidden world. Construct once per experiment; deterministic from config."""

    def __init__(self, cfg: ExperimentConfig):
        self.cfg = cfg
        rng = np.random.default_rng(np.random.SeedSequence([cfg.world_seed, 101]))
        D, P, K = cfg.n_dims, cfg.n_peaks, cfg.n_ctx
        c = rng.uniform(0.1, 0.9, (P, D))
        v = rng.uniform(0.55, 0.95, P)
        decoy = np.zeros(P, dtype=bool)
        decoy[rng.permutation(P)[: cfg.n_decoys]] = True
        real = ~decoy
        nr = int(real.sum())
        c[real, DIM_CAPITAL] = rng.uniform(0.0, 0.2, nr)
        c[real, DIM_EFFORT] = rng.uniform(0.1, 0.45, nr)
        c[real, DIM_EVIDENCE] = rng.uniform(0.5, 0.9, nr)
        c[real, DIM_DEMAND_CLAIM] = rng.uniform(0.3, 0.5, nr)
        c[decoy, DIM_CAPITAL] = rng.uniform(0.7, 0.95, cfg.n_decoys)
        v[decoy] = rng.uniform(0.95, 1.0, cfg.n_decoys)
        S = rng.normal(0, cfg.shift_scale, (P, D, K))
        S[:, DIM_CAPITAL, :] = 0.0
        S[:, DIM_EFFORT, :] = 0.0
        self._centers = c
        self._values = v
        self._decoy = decoy
        self._shift = S
        self.ctx_train = rng.random((cfg.n_train_scenarios, K))
        self.ctx_heldout = rng.random((cfg.n_heldout_scenarios, K))
        # v0.2 E4 drift: separate RNG stream so that the stationary world (drift_amp = 0) is bit-identical to v0.1
        self._drift_dir = self._drift_phase = None
        if cfg.drift_amp > 0:
            drng = np.random.default_rng(np.random.SeedSequence([cfg.world_seed, 202]))
            u = drng.standard_normal((P, D))
            u[:, DIM_CAPITAL] = 0.0
            u[:, DIM_EFFORT] = 0.0
            self._drift_dir = u
            self._drift_phase = drng.uniform(0.0, 2 * np.pi, P)

    # ------------------------------------------------------------ fingerprint
    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for a in (self._centers, self._values, self._decoy, self._shift, self.ctx_train, self.ctx_heldout):
            h.update(np.ascontiguousarray(a).tobytes())
        if self._drift_dir is not None:  # only when drifting, so stationary fingerprints stay unchanged
            for a in (self._drift_dir, self._drift_phase, np.array([self.cfg.drift_amp, self.cfg.drift_period])):
                h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()

    # ----------------------------------------------------------- core scoring
    def _penalty(self, X: np.ndarray) -> np.ndarray:
        cfg = self.cfg
        cap = cfg.capital_penalty * np.maximum(0.0, X[:, DIM_CAPITAL] - 0.25)
        eff = cfg.effort_penalty * np.maximum(0.0, X[:, DIM_EFFORT] - 0.5)
        uns = cfg.unsupported_penalty * np.maximum(0.0, X[:, DIM_DEMAND_CLAIM] - X[:, DIM_EVIDENCE] - 0.15)
        return cap + eff + uns

    def drift_offset(self, t: float) -> np.ndarray | None:
        """(P,D) displacement of the peak centres at time t (generation index); None for a stationary world."""
        if self._drift_dir is None:
            return None
        phase = 2 * np.pi * float(t) / self.cfg.drift_period + self._drift_phase
        return self.cfg.drift_amp * self._drift_dir * np.sin(phase)[:, None]

    def _shifted_centers(self, ctx: np.ndarray, t: float = 0.0) -> np.ndarray:
        """ctx (n,K) -> (n,P,D)"""
        sh = np.einsum("pdk,nk->npd", self._shift, ctx - 0.5)
        off = self.drift_offset(t)
        base = self._centers[None] if off is None else self._centers[None] + off[None]
        return np.clip(base + sh, 0.0, 1.0)

    def _dist_match(self, X: np.ndarray, ctx: np.ndarray, t: float = 0.0):
        cs = self._shifted_centers(ctx, t)
        dist = np.linalg.norm(X[:, None, :] - cs, axis=2)  # (n,P)
        match = self._values[None] * np.exp(-dist / self.cfg.peak_length_scale)
        return dist, match

    # ------------------------------------------------------------- training
    def train_fitness(self, X: np.ndarray, scen_idx: np.ndarray, noise: np.ndarray, t: float = 0.0):
        ctx = self.ctx_train[scen_idx]
        dist, match = self._dist_match(X, ctx, t)
        f = match.max(axis=1) - self._penalty(X) + noise
        f = np.clip(f, -1.0, 1.0)
        hit = (dist <= self.cfg.discovery_radius) & (
            match - self._penalty(X)[:, None] >= 0.5 * self._values[None]) & (~self._decoy[None])
        return f, hit.any(axis=0)

    # ------------------------------------------------------------- held-out
    def heldout_metrics(self, Xh: np.ndarray, t: float = 0.0) -> dict:
        """Xh: (E, S, D) candidates (entry e, held-out context s). Noise-free, evaluated at time t."""
        cfg = self.cfg
        E, S, _ = Xh.shape
        real = ~self._decoy
        denom = float(self._values[real].sum())
        qd, best, cov = [], [], []
        for s in range(S):
            ctx = np.repeat(self.ctx_heldout[s][None], E, axis=0)
            dist, match = self._dist_match(Xh[:, s, :], ctx, t)
            net = match - self._penalty(Xh[:, s, :])[:, None]
            per_peak = np.maximum(net, 0.0).max(axis=0)
            qd.append(per_peak[real].sum() / denom)
            best.append(max(0.0, float(net.max())))
            found = ((dist <= cfg.discovery_radius) & (net >= 0.5 * self._values[None])).any(axis=0)
            cov.append(found[real].sum() / real.sum())
        return {"heldout_qd": float(np.mean(qd)), "heldout_best": float(np.mean(best)),
                "heldout_discovery": float(np.mean(cov))}

    def static_candidate_heldout(self, x: np.ndarray) -> float:
        """Mean held-out net score of ONE fixed candidate across held-out contexts (report only)."""
        X = np.repeat(x[None], len(self.ctx_heldout), axis=0)
        dist, match = self._dist_match(X, self.ctx_heldout)
        net = match.max(axis=1) - self._penalty(X)
        return float(np.mean(net))

    @property
    def n_real_peaks(self) -> int:
        return int((~self._decoy).sum())

    @property
    def n_peaks(self) -> int:
        return len(self._values)


class Evaluator:
    """The only interface agents get: budgeted, noisy training evaluation."""

    def __init__(self, world: BenchmarkWorld, env_rng: np.random.Generator, allowed_evals: int = 0):
        self._world = world
        self.env_rng = env_rng
        self.n_evals = 0
        self.allowed_evals = allowed_evals
        self.discovered = np.zeros(world.n_peaks, dtype=bool)  # telemetry, never read by agents
        self.t = 0  # current generation clock, set by the runner before each step (drifting worlds only use it)

    def sample_scenarios(self, n: int):
        idx = self.env_rng.integers(0, self._world.cfg.n_train_scenarios, n)
        return idx, self._world.ctx_train[idx].copy()

    def evaluate(self, X: np.ndarray, scen_idx: np.ndarray) -> np.ndarray:
        n = len(X)
        if self.n_evals + n > self.allowed_evals:
            raise BudgetExceeded(f"evaluation budget exceeded: {self.n_evals}+{n} > {self.allowed_evals}")
        X = np.clip(np.asarray(X, dtype=np.float64), 0.0, 1.0)
        noise = self.env_rng.normal(0.0, self._world.cfg.obs_noise, n)
        f, hit = self._world.train_fitness(X, scen_idx, noise, self.t)
        self.discovered |= hit
        self.n_evals += n
        return f

    def get_state(self):
        return {"n_evals": self.n_evals, "allowed_evals": self.allowed_evals,
                "discovered": self.discovered.copy(), "env_rng": self.env_rng.bit_generator.state}

    def set_state(self, s):
        self.n_evals = int(s["n_evals"])
        self.allowed_evals = int(s["allowed_evals"])
        self.discovered = np.asarray(s["discovered"], dtype=bool).copy()
        self.env_rng.bit_generator.state = s["env_rng"]
