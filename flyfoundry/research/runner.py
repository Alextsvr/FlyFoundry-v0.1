"""One (arm, seed) experimental unit: steps the arm, accounts resources, records history."""
from __future__ import annotations

import time
import tracemalloc

import numpy as np

from ..agents.registry import build_arm
from ..config import ExperimentConfig
from ..environments.benchmark import BenchmarkWorld, Evaluator
from ..evaluation.fitness import diversity, novelty


class ArmRunner:
    def __init__(self, arm_name: str, seed_idx: int, cfg: ExperimentConfig, world: BenchmarkWorld):
        self.arm_name, self.seed_idx, self.cfg, self.world = arm_name, seed_idx, cfg, world
        self.key = f"{arm_name}|{seed_idx}"
        seed = cfg.seed_base + seed_idx
        self.arm = build_arm(arm_name, cfg, seed)
        # environment stream depends only on the seed -> identical scenario / noise draws across arms (paired design)
        env_rng = np.random.default_rng(np.random.SeedSequence([seed, 7777]))
        self.evaluator = Evaluator(world, env_rng, 0)
        self.history: list[dict] = []
        self.cpu_search_total = 0.0
        self.cpu_monitor_total = 0.0
        self.peak_mem_kb = 0.0

    @property
    def generation(self) -> int:
        return self.arm.gen

    def step(self) -> dict:
        cfg, arm = self.cfg, self.arm
        gen = arm.gen
        self.evaluator.allowed_evals += cfg.pop_size  # identical per-generation budget for every arm
        base_mem = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
        if tracemalloc.is_tracing():
            tracemalloc.reset_peak()
        t0 = time.process_time()
        out = arm.step(self.evaluator, gen)
        t1 = time.process_time()
        mem_kb = (tracemalloc.get_traced_memory()[1] - base_mem) / 1024 if tracemalloc.is_tracing() else 0.0

        fl = arm.archive.filled
        ast = arm.archive.stats(cfg.viable_threshold)
        Xh = arm.heldout_candidates(self.world.ctx_heldout)
        ho = self.world.heldout_metrics(Xh) if Xh is not None else \
            {"heldout_qd": 0.0, "heldout_best": 0.0, "heldout_discovery": 0.0}
        f = out.f
        rec = {
            "gen": gen + 1, "evals": int(self.evaluator.n_evals),
            "f_mean": float(f.mean()), "f_median": float(np.median(f)), "f_best": float(f.max()),
            "f_q10": float(np.quantile(f, 0.1)), "f_q90": float(np.quantile(f, 0.9)),
            "fsh_mean": float(out.f_sh.mean()),
            "diversity": diversity(out.X),
            "novelty": novelty(out.X, arm.archive.X[fl] if len(fl) else None),
            "pop_niches": int(out.pop_niches),
            "discovered": int(self.evaluator.discovered.sum()),
            "n_mut": float(out.n_mut),
            "champion_id": int(out.ids[int(np.argmax(f))]),
            **ast, **ho,
        }
        t2 = time.process_time()
        rec["cpu_search_s"] = t1 - t0
        rec["cpu_monitor_s"] = t2 - t1
        rec["mem_peak_kb"] = mem_kb
        self.cpu_search_total += t1 - t0
        self.cpu_monitor_total += t2 - t1
        self.peak_mem_kb = max(self.peak_mem_kb, mem_kb)
        self.history.append(rec)
        return rec

    # ----------------------------------------------------------------- state
    def get_state(self) -> dict:
        return {"arm_name": self.arm_name, "seed_idx": self.seed_idx, "arm": self.arm.get_state(),
                "evaluator": self.evaluator.get_state(), "history": self.history,
                "cpu_search_total": self.cpu_search_total, "cpu_monitor_total": self.cpu_monitor_total,
                "peak_mem_kb": self.peak_mem_kb}

    def set_state(self, s: dict) -> None:
        self.arm.set_state(s["arm"])
        self.evaluator.set_state(s["evaluator"])
        self.history = list(s["history"])
        self.cpu_search_total = float(s["cpu_search_total"])
        self.cpu_monitor_total = float(s["cpu_monitor_total"])
        self.peak_mem_kb = float(s["peak_mem_kb"])
