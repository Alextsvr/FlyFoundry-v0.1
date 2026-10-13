"""v0.2 E4: the drifting world must (a) leave the stationary world untouched, (b) actually drift, (c) stay resumable."""
import importlib.util
import pathlib

import numpy as np

from flyfoundry.config import ExperimentConfig
from flyfoundry.environments.benchmark import DIM_CAPITAL, DIM_EFFORT, BenchmarkWorld
from flyfoundry.research.experiment import Experiment
from flyfoundry.storage.serialize import state_hash

QUIET = lambda *a, **k: None  # noqa: E731
E1_WORLD_FINGERPRINT = "e59b7c93fada16e117f2638d74af94079ddaa10dc4bc28b4893eed64658aebda"  # from the verified E1 run on GitHub Actions


def _drift_cfg(**kw):
    base = dict(n_seeds=2, pop_size=20, survivors=6, elites=2, drift_amp=0.15, drift_period=10.0)
    base.update(kw)
    return ExperimentConfig(**base)


def test_stationary_world_is_unchanged_by_drift_support():
    cfg = ExperimentConfig.from_file(pathlib.Path("configs/swarm_e1.json"))
    w = BenchmarkWorld(cfg)
    assert w.drift_offset(17) is None
    assert w.fingerprint() == E1_WORLD_FINGERPRINT  # same world that produced the E1 results


def test_drift_actually_moves_the_peaks():
    w = BenchmarkWorld(_drift_cfg())
    off0, off3, offT = w.drift_offset(0), w.drift_offset(3), w.drift_offset(10)
    assert np.abs(off0 - off3).max() > 0.01
    assert np.allclose(off0, offT)                                   # periodic with the configured period
    assert np.all(off3[:, DIM_CAPITAL] == 0) and np.all(off3[:, DIM_EFFORT] == 0)
    assert w.fingerprint() != BenchmarkWorld(_drift_cfg(drift_amp=0.0)).fingerprint()


def test_a_fixed_candidate_set_loses_value_as_the_world_drifts():
    """Validity check (a) of E4: drift must matter, otherwise a 'tracking' advantage could not exist."""
    w = BenchmarkWorld(_drift_cfg(drift_period=20.0))
    real = ~w._decoy
    Xh = np.repeat(np.clip(w._centers[real][:, None, :], 0, 1), len(w.ctx_heldout), axis=1)
    at0 = w.heldout_metrics(Xh, 0.0)["heldout_qd"]
    at_half = w.heldout_metrics(Xh, 5.0)["heldout_qd"]
    assert at0 - at_half > 0.02, (at0, at_half)


def test_tracking_metrics_only_in_drifting_worlds():
    stat = Experiment(ExperimentConfig(n_seeds=2, pop_size=20, survivors=6, elites=2)); stat.advance(2, log=QUIET)
    dr = Experiment(_drift_cfg()); dr.advance(2, log=QUIET)
    assert all("track_qd" not in r.history[-1] for r in stat.runners.values())
    for r in dr.runners.values():
        h = r.history[-1]
        assert {"track_qd", "track_best", "track_discovery"} <= set(h) and 0.0 <= h["track_qd"] <= 1.5


def test_drifting_world_is_deterministic_and_resumable():
    cfg = _drift_cfg()
    a = Experiment(cfg); a.advance(3, log=QUIET)
    b = Experiment(cfg); b.advance(3, log=QUIET)
    c = Experiment.from_payload(a.payload(), cfg); c.advance(3, log=QUIET)
    d = Experiment(cfg); d.advance(6, log=QUIET)
    for k in a.runners:
        assert state_hash(a.runners[k].get_state()["arm"]) == state_hash(b.runners[k].get_state()["arm"])
        assert state_hash(c.runners[k].get_state()["arm"]) == state_hash(d.runners[k].get_state()["arm"]), k
        assert c.runners[k].history[-1]["track_qd"] == d.runners[k].history[-1]["track_qd"]


def test_analysis_script_verdict_rules(tmp_path):
    spec = importlib.util.spec_from_file_location("analyze_e4", "scripts/analyze_e4.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.verdict(0.01, 0.05) == "SUPPORTED" and mod.verdict(-0.05, -0.01) == "REFUTED"
    assert mod.verdict(-0.01, 0.05) == "INCONCLUSIVE" and mod.verdict(0.0, 0.05) == "INCONCLUSIVE"
    rng = np.random.default_rng(0)
    rows = ["arm,seed,gen,track_qd"]
    for seed in range(20):
        base = rng.normal(0, 0.01)
        for gen in range(1, 61):
            for arm, shift in (("A_fly_plastic", 0.0), ("A_fly_noplast", 0.0), ("A_fly_shuffled", 0.0),
                               ("B_evolved_ann", 0.10), ("C_genetic", 0.05), ("D_random", 0.0)):
                rows.append(f"{arm},{seed},{gen},{0.3 + shift + base + rng.normal(0, 0.005)}")
    p = tmp_path / "h.csv"; p.write_text("\n".join(rows))
    res = mod.analyse(str(p))
    by = {c["id"]: c for c in res["contrasts"]}
    assert by["E4-H1"]["verdict"] == "REFUTED"        # fly is 0.10 worse than the ANN by construction
    assert by["E4-H2"]["verdict"] == "INCONCLUSIVE"   # no true difference
    assert by["E4-H4"]["verdict"] == "SUPPORTED"
    assert "E4-H2" in mod.markdown(res, "medium")
