"""v0.2 E2: island model. K independent populations of one arm, optional ring migration, select-based merge.

ISOLATION RULE (pre-registered, enforced by tests/test_islands.py): this module may use training evaluations
(through ``Evaluator``) and the noise-free `select` contexts (through ``SelectView``). It must never touch the
`final` contexts - those belong to ``research/tournament.py`` only.
"""
from __future__ import annotations

import numpy as np

from ..agents.registry import build_arm
from ..config import ExperimentConfig
from ..environments.benchmark import BenchmarkWorld, Evaluator, SelectView

N_ISLANDS = 10
MIGRATE_EVERY = 10     # generations
N_MIGRANTS = 3         # elites sent along the ring per migration event
POOL_FACTOR = 10       # single-pool baseline has POOL_FACTOR x the population of one island (same total evaluations)


def pool_config(cfg: ExperimentConfig) -> ExperimentConfig:
    """Config of the single big population (same total evaluations as the islands). Survivor/elite counts scale."""
    return cfg.with_overrides(pop_size=cfg.pop_size * POOL_FACTOR, survivors=cfg.survivors * POOL_FACTOR,
                              elites=cfg.elites * POOL_FACTOR)


class Population:
    """One arm + its own paired evaluator (same env-stream construction as ``ArmRunner``)."""

    def __init__(self, arm_name: str, cfg: ExperimentConfig, world: BenchmarkWorld, seed: int):
        self.cfg, self.arm_name = cfg, arm_name
        self.arm = build_arm(arm_name, cfg, seed)
        self.evaluator = Evaluator(world, np.random.default_rng(np.random.SeedSequence([seed, 7777])), 0)

    def step(self) -> None:
        self.evaluator.allowed_evals += self.cfg.pop_size
        self.evaluator.t = self.arm.gen
        self.arm.step(self.evaluator, self.arm.gen)

    @property
    def n_evals(self) -> int:
        return int(self.evaluator.n_evals)


def migrate_ring(pops: list[Population], select: SelectView, k: int = N_MIGRANTS) -> None:
    """Each island sends its k best archive elites (ranked on `select`) to the next island on the ring."""
    sent = []
    for p in pops:
        fl = p.arm.archive.filled
        if len(fl) == 0:
            sent.append(None)
            continue
        sc = select.score(p.arm.deploy(fl, select.ctx))
        top = fl[np.argsort(-sc)[:k]]
        sent.append(p.arm.export_genomes(top))
    n = len(pops)
    for i, p in enumerate(pops):
        g = sent[(i - 1) % n]
        if g is not None and len(g):
            p.arm.import_genomes(g, p.arm.gen)


def merge_by_select(pops: list[Population], select: SelectView) -> dict[int, tuple[float, int]]:
    """Meta-archive: per niche keep the island elite with the best `select` score. -> {niche: (score, pop index)}."""
    best: dict[int, tuple[float, int]] = {}
    for pi, p in enumerate(pops):
        fl = p.arm.archive.filled
        if len(fl) == 0:
            continue
        sc = select.score(p.arm.deploy(fl, select.ctx))
        for n, s in zip(fl, sc):
            n = int(n)
            if n not in best or s > best[n][0]:
                best[n] = (float(s), pi)
    return best


def run_islands(arm_name: str, cfg: ExperimentConfig, world: BenchmarkWorld, rep: int, generations: int,
                migrate: bool) -> list[Population]:
    pops = [Population(arm_name, cfg, world, cfg.seed_base + 1000 * rep + i) for i in range(N_ISLANDS)]
    select = world.select_view()
    for g in range(generations):
        for p in pops:
            p.step()
        if migrate and (g + 1) % MIGRATE_EVERY == 0 and g + 1 < generations:
            migrate_ring(pops, select)
    return pops


def run_pool(arm_name: str, cfg: ExperimentConfig, world: BenchmarkWorld, rep: int, generations: int) -> list[Population]:
    big = Population(arm_name, pool_config(cfg), world, cfg.seed_base + 1000 * rep + 99)
    for _ in range(generations):
        big.step()
    return [big]
