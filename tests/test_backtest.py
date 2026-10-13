"""v0.2 E3 plumbing: data transcription, Spearman helper, plugin interface drives an unchanged arm."""
import numpy as np

from flyfoundry.agents.registry import build_arm
from flyfoundry.config import ExperimentConfig
from flyfoundry.evaluation.plugins import ContextEvaluator, TabularBacktest, rank_rows, spearman_rows


def test_table_reproduces_published_scores_and_ranks():
    f = TabularBacktest()
    pub = {"base": {"H07": 3.87, "H01": 3.51, "H05": 3.18, "H12": 3.11, "H06": 2.98, "H03": 1.82},
           "risk_averse": {"H07": 3.83, "H01": 3.77, "H10": 2.15, "H03": 1.83},
           "automation_first": {"H07": 3.91, "H03": 1.59}}
    for s, d in pub.items():
        for h, v in d.items():
            assert round(float(f.ref_scores[s][f.names.index(h)]), 2) == v, (s, h)
    for s in f.W:
        order = np.argsort(f.ref_ranks[s])
        assert [f.names[i] for i in order[:2]] == ["H07", "H01"] and f.names[order[-1]] == "H03"


def test_spearman_helper():
    r = np.array([1., 2, 3, 4, 5])
    assert np.allclose(spearman_rows(np.array([[5., 4, 3, 2, 1], [1., 2, 3, 4, 5], [1., 1, 1, 1, 1]]), r), [-1, 1, 0])
    assert np.allclose(rank_rows(np.array([[3., 1, 3, 2]]))[0], [3.5, 1, 3.5, 2])


def test_plugin_drives_unchanged_ga_arm_and_learns():
    f = TabularBacktest()
    cfg = ExperimentConfig(n_dims=f.n_dims, pop_size=40, survivors=12, elites=3, archive_dims=(0, 1, 3))
    arm = build_arm("C_genetic", cfg, 5)
    ev = ContextEvaluator(f, np.random.default_rng(1))
    first = None
    for g in range(15):
        ev.allowed_evals += cfg.pop_size
        out = arm.step(ev, g)
        first = out.f.mean() if first is None else first
    assert out.f.mean() > first
