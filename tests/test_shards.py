"""v0.2 sharding: a sharded experiment, once merged, must equal the unsharded one (state-for-state)."""
import json

import pytest

from flyfoundry.cli.main import main
from flyfoundry.config import ExperimentConfig
from flyfoundry.research.experiment import Experiment, shard_seeds
from flyfoundry.storage.checkpoint import CheckpointCorrupt, CheckpointStore
from flyfoundry.storage.serialize import state_hash

QUIET = lambda *a, **k: None  # noqa: E731
NONDETERMINISTIC = ("cpu_", "mem_")  # wall/CPU/memory measurements differ between runs by nature


@pytest.fixture(scope="module")
def cfg5():
    return ExperimentConfig(n_seeds=5, pop_size=20, survivors=6, elites=2, gens_per_run=3)


def _science(exp):
    """Everything that must be reproducible: arm state, evaluator state, history without resource measurements."""
    out = {}
    for k, r in exp.runners.items():
        st = r.get_state()
        hist = [{a: b for a, b in h.items() if not a.startswith(NONDETERMINISTIC)} for h in st["history"]]
        out[k] = state_hash({"arm": st["arm"], "evaluator": st["evaluator"], "history": hist})
    return out


def _shards(cfg, n, gens):
    exps = []
    for i in range(n):
        e = Experiment(cfg, shard_seeds(cfg.n_seeds, i, n))
        e.advance(gens, log=QUIET)
        exps.append(e)
    return exps


@pytest.mark.parametrize("n_seeds,n_shards", [(1, 1), (5, 1), (5, 2), (5, 5), (10, 3), (100, 10), (7, 4)])
def test_shard_seeds_is_a_clean_partition(n_seeds, n_shards):
    blocks = [shard_seeds(n_seeds, i, n_shards) for i in range(n_shards)]
    flat = [s for b in blocks for s in b]
    assert flat == list(range(n_seeds))  # contiguous, ordered, no overlap, nothing missing
    assert max(map(len, blocks)) - min(map(len, blocks)) <= 1


@pytest.mark.parametrize("bad", [(0, 0), (2, 2), (-1, 3), (0, 6)])
def test_shard_seeds_rejects_invalid(bad):
    with pytest.raises(ValueError):
        shard_seeds(5, *bad)


def test_merged_shards_equal_unsharded(cfg5):
    full = Experiment(cfg5); full.advance(3, log=QUIET)
    for n in (2, 5):  # N must not matter
        merged = Experiment.merge([e.payload() for e in _shards(cfg5, n, 3)])
        assert merged.is_full and merged.generation == 3
        assert _science(merged) == _science(full), f"{n} shards differ from the unsharded run"
        assert merged.total_evals == full.total_evals


def test_shard_resume_equals_uninterrupted(cfg5):
    e = Experiment(cfg5, shard_seeds(5, 1, 2)); e.advance(2, log=QUIET)
    again = Experiment.from_payload(e.payload(), cfg5); again.advance(2, log=QUIET)
    straight = Experiment(cfg5, shard_seeds(5, 1, 2)); straight.advance(4, log=QUIET)
    assert again.seeds == straight.seeds == [3, 4]
    assert _science(again) == _science(straight)


def test_merge_refuses_non_partitions(cfg5):
    a, b = _shards(cfg5, 2, 2)
    with pytest.raises(CheckpointCorrupt, match="partition"):
        Experiment.merge([a.payload()])  # a shard is missing
    with pytest.raises(CheckpointCorrupt, match="partition"):
        Experiment.merge([a.payload(), a.payload(), b.payload()])  # overlap
    b.advance(1, log=QUIET)
    with pytest.raises(CheckpointCorrupt, match="generation"):
        Experiment.merge([a.payload(), b.payload()])  # shards at different generations
    other = ExperimentConfig(n_seeds=5, pop_size=24, survivors=6, elites=2)
    c = Experiment(other, shard_seeds(5, 1, 2)); c.advance(2, log=QUIET)
    with pytest.raises(CheckpointCorrupt, match="config_hash"):
        Experiment.merge([a.payload(), c.payload()])  # different configuration


def test_islands_cannot_see_other_shards(cfg5):
    """A shard only builds runners for its own seeds, so it cannot read or depend on another shard's data."""
    e = Experiment(cfg5, shard_seeds(5, 0, 2))
    assert {int(k.split("|")[1]) for k in e.runners} == {0, 1, 2}


def test_cli_shards_then_merge(tmp_path, cfg5):
    cfgp = tmp_path / "c.json"; cfgp.write_text(json.dumps(cfg5.to_dict()))
    out = str(tmp_path / "out")
    for i in range(2):
        st = str(tmp_path / f"s{i}")
        assert main(["run", "--config", str(cfgp), "--state-dir", st, "--out", out, "--allow-fresh",
                     "--generations", "2", "--shard", f"{i}/2"]) == 0
        assert main(["resume", "--config", str(cfgp), "--state-dir", st, "--out", out, "--generations", "1",
                     "--shard", f"{i}/2"]) == 0
    # a shard directory must refuse to be resumed as a different shard, or as the whole experiment
    assert main(["resume", "--config", str(cfgp), "--state-dir", str(tmp_path / "s0"), "--out", out, "--shard", "1/2"]) == 3
    assert main(["resume", "--config", str(cfgp), "--state-dir", str(tmp_path / "s0"), "--out", out]) == 3
    # merge
    merged = str(tmp_path / "merged")
    assert main(["merge", "--config", str(cfgp), "--shard-dir", str(tmp_path / "s0"), "--shard-dir", str(tmp_path / "s1"),
                 "--state-dir", merged, "--out", out]) == 0
    assert main(["merge", "--config", str(cfgp), "--shard-dir", str(tmp_path / "s0"), "--shard-dir", str(tmp_path / "s1"),
                 "--state-dir", merged, "--out", out]) == 2  # target exists, no silent replace
    assert main(["validate", "--state-dir", merged]) == 0
    res = json.loads((tmp_path / "out" / "results.json").read_text())
    assert res["generation"] == 3 and (tmp_path / "out" / "index.html").stat().st_size > 10_000
    # the merged state is an ordinary full checkpoint: it resumes like one and equals an unsharded run
    full = Experiment(cfg5); full.advance(3, log=QUIET)
    loaded = Experiment.from_payload(CheckpointStore(merged).load_latest().payload, cfg5)
    assert _science(loaded) == _science(full)
    assert main(["resume", "--config", str(cfgp), "--state-dir", merged, "--out", out, "--generations", "1"]) == 0
