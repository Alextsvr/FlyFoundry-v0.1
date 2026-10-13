"""Arms C (genetic algorithm) and D (random search): direct 12-D candidate genomes, no neural controller."""
from __future__ import annotations

import numpy as np

from ..config import ExperimentConfig
from ..evaluation.fitness import shared_fitness
from ..evolution.archive import MapElitesArchive
from .base import Arm, StepOutput


class _DirectArm(Arm):
    uses_context = False

    def __init__(self, cfg, seed, arm_code, name):
        super().__init__(cfg, seed, arm_code)
        self.name = name
        self.archive = MapElitesArchive(cfg.n_dims, cfg.archive_bins, cfg.archive_dims)
        self.champions: list = []
        self.X = self.rng.random((cfg.pop_size, cfg.n_dims))
        self.ids = self.lineage.new_ids(cfg.pop_size)
        n = cfg.pop_size
        self.lineage.birth(self.ids, -np.ones(n), -np.ones(n), 0, np.zeros(n), np.zeros(n))

    def _evaluate(self, evaluator, gen):
        scen, _ = evaluator.sample_scenarios(len(self.X))   # context is NOT observable to direct arms
        f = evaluator.evaluate(self.X, scen)
        fsh = shared_fitness(f, self.X, self.cfg.share_sigma)
        self.archive.add_batch(self.X, f, self.ids, gen)
        self.lineage.observe(self.ids, f)
        return f, fsh

    def heldout_candidates(self, eval_ctx):
        fl = self.archive.filled
        if len(fl) == 0:
            return None
        return np.repeat(self.archive.X[fl][:, None, :], len(eval_ctx), axis=1)

    def population_candidates(self, eval_ctx):
        return np.repeat(self.X[:, None, :], len(eval_ctx), axis=1)

    def get_state(self):
        s = self._base_state()
        s.update({"X": self.X, "champions": np.array(self.champions, dtype=np.int64).reshape(-1, 2)})
        return s

    def set_state(self, s):
        self._load_base(s)
        self.X = np.asarray(s["X"]).copy()
        self.champions = [list(map(int, r)) for r in np.asarray(s["champions"])]

    def model_card(self):
        return {"model_type": self.name, "trainable_parameters": self.cfg.n_dims}


class GeneticArm(_DirectArm):
    def __init__(self, cfg, seed, arm_code):
        super().__init__(cfg, seed, arm_code, "genetic_algorithm")

    def step(self, evaluator, gen):
        cfg, N, D = self.cfg, len(self.X), self.cfg.n_dims
        f, fsh = self._evaluate(evaluator, gen)
        pop_niches = self._niche_count(self.X)
        out = StepOutput(self.X.copy(), f, fsh, self.ids.copy(), 0.0, pop_niches)
        order = np.argsort(-fsh)
        elites = order[: cfg.elites]
        self.lineage.death(self.ids[order[cfg.elites:]], gen)
        n_new = N - len(elites)
        n_imm = int(round(cfg.ga_immigrants * N))
        kids = np.zeros((n_new, D))
        p1 = -np.ones(n_new, dtype=np.int64)
        p2 = -np.ones(n_new, dtype=np.int64)
        ops = np.zeros(n_new, dtype=np.int64)
        nmut = np.zeros(n_new, dtype=np.int64)

        def tour():
            c = self.rng.integers(0, N, cfg.tournament)
            return int(c[np.argmax(fsh[c])])

        for j in range(n_new):
            if j < n_imm:  # random immigrants maintain diversity
                kids[j] = self.rng.random(D)
                continue
            a = tour()
            if self.rng.random() < cfg.p_crossover:
                b = tour()
                mask = self.rng.random(D) < 0.5
                child, ops[j], p2[j] = np.where(mask, self.X[a], self.X[b]), 2, self.ids[b]
            else:
                child, ops[j] = self.X[a].copy(), 1
            m = self.rng.random(D) < cfg.ga_mut_rate
            child = np.clip(child + m * self.rng.normal(0, cfg.ga_mut_sigma, D), 0.0, 1.0)
            kids[j], p1[j], nmut[j] = child, self.ids[a], int(m.sum())
        new_ids = self.lineage.new_ids(n_new)
        self.lineage.birth(new_ids, p1, p2, gen + 1, ops, nmut)
        self.X = np.vstack([self.X[elites], kids])
        self.ids = np.concatenate([self.ids[elites], new_ids])
        out.n_mut = float(nmut.mean())
        self._finish_generation(gen, out.X, f, out.ids)
        return out


class RandomArm(_DirectArm):
    def __init__(self, cfg, seed, arm_code):
        super().__init__(cfg, seed, arm_code, "random_search")

    def step(self, evaluator, gen):
        cfg, N = self.cfg, len(self.X)
        f, fsh = self._evaluate(evaluator, gen)
        out = StepOutput(self.X.copy(), f, fsh, self.ids.copy(), 0.0, self._niche_count(self.X))
        self.lineage.death(self.ids, gen)
        self.X = self.rng.random((N, cfg.n_dims))
        self.ids = self.lineage.new_ids(N)
        self.lineage.birth(self.ids, -np.ones(N), -np.ones(N), gen + 1, np.zeros(N), np.zeros(N))
        self._finish_generation(gen, out.X, f, out.ids)
        return out
