"""Arm factory."""
from __future__ import annotations

import zlib

from ..biology.mushroom_body import MushroomBodyPolicy
from ..config import ExperimentConfig
from .controller_arm import ControllerArm
from .direct_arms import GeneticArm, RandomArm
from .policies import MLPPolicy


def arm_code(name: str) -> int:
    return zlib.crc32(name.encode()) & 0x7FFFFFFF


def build_arm(name: str, cfg: ExperimentConfig, seed: int):
    code = arm_code(name)
    # wiring seed is shared by all seeds' *structure family*; per-seed instance differs
    if name == "A_fly_plastic":
        return ControllerArm(cfg, seed, code, name, MushroomBodyPolicy(cfg, seed, False), True)
    if name == "A_fly_noplast":
        return ControllerArm(cfg, seed, code, name, MushroomBodyPolicy(cfg, seed, False), False)
    if name == "A_fly_shuffled":
        return ControllerArm(cfg, seed, code, name, MushroomBodyPolicy(cfg, seed, True), True)
    if name == "B_evolved_ann":
        target = MushroomBodyPolicy(cfg, seed, False).n_params
        return ControllerArm(cfg, seed, code, name, MLPPolicy(cfg, target), False)
    if name == "C_genetic":
        return GeneticArm(cfg, seed, code)
    if name == "D_random":
        return RandomArm(cfg, seed, code)
    raise ValueError(f"unknown arm {name!r}")
