"""Immutable experiment configuration."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

ALL_ARMS = (
    "A_fly_plastic",
    "A_fly_noplast",
    "A_fly_shuffled",
    "B_evolved_ann",
    "C_genetic",
    "D_random",
)
LLM_ARM = "E_llm_baseline"


@dataclass(frozen=True)
class ExperimentConfig:
    name: str = "flyfoundry-v0.1"
    # --- experimental design -------------------------------------------------
    world_seed: int = 20261012
    seed_base: int = 1000
    n_seeds: int = 5
    pop_size: int = 100
    gens_per_run: int = 20          # runtime knob, NOT part of the identity hash
    max_total_generations: int = 300
    arms: tuple = ALL_ARMS
    # --- benchmark world -----------------------------------------------------
    n_dims: int = 12
    n_ctx: int = 4
    n_peaks: int = 8                # includes decoys
    n_decoys: int = 2
    n_train_scenarios: int = 16
    n_heldout_scenarios: int = 16
    shift_scale: float = 0.20
    peak_length_scale: float = 0.5
    discovery_radius: float = 0.35
    obs_noise: float = 0.03
    capital_penalty: float = 2.0
    effort_penalty: float = 1.0
    unsupported_penalty: float = 1.0
    drift_amp: float = 0.0          # v0.2 E4: per-dimension peak drift amplitude; 0 = stationary world (v0.1 behaviour)
    drift_period: float = 40.0      # generations per drift cycle (only used when drift_amp > 0)
    # --- archive / diversity -------------------------------------------------
    archive_bins: int = 4
    archive_dims: tuple = (0, 1, 3)
    viable_threshold: float = 0.2
    share_sigma: float = 0.35
    # --- evolution -----------------------------------------------------------
    survivors: int = 30
    elites: int = 5
    tournament: int = 3
    p_archive_parent: float = 0.3
    p_crossover: float = 0.5
    mut_rate: float = 0.10
    mut_sigma_rel: float = 0.30
    ga_mut_rate: float = 0.20
    ga_mut_sigma: float = 0.10
    ga_immigrants: float = 0.05
    explore_sigma: float = 0.40
    # --- mushroom-body inspired controller ----------------------------------
    pn_per_dim: int = 5
    pn_width: float = 0.15
    n_kc: int = 64
    kc_active: int = 4
    kc_claws: int = 4
    kc_same_modality: int = 2
    w_init_std: float = 0.5
    eta: float = 0.5
    eta_bias: float = 0.1
    weight_decay: float = 0.01
    baseline_beta: float = 0.8
    weight_clip: float = 3.0
    # --- statistics ----------------------------------------------------------
    bootstrap_resamples: int = 2000
    min_seeds_for_claim: int = 10
    # --- persistence ---------------------------------------------------------
    checkpoints_keep: int = 3
    lineage_keep_generations: int = 50

    # -------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, tuple):
                d[k] = list(v)
        return d

    def identity_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        d.pop("gens_per_run", None)
        d.pop("name", None)
        return d

    def identity_hash(self) -> str:
        blob = json.dumps(self.identity_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExperimentConfig":
        known = {f.name: f for f in fields(cls)}
        unknown = set(d) - set(known)
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        kw = {}
        for k, v in d.items():
            if isinstance(known[k].default, tuple) and isinstance(v, list):
                v = tuple(v)
            kw[k] = v
        return cls(**kw)

    @classmethod
    def from_file(cls, path: str | Path) -> "ExperimentConfig":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def with_overrides(self, **kw) -> "ExperimentConfig":
        kw = {k: v for k, v in kw.items() if v is not None}
        return replace(self, **kw)
