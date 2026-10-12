import json

import numpy as np
import pytest

from flyfoundry.agents import llm_baseline
from flyfoundry.biology.mushroom_body import MushroomBodyPolicy, build_wiring
from flyfoundry.config import ExperimentConfig
from flyfoundry.environments.benchmark import BenchmarkWorld, BudgetExceeded, Evaluator
from flyfoundry.evaluation.stats import bootstrap_mean_ci
from flyfoundry.storage.serialize import decode, encode, state_hash


def test_config_identity_and_validation():
    a = ExperimentConfig()
    assert a.identity_hash() == ExperimentConfig(gens_per_run=99).identity_hash()  # runtime knob excluded
    assert a.identity_hash() != ExperimentConfig(pop_size=50).identity_hash()
    with pytest.raises(ValueError):
        ExperimentConfig.from_dict({"nope": 1})
    with pytest.raises(Exception):
        a.pop_size = 3  # frozen


def test_serialize_exact_roundtrip():
    rng = np.random.default_rng(5)
    obj = {"a": rng.standard_normal((3, 4)).astype(np.float32), "r": rng.bit_generator.state, "x": [1, 2.5, None],
           "i": np.arange(5)}
    back = decode(json.loads(json.dumps(encode(obj))))
    assert state_hash(back) == state_hash(obj)
    assert back["a"].dtype == np.float32 and np.array_equal(back["a"], obj["a"])
    rng2 = np.random.default_rng(0)
    rng2.bit_generator.state = back["r"]
    assert rng2.random() == rng.random()


def test_world_deterministic_and_budget(tiny_cfg):
    w1, w2 = BenchmarkWorld(tiny_cfg), BenchmarkWorld(tiny_cfg)
    assert w1.fingerprint() == w2.fingerprint()
    ev = Evaluator(w1, np.random.default_rng(1), allowed_evals=10)
    X = np.random.default_rng(2).random((10, 12))
    idx, _ = ev.sample_scenarios(10)
    f = ev.evaluate(X, idx)
    assert f.shape == (10,) and np.all(np.abs(f) <= 1.0)
    with pytest.raises(BudgetExceeded):
        ev.evaluate(X[:1], idx[:1])


def test_decoys_are_traps(tiny_cfg):
    w = BenchmarkWorld(tiny_cfg)
    d = int(np.where(w._decoy)[0][0])
    r = int(np.where(~w._decoy)[0][0])
    xd, xr = w._centers[d].copy(), w._centers[r].copy()
    assert w.static_candidate_heldout(xd) < w.static_candidate_heldout(xr)


def test_heldout_metrics_bounded(tiny_cfg):
    w = BenchmarkWorld(tiny_cfg)
    Xh = np.repeat(w._centers[~w._decoy][:, None, :], len(w.ctx_heldout), axis=1)
    m = w.heldout_metrics(Xh)
    assert 0 <= m["heldout_qd"] <= 1.0 and m["heldout_qd"] > 0.3


def test_mushroom_body_properties(tiny_cfg):
    cfg = tiny_cfg
    C = build_wiring(cfg, 3, False)
    S = build_wiring(cfg, 3, True)
    assert np.array_equal(C.sum(0), S.sum(0))          # KC in-degree preserved
    assert not np.array_equal(C, S)
    pol = MushroomBodyPolicy(cfg, 3)
    rng = np.random.default_rng(0)
    p = pol.init_params(rng, 5)
    ctx = rng.random((5, 4))
    X, kc = pol.forward(p, ctx, np.zeros((5, 12), np.float32))
    assert np.all(kc.sum(1) == cfg.kc_active)           # sparse code
    assert pol.model_card()["uses_real_flywire_connectivity"] is False
    p2 = p.copy()
    pol.plastic_update(p2, p, kc, rng.normal(0, .4, (5, 12)).astype(np.float32), np.ones(5))
    assert not np.array_equal(p, p2)
    p3 = p.copy()
    pol.plastic_update(p3, p, kc, np.zeros((5, 12), np.float32), np.zeros(5))
    assert np.allclose(p, p3)                            # no dopamine error -> no change


def test_llm_adapter_never_simulates(monkeypatch):
    monkeypatch.delenv("FLYFOUNDRY_LLM_ENDPOINT", raising=False)
    ok, reason = llm_baseline.availability()
    assert not ok and reason.startswith("NOT RUN")
    with pytest.raises(RuntimeError):
        llm_baseline.LLMBaselineAdapter().propose(np.zeros(4), 3, 12)
    rows = llm_baseline.parse_candidates("blah [[0.1,0.2,0.3],[0.5,0.5]] x", 3)
    assert rows.shape == (1, 3)
    assert llm_baseline.parse_candidates("no json", 3).shape == (0, 3)


def test_bootstrap_ci():
    m, lo, hi = bootstrap_mean_ci([1, 2, 3, 4, 5], 500, seed=0)
    assert lo <= m <= hi and m == 3
    assert np.isnan(bootstrap_mean_ci([1.0])[1])


def test_agents_cannot_reach_heldout():
    """Static guard: arm code must not touch hidden world internals or held-out data."""
    import pathlib
    for p in pathlib.Path("flyfoundry/agents").glob("*.py"):
        src = p.read_text()
        for bad in ("ctx_heldout", "heldout_metrics", "_centers", "_values", "_shift", "BenchmarkWorld", "ctx_train"):
            assert bad not in src, f"{p.name} references {bad}"
