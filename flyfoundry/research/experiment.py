"""Experiment orchestration: lock-step advance of all (arm, seed) runners, checkpoint payloads, resume."""
from __future__ import annotations

try:
    import resource          # Unix only; the research code must stay importable on Windows (peak memory is then reported as 0)
except ImportError:  # pragma: no cover
    resource = None
import time
import tracemalloc
import uuid
from datetime import datetime, timezone

from ..agents import llm_baseline
from ..config import ALL_ARMS, LLM_ARM, SCHEMA_VERSION, ExperimentConfig
from ..environments.benchmark import BenchmarkWorld
from ..storage.checkpoint import CheckpointCorrupt, ConfigMismatch
from . import provenance
from .runner import ArmRunner


def _rss_mb() -> float:
    if resource is None:
        return 0.0
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def shard_seeds(n_seeds: int, index: int, n_shards: int) -> list[int]:
    """Seed indices of shard ``index`` (0-based) out of ``n_shards``: contiguous blocks, sizes differ by at most one.

    Seeds are whole experimental units (every arm runs the same seed indices), so a shard is a self-contained
    sub-experiment and the union over all shards is exactly range(n_seeds).
    """
    if n_shards < 1 or not 0 <= index < n_shards:
        raise ValueError(f"invalid shard {index}/{n_shards}")
    if n_shards > n_seeds:
        raise ValueError(f"cannot split {n_seeds} seeds into {n_shards} shards")
    base, extra = divmod(n_seeds, n_shards)
    start = index * base + min(index, extra)
    return list(range(start, start + base + (1 if index < extra else 0)))


