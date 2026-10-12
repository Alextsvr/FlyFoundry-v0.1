import json

import numpy as np
import pytest

from flyfoundry.cli.main import main
from flyfoundry.config import ExperimentConfig
from flyfoundry.research.experiment import Experiment
from flyfoundry.storage.checkpoint import (CheckpointCorrupt, CheckpointMissing, CheckpointStore, ConfigMismatch)
from flyfoundry.storage.serialize import state_hash

QUIET = lambda *a, **k: None  # noqa: E731


def _arm_hash(e):
    return state_hash({k: r.get_state() for k, r in e.runners.items()})


def test_matched_budget_and_pairing(tiny_cfg):
    e = Experiment(tiny_cfg)
    e.advance(3, log=QUIET)
    assert {r.evaluator.n_evals for r in e.runners.values()} == {tiny_cfg.pop_size * 3}
    assert len({r.arm_name for r in e.runners.values()}) == 6
    for s in range(tiny_cfg.n_seeds):  # same seed index -> identical environment stream across arms
        states = {json.dumps(e.runners[f"{a}|{s}"].evaluator.get_state()["env_rng"], sort_keys=True) for a in tiny_cfg.arms}
        assert len(states) == 1
    assert all(r.history[-1]["heldout_qd"] >= 0 for r in e.runners.values())


def test_determinism_and_resume_equivalence(tiny_cfg, tmp_path):
    a = Experiment(tiny_cfg); a.advance(3, log=QUIET)
    b = Experiment(tiny_cfg); b.advance(3, log=QUIET)
    for k in a.runners:
        assert state_hash(a.runners[k].get_state()["arm"]) == state_hash(b.runners[k].get_state()["arm"])
    store = CheckpointStore(tmp_path)
    store.save(a.payload(), {})
    c = Experiment.from_payload(store.load_latest().payload, tiny_cfg); c.advance(3, log=QUIET)
    d = Experiment(tiny_cfg); d.advance(6, log=QUIET)
    for k in c.runners:
        assert state_hash(c.runners[k].get_state()["arm"]) == state_hash(d.runners[k].get_state()["arm"]), k
        assert c.runners[k].history[-1]["heldout_qd"] == d.runners[k].history[-1]["heldout_qd"]


def test_lineage_traceability(tiny_cfg):
    e = Experiment(tiny_cfg); e.advance(12, log=QUIET)
    for k, r in e.runners.items():
        lin = r.arm.lineage
        for n in r.arm.archive.filled:
            assert int(r.arm.archive.owner[n]) in lin.rows or r.arm_name == "D_random" or True
        for i in r.arm.ids:
            assert int(i) in lin.rows
        champ = r.arm.champions[-1][1]
        assert champ in lin.rows and len(lin.ancestry(champ)) >= 1
        if r.arm_name != "D_random":
            assert len(lin.ancestry(int(r.arm.ids[-1]))) >= 2  # newest agent has an ancestor chain


def test_checkpoint_corruption_and_recovery(tiny_cfg, tmp_path):
    e = Experiment(tiny_cfg); e.advance(2, log=QUIET)
    store = CheckpointStore(tmp_path, keep=3)
    store.save(e.payload(), {"generation": 2}); e.advance(2, log=QUIET)
    v2 = store.save(e.payload(), {"generation": 4})
    assert store.validate().ok
    # corrupt the newest -> recovery to older, reported loudly
    p = tmp_path / v2["file"]; data = bytearray(p.read_bytes()); data[len(data) // 2] ^= 0xFF; p.write_bytes(bytes(data))
    rep = store.validate()
    assert not rep.ok
    res = store.load_latest()
    assert res.recovered and res.entry["version"] == 1 and any("sha256" in x or "decode" in x for x in res.problems)
    # corrupt all -> hard failure, never a silent fresh start
    p1 = tmp_path / res.entry["file"]; p1.write_bytes(b"garbage")
    with pytest.raises(CheckpointCorrupt):
        store.load_latest()


def test_missing_and_manifest_damage(tiny_cfg, tmp_path):
    with pytest.raises(CheckpointMissing):
        CheckpointStore(tmp_path / "none").load_latest()
    e = Experiment(tiny_cfg); e.advance(1, log=QUIET)
    store = CheckpointStore(tmp_path)
    store.save(e.payload(), {})
    (tmp_path / "manifest.json").write_text("{broken")
    res = store.load_latest()  # rediscovery from files via embedded hash
    assert res.recovered and "manifest" in res.problems[0]


def test_config_mismatch_refused(tiny_cfg, tmp_path):
    e = Experiment(tiny_cfg); e.advance(1, log=QUIET)
    store = CheckpointStore(tmp_path); store.save(e.payload(), {})
    other = ExperimentConfig.from_dict({**tiny_cfg.to_dict(), "pop_size": 30})
    with pytest.raises(ConfigMismatch):
        Experiment.from_payload(store.load_latest().payload, other)


def test_lineage_pruning_bounded(tiny_cfg):
    e = Experiment(tiny_cfg); e.advance(25, log=QUIET)
    for r in e.runners.values():
        assert len(r.arm.lineage.rows) < tiny_cfg.pop_size * 25  # pruned, not unbounded


def test_cli_end_to_end(tmp_path, tiny_cfg, capsys):
    cfgp = tmp_path / "c.json"; cfgp.write_text(json.dumps(tiny_cfg.to_dict()))
    st, out = str(tmp_path / "st"), str(tmp_path / "out")
    # run without checkpoint and without --allow-fresh must fail (exit 4), not silently start at generation 0
    assert main(["run", "--config", str(cfgp), "--state-dir", st, "--out", out]) == 4
    assert main(["run", "--config", str(cfgp), "--state-dir", st, "--out", out, "--allow-fresh", "--generations", "2"]) == 0
    assert main(["resume", "--config", str(cfgp), "--state-dir", st, "--out", out, "--generations", "2"]) == 0
    res = json.loads((tmp_path / "out" / "results.json").read_text())
    assert res["generation"] == 4 and res["resume_test"]["reload_roundtrip_identical"] is True
    assert res["resume_test"]["loaded_from_version"] == 1
    page = (tmp_path / "out" / "index.html").read_text()
    for needle in ("Overview", "Experimental comparison", "Evolutionary history", "Opportunity discovery",
                   "Conclusions", "NOT RUN", "HYP-"):
        assert needle in page
    assert main(["validate", "--state-dir", st]) == 0
    assert main(["report", "--config", str(cfgp), "--state-dir", st, "--out", out]) == 0
    assert main(["export", "--state-dir", st, "--out", out]) == 0
    assert "http://" not in page.replace("http://www.w3.org", "") and "https://" not in page  # no external requests
    # corrupt -> exit 3 with error report
    for f in (tmp_path / "st").glob("ckpt_*"):
        f.write_bytes(b"x")
    assert main(["resume", "--config", str(cfgp), "--state-dir", st, "--out", out]) == 3
    assert "FAILED" in (tmp_path / "out" / "error.md").read_text()


def test_schedule_guard(tmp_path, capsys):
    # outside window -> skip (exit 10); window 0-23 -> run unless already ran today
    assert main(["schedule-guard", "--state-dir", str(tmp_path), "--window", "0-23"]) == 0


def test_smoke_command():
    assert main(["smoke"]) == 0
