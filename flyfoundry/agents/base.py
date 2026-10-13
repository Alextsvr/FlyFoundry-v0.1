"""Common arm machinery: archive, lineage, RNG, state (de)serialization."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import ExperimentConfig
from ..evolution.archive import MapElitesArchive
from ..evolution.lineage import Lineage


@dataclass
class StepOutput:
    X: np.ndarray          # candidates evaluated this generation (N, D)
    f: np.ndarray          # raw training fitness
    f_sh: np.ndarray       # shared fitness
    ids: np.ndarray        # agent ids
    n_mut: float           # mean mutated genes of the offspring produced
    pop_niches: int        # distinct archive niches occupied by this generation


class Arm:
    name = "base"
    uses_context = False

    def __init__(self, cfg: ExperimentConfig, seed: int, arm_code: int):
        self.cfg = cfg
        self.seed = seed
        self.rng = np.random.default_rng(np.random.SeedSequence([seed, arm_code, 424242]))
        self.lineage = Lineage()
        self.archive: MapElitesArchive | None = None
        self.gen = 0
        self.ids = np.zeros(0, dtype=np.int64)
        self.champions: list = []

    # -- interface -------------------------------------------------------------
    def step(self, evaluator, gen: int) -> StepOutput:
        raise NotImplementedError

    def heldout_candidates(self, eval_ctx: np.ndarray):
        """-> (E, S, D) candidates from the arm's archive, or None. Uses TRAINING-selected elites only."""
        raise NotImplementedError

    def population_candidates(self, eval_ctx: np.ndarray) -> np.ndarray:
        """-> (N, S, D): what the CURRENT population would deploy in each of the S given contexts (E4 tracking metric)."""
        raise NotImplementedError

    def living_ids(self):
        return self.ids

    def model_card(self) -> dict:
        return {}

    def get_state(self) -> dict:
        raise NotImplementedError

    def set_state(self, s: dict) -> None:
        raise NotImplementedError

    # -- shared helpers --------------------------------------------------------
    def _base_state(self) -> dict:
        return {"rng": self.rng.bit_generator.state, "lineage": self.lineage.get_state(),
                "archive": self.archive.get_state(), "ids": self.ids, "gen": self.gen}

    def _load_base(self, s: dict) -> None:
        self.rng.bit_generator.state = s["rng"]
        self.lineage.set_state(s["lineage"])
        self.archive.set_state(s["archive"])
        self.ids = np.asarray(s["ids"]).copy()
        self.gen = int(s["gen"])

    def _niche_count(self, X) -> int:
        return int(len(np.unique(self.archive.niche_of(X))))

    def _finish_generation(self, gen, X, f, ids) -> None:
        """Record the generation champion and prune old genealogy branches."""
        i = int(np.argmax(f))
        self.champions.append([int(gen), int(ids[i])])
        keep_n = self.cfg.lineage_keep_generations
        self.champions = self.champions[-keep_n:]
        self.gen = gen + 1
        if (gen + 1) % 10 == 0:
            roots = list(self.ids) + [int(o) for o in self.archive.owner[self.archive.filled]] \
                + [c[1] for c in self.champions]
            self.lineage.prune(roots)