class Experiment:
    def __init__(self, cfg: ExperimentConfig, seeds=None):
        self.cfg = cfg
        self.world = BenchmarkWorld(cfg)
        self.seeds = sorted(range(cfg.n_seeds) if seeds is None else (int(x) for x in seeds))
        if not self.seeds or len(set(self.seeds)) != len(self.seeds) or not set(self.seeds) <= set(range(cfg.n_seeds)):
            raise ValueError(f"invalid seed subset {self.seeds} for n_seeds={cfg.n_seeds}")
        self.runners: dict[str, ArmRunner] = {}
        for arm in cfg.arms:
            for s in self.seeds:
                r = ArmRunner(arm, s, cfg, self.world)
                self.runners[r.key] = r
        ok, reason = llm_baseline.availability()
        # Arm E is never simulated. v0.1 does not schedule LLM calls even when an endpoint exists.
        self.llm = {"arm": LLM_ARM, "status": "NOT RUN",
                    "reason": reason if not ok else "endpoint configured, but v0.1 does not yet schedule LLM evaluations"}
        self.runs: list[dict] = []
        self.model_cards = {a: next(r for r in self.runners.values() if r.arm_name == a).arm.model_card()
                            for a in cfg.arms}

    # ------------------------------------------------------------ properties
    @property
    def is_full(self) -> bool:
        """True when this experiment holds every seed (i.e. it is not one shard of a larger experiment)."""
        return self.seeds == list(range(self.cfg.n_seeds))

    @property
    def generation(self) -> int:
        gens = {r.generation for r in self.runners.values()}
        if len(gens) != 1:
            raise CheckpointCorrupt(f"runners are at different generations: {sorted(gens)}")
        return gens.pop()

    @property
    def total_evals(self) -> int:
        return sum(r.evaluator.n_evals for r in self.runners.values())

    # --------------------------------------------------------------- advance
    def advance(self, n_gens: int, time_budget_s: float | None = None, log=print, run_note: dict | None = None) -> dict:
        cfg = self.cfg
        n_gens = min(n_gens, cfg.max_total_generations - self.generation)
        run = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6],
               "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "gen_start": self.generation, "requested_gens": n_gens, "status": "running",
               "code_revision": provenance.code_revision(), "environment": provenance.environment_info()}
        run.update(run_note or {})
        t_wall, t_cpu, evals0 = time.perf_counter(), time.process_time(), self.total_evals
        tracemalloc.start()
        done = 0
        try:
            for _ in range(n_gens):
                if time_budget_s is not None and time.perf_counter() - t_wall > time_budget_s:
                    run["stopped_early_reason"] = f"wall-clock budget {time_budget_s:.0f}s reached"
                    break
                for r in self.runners.values():
                    r.step()
                done += 1
                if done % 5 == 0 or done == n_gens:
                    log(f"  generation {self.generation}/{cfg.max_total_generations}  evals={self.total_evals}")
        finally:
            tracemalloc.stop()
        run.update({"gens_done": done, "gen_end": self.generation,
                    "evals_added": self.total_evals - evals0,
                    "wall_s": round(time.perf_counter() - t_wall, 3),
                    "cpu_s": round(time.process_time() - t_cpu, 3),
                    "peak_rss_mb": round(_rss_mb(), 1),
                    "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status": "completed" if done == n_gens else "completed_early"})
        self.runs.append(run)
        self.check_invariants()
        return run

    # ------------------------------------------------------------ invariants
    def check_invariants(self) -> None:
        g = self.generation
        for k, r in self.runners.items():
            exp_evals = self.cfg.pop_size * g
            if r.evaluator.n_evals != exp_evals:
                raise CheckpointCorrupt(f"{k}: evals {r.evaluator.n_evals} != pop*gen {exp_evals} (budget not matched)")
            if len(r.history) != g:
                raise CheckpointCorrupt(f"{k}: history length {len(r.history)} != generation {g}")

    # --------------------------------------------------------------- payload
    def payload(self) -> dict:
        return {
            "meta": {"schema": SCHEMA_VERSION, "generation": self.generation, "total_evals": self.total_evals,
                     "config_hash": self.cfg.identity_hash(), "world_fingerprint": self.world.fingerprint(),
                     "taxonomy_sha256": provenance.taxonomy_hash(), "code_revision": provenance.code_revision(),
                     "n_runs": len(self.runs), "seeds": list(self.seeds)},
            "config": self.cfg.to_dict(),
            "runners": {k: r.get_state() for k, r in self.runners.items()},
            "runs": self.runs, "llm": self.llm, "model_cards": self.model_cards,
        }

    @classmethod
    def from_payload(cls, payload: dict, cfg: ExperimentConfig | None = None) -> "Experiment":
        stored = ExperimentConfig.from_dict(payload["config"])
        if cfg is not None and cfg.identity_hash() != stored.identity_hash():
            raise ConfigMismatch(
                f"configuration differs from the checkpoint's immutable configuration "
                f"({cfg.identity_hash()[:12]} vs {stored.identity_hash()[:12]}); start a new experiment instead")
        # keep runtime-only knobs (gens_per_run) from the caller
        use = cfg.with_overrides() if cfg is not None else stored
        exp = cls(use, seeds=payload["meta"].get("seeds"))  # checkpoints from before v0.2 have no "seeds" -> all
        if exp.world.fingerprint() != payload["meta"]["world_fingerprint"]:
            raise CheckpointCorrupt("benchmark world fingerprint differs from checkpoint (code/dataset drift)")
        if set(payload["runners"]) != set(exp.runners):
            raise CheckpointCorrupt("runner set differs from checkpoint")
        for k, st in payload["runners"].items():
            exp.runners[k].set_state(st)
        exp.runs = list(payload["runs"])
        exp.llm = payload["llm"]
        exp.check_invariants()
        return exp

    # ----------------------------------------------------------------- merge
    @classmethod
    def merge(cls, payloads: list[dict]) -> "Experiment":
        """Combine shard payloads into one full experiment. Refuses anything that is not a clean partition."""
        if not payloads:
            raise CheckpointCorrupt("no shard payloads to merge")
        metas = [p["meta"] for p in payloads]
        for key in ("config_hash", "world_fingerprint", "taxonomy_sha256", "generation"):
            vals = {m.get(key) for m in metas}
            if len(vals) != 1:
                raise CheckpointCorrupt(f"shards disagree on {key}: {sorted(map(str, vals))}")
        revs = {m.get("code_revision") for m in metas}
        if len(revs) != 1:
            raise CheckpointCorrupt(f"shards were produced by different code revisions: {sorted(map(str, revs))}")
        cfg = ExperimentConfig.from_dict(payloads[0]["config"])
        seen: list[int] = []
        for m in metas:
            if "seeds" not in m:
                raise CheckpointCorrupt("a payload without seed information cannot be merged")
            seen.extend(m["seeds"])
        if sorted(seen) != list(range(cfg.n_seeds)):
            raise CheckpointCorrupt(
                f"shards do not partition the seeds 0..{cfg.n_seeds - 1} (got {sorted(seen)}): overlap or missing shard")
        exp = cls(cfg)
        for p in payloads:
            for k, st in p["runners"].items():
                exp.runners[k].set_state(st)
        exp.runs = [dict(r, shard_seeds=list(p["meta"]["seeds"])) for p in payloads for r in p["runs"]]
        exp.llm = payloads[0]["llm"]
        exp.check_invariants()
        return exp

