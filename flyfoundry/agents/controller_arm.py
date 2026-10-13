"""Population of neural controllers (arms A and B) evolved with a MAP-Elites-assisted GA.

Both A and B share this exact evolutionary engine; only the policy differs
(and A optionally has lifetime plasticity), so A-vs-B isolates the architecture.
"""
from __future__ import annotations

import numpy as np

from ..config import ExperimentConfig
from ..evaluation.fitness import shared_fitness
from ..evolution.archive import MapElitesArchive
from .base import Arm, StepOutput


class ControllerArm(Arm):
    uses_context = True

    def __init__(self, cfg: ExperimentConfig, seed: int, arm_code: int, name: str, policy, plastic: bool):
        super().__init__(cfg, seed, arm_code)
        self.name, self.policy, self.plastic = name, policy, plastic
        P, N = policy.n_params, cfg.pop_size
        self.archive = MapElitesArchive(cfg.n_dims, cfg.archive_bins, cfg.archive_dims,
                                        genome_size=P, pheno_size=P if plastic else 0)
        self.genome = policy.init_params(self.rng, N)
        self.learned = self.genome.copy() if plastic else self.genome
        self.baseline = np.full(N, np.nan)
        self.champions: list = []
        self.ids = self.lineage.new_ids(N)
        self.lineage.birth(self.ids, -np.ones(N), -np.ones(N), 0, np.zeros(N), np.zeros(N))

    # ------------------------------------------------------------------ step
    def step(self, evaluator, gen: int) -> StepOutput:
        cfg, N = self.cfg, len(self.ids)
        scen, ctx = evaluator.sample_scenarios(N)
        eps = self.rng.normal(0.0, cfg.explore_sigma, (N, cfg.n_dims)).astype(np.float32)
        Xo, cache = self.policy.forward(self.learned, ctx, eps)
        X = Xo.astype(np.float64)
        f = evaluator.evaluate(X, scen)
        fsh = shared_fitness(f, X, cfg.share_sigma)
        self.archive.add_batch(X, f, self.ids, gen, genome=self.genome,
                               pheno=self.learned if self.plastic else None)
        self.lineage.observe(self.ids, f)
        pop_niches = self._niche_count(X)
        if self.plastic:
            delta = np.where(np.isnan(self.baseline), 0.0, f - self.baseline)
            self.policy.plastic_update(self.learned, self.genome, cache, eps, delta)
            self.baseline = np.where(np.isnan(self.baseline), f,
                                     cfg.baseline_beta * self.baseline + (1 - cfg.baseline_beta) * f)
        out = StepOutput(X, f, fsh, self.ids.copy(), 0.0, pop_niches)
        out.n_mut = self._reproduce(fsh, gen)
        self._finish_generation(gen, X, f, out.ids)
        return out

    def _reproduce(self, fsh, gen) -> float:
        cfg, N, P = self.cfg, len(self.ids), self.policy.n_params
        order = np.argsort(-fsh)
        surv = order[: cfg.survivors]
        self.lineage.death(self.ids[order[cfg.survivors:]], gen)
        n_new = N - len(surv)
        fl = self.archive.filled
        scale = self.policy.init_scale
        kids = np.zeros((n_new, P), dtype=np.float32)
        p1 = np.zeros(n_new, dtype=np.int64)
        p2 = -np.ones(n_new, dtype=np.int64)
        ops = np.zeros(n_new, dtype=np.int64)
        nmut = np.zeros(n_new, dtype=np.int64)

        def parent():
            if len(fl) > 0 and self.rng.random() < cfg.p_archive_parent:
                n = int(self.rng.choice(fl))
                return self.archive.genome[n], int(self.archive.owner[n])
            cand = self.rng.choice(surv, size=cfg.tournament)
            b = int(cand[np.argmax(fsh[cand])])
            return self.genome[b], int(self.ids[b])

        for j in range(n_new):
            g1, i1 = parent()
            if self.rng.random() < cfg.p_crossover:
                g2, i2 = parent()
                mask = self.rng.random(P) < 0.5
                child, ops[j], p2[j] = np.where(mask, g1, g2), 2, i2
            else:
                child, ops[j] = g1.copy(), 1
            m = self.rng.random(P) < cfg.mut_rate
            child = child + (m * self.rng.standard_normal(P) * cfg.mut_sigma_rel * scale).astype(np.float32)
            kids[j], p1[j], nmut[j] = child, i1, int(m.sum())
        new_ids = self.lineage.new_ids(n_new)
        self.lineage.birth(new_ids, p1, p2, gen + 1, ops, nmut)
        self.genome = np.concatenate([self.genome[surv], kids]).astype(np.float32)
        if self.plastic:
            self.learned = np.concatenate([self.learned[surv], kids]).astype(np.float32)
        else:
            self.learned = self.genome
        self.baseline = np.concatenate([self.baseline[surv], np.full(n_new, np.nan)])
        self.ids = np.concatenate([self.ids[surv], new_ids])
        return float(nmut.mean()) if n_new else 0.0

    # --------------------------------------------------------------- held-out
    def heldout_candidates(self, eval_ctx):
        fl = self.archive.filled
        if len(fl) == 0:
            return None
        params = (self.archive.pheno if self.plastic else self.archive.genome)[fl]
        S = len(eval_ctx)
        Xh = np.zeros((len(fl), S, self.cfg.n_dims))
        zero = np.zeros((len(fl), self.cfg.n_dims), dtype=np.float32)
        for s in range(S):
            ctx = np.repeat(eval_ctx[s][None], len(fl), axis=0)
            Xh[:, s, :] = self.policy.forward(params, ctx, zero)[0]
        return Xh

    def population_candidates(self, eval_ctx):
        """Current population (survivors with their learned weights + newborns) acting without exploration noise."""
        N, S = len(self.ids), len(eval_ctx)
        out = np.zeros((N, S, self.cfg.n_dims))
        zero = np.zeros((N, self.cfg.n_dims), dtype=np.float32)
        for s in range(S):
            ctx = np.repeat(eval_ctx[s][None], N, axis=0)
            out[:, s, :] = self.policy.forward(self.learned, ctx, zero)[0]
        return out

    def model_card(self):
        c = self.policy.model_card()
        c["plasticity_enabled"] = bool(self.plastic)
        return c

    # ------------------------------------------------------------------ state
    def get_state(self):
        s = self._base_state()
        s.update({"genome": self.genome, "baseline": self.baseline,
                  "champions": np.array(self.champions, dtype=np.int64).reshape(-1, 2)})
        if self.plastic:
            s["learned"] = self.learned
        return s

    def set_state(self, s):
        self._load_base(s)
        self.genome = np.asarray(s["genome"]).copy()
        self.learned = np.asarray(s["learned"]).copy() if self.plastic else self.genome
        self.baseline = np.asarray(s["baseline"]).copy()
        self.champions = [list(map(int, r)) for r in np.asarray(s["champions"])]
