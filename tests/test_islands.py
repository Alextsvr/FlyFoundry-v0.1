"""v0.2 E2: island model. Isolation of the `final` contexts, budget equality, determinism, migration mechanics."""
import importlib.util
import pathlib

import numpy as np

from flyfoundry.config import ExperimentConfig
from flyfoundry.environments.benchmark import BenchmarkWorld
from flyfoundry.research import islands as isl
from flyfoundry.research.tournament import final_tournament

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _cfg():
    return ExperimentConfig(n_seeds=2, pop_size=20, survivors=6, elites=2)


def test_islands_code_cannot_reach_final_contexts():
    src = (ROOT / "flyfoundry/research/islands.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("#", '"""')) and "ISOLATION" not in l)
    for bad in ("final_judge", "FinalJudge", "ctx_final", "_split_contexts", "_split", "ctx_heldout", "tournament"):
        assert bad not in code.replace("research/tournament.py", ""), f"islands.py references {bad}"
    for p in (ROOT / "flyfoundry/agents").glob("*.py"):
        assert "final_judge" not in p.read_text() and "select_view" not in p.read_text()


def test_split_contexts_are_disjoint_and_do_not_change_the_world():
    w = BenchmarkWorld(ExperimentConfig.from_file(ROOT / "configs/swarm_e1.json"))
    fp = w.fingerprint()
    sel, fin = w.select_view().ctx, w.final_judge().ctx
    assert sel.shape == fin.shape == (16, 4)
    assert not np.allclose(sel, fin) and not np.allclose(sel, w.ctx_heldout) and not np.allclose(fin, w.ctx_train)
    assert w.fingerprint() == fp == "e59b7c93fada16e117f2638d74af94079ddaa10dc4bc28b4893eed64658aebda"


def test_equal_evaluation_budget_and_determinism():
    cfg = _cfg()
    w = BenchmarkWorld(cfg)
    for arm in ("C_genetic", "B_evolved_ann"):
        a = isl.run_islands(arm, cfg, w, 0, 12, migrate=True)
        b = isl.run_pool(arm, cfg, w, 0, 12)
        assert sum(p.n_evals for p in a) == sum(p.n_evals for p in b) == 12 * cfg.pop_size * isl.N_ISLANDS
        r1 = final_tournament(a, w)
        r2 = final_tournament(isl.run_islands(arm, cfg, w, 0, 12, migrate=True), w)
        assert r1 == r2


def test_migration_moves_elites_but_keeps_population_size():
    cfg = _cfg()
    w = BenchmarkWorld(cfg)
    for arm in ("C_genetic", "B_evolved_ann"):
        pops = [isl.Population(arm, cfg, w, 100 + i) for i in range(3)]
        for _ in range(3):
            for p in pops:
                p.step()
        n0 = [len(p.arm.ids) for p in pops]
        ids0 = [set(p.arm.ids.tolist()) for p in pops]
        isl.migrate_ring(pops, w.select_view(), k=2)
        assert [len(p.arm.ids) for p in pops] == n0
        assert all(len(set(p.arm.ids.tolist()) - i0) == 2 for p, i0 in zip(pops, ids0))
        for p in pops:
            p.step()  # still runs after receiving migrants


def test_pool_config_scales_counts():
    c = isl.pool_config(_cfg())
    assert (c.pop_size, c.survivors, c.elites) == (200, 60, 20)


def test_analysis_script_runs_on_synthetic_shards(tmp_path):
    import json
    spec = importlib.util.spec_from_file_location("analyze_e2", ROOT / "scripts/analyze_e2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rng = np.random.default_rng(0)
    rows = []
    for rep in range(12):
        for arm in ("B_evolved_ann", "C_genetic"):
            for c, mu in zip(m.CONDS, (0.5, 0.5, 0.4)):
                rows.append({"rep": rep, "arm": arm, "condition": c, "final_qd": mu + rng.normal(0, .01), "final_best": .5,
                             "gap": rng.normal(0, .01), "n_evals": 100})
    meta = {"config_hash": "x", "world_fingerprint": "y", "generations": 60, "repeats": 12, "n_islands": 10,
            "migrate_every": 10, "n_migrants": 3, "pool_factor": 10}
    for i in range(3):
        (tmp_path / f"e2_shard_{i}.json").write_text(json.dumps({**meta, "shard": [i, 3], "rows": rows[i::3]}))
    got, _ = m.load(str(tmp_path / "**/e2_shard_*.json").replace("**/", ""), 12)
    res = m.analyse(got)
    h1 = [c for c in res["contrasts"] if c["id"] == "E2-H1"]
    assert len(h1) == 2 and all(c["verdict"] == "SUPPORTED" for c in h1)
    assert "E2-H4" in m.markdown(res, meta)
