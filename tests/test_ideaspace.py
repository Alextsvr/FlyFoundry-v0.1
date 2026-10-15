"""Phase 1 layer C: idea space as a Fitness plugin."""
import numpy as np

from flyfoundry.agents.registry import build_arm
from flyfoundry.config import ExperimentConfig
from flyfoundry.evaluation.plugins import ContextEvaluator
from flyfoundry.phase1.ideaspace import CRITERIA, GATE_SCORE, TYPES, IdeaSpace, load_seeds


def test_space_shape_gates_and_scale():
    sp = IdeaSpace()
    idx, F, gated, legal, S = sp.exhaustive()
    assert len(idx) == sp.n_total == int(np.prod(sp.sizes))
    assert F.min() >= 1 and F.max() <= 5 and S.shape == (sp.n_total, 5)
    assert gated.sum() > 0 and np.all(S[gated] == GATE_SCORE) and S[~gated].min() >= 0 and S[~gated].max() <= 1
    assert "own existing network" not in sp.names["channel"]


def test_fitness_plugin_matches_exhaustive_and_decoding_is_total():
    sp = IdeaSpace()
    idx, F, gated, legal, S = sp.exhaustive()
    rng = np.random.default_rng(0)
    pick = rng.integers(0, len(idx), 200)
    X = (idx[pick] + 0.5) / np.array(sp.sizes)          # centre of each cell decodes back to the same tuple
    assert np.array_equal(sp.decode_indices(X), idx[pick])
    ctx = rng.integers(0, 5, 200)
    assert np.allclose(sp.train(X, ctx), S[pick, ctx])
    assert np.array_equal(sp.decode_indices(np.ones((1, 5))), [[s - 1 for s in sp.sizes]])   # x = 1.0 stays in range


def test_unchanged_ga_arm_runs_on_the_idea_space_and_beats_random():
    sp = IdeaSpace()
    cfg = ExperimentConfig(n_dims=5, pop_size=60, survivors=18, elites=3, archive_dims=(0, 1, 2), archive_bins=4)
    arm = build_arm("C_genetic", cfg, 11)
    ev = ContextEvaluator(sp, np.random.default_rng(2))
    first = None
    for g in range(25):
        ev.allowed_evals += cfg.pop_size
        out = arm.step(ev, g)
        first = out.f.mean() if first is None else first
    assert out.f.mean() > first


def test_seeds_are_complete_and_ordered_like_the_weights():
    s = load_seeds()
    assert [x["id"] for x in s] == [f"H{i:02d}" for i in range(1, 13)] + [f"N{i}" for i in range(1, 8)] + ["R1"]
    assert all(len(x["f"]) == len(CRITERIA) and 1 <= min(x["f"]) and max(x["f"]) <= 5 for x in s)


def test_owner_conflict_gate_removes_psp_merchants_and_flags_others():
    sp = IdeaSpace()
    idx, F, gated, legal, S = sp.exhaustive()
    c = sp.names["customer"].index("iGaming / PSP merchants")
    assert gated[idx[:, 0] == c].all() and np.all(S[idx[:, 0] == c] == GATE_SCORE)
    e = sp.names["customer"].index("small EU e-commerce merchants")
    assert (~gated[idx[:, 0] == e]).any() and legal[idx[:, 0] == e].all()
