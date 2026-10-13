"""Phase 1 layer F: probes (offline, fake transport), scoring, calibration harness, leakage guard."""
import json
import pathlib
from datetime import datetime, timezone

import numpy as np

from flyfoundry.phase1 import calibration, probes, scoring

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = lambda: datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)  # noqa: E731


def fake_transport(strength):
    """strength: idea id -> latent 'demand'. Returns plausible API payloads; counts rise with demand."""
    calls = []

    def t(url, headers):
        calls.append(url)
        assert "flyfoundry-research" in headers["User-Agent"]
        key = next((i for i in strength if f"X{int(i[1:])}X" in url), None)
        s = strength[key] if key else 1
        if "hn.algolia.com" in url:
            return 200, json.dumps({"nbHits": int(10 * s)})
        if "api.github.com" in url:
            return 200, json.dumps({"total_count": int(5 * s), "items": [{"stargazers_count": 10 * s}] * 5})
        if "api.stackexchange.com" in url:
            return 200, json.dumps({"total": int(20 * s)})
        return 404, "nope"
    t.calls = calls
    return t


def _ideas(n=12):
    return [{"id": f"H{i:02d}", "name": f"X{i}X", "calibration": "1", "hn_phrases": [f"phraseX{i}X"], "gh_query": f"qX{i}X",
             "se_query": f"sX{i}X", "se_site": "stackoverflow", "basis": ""} for i in range(1, n + 1)]


def test_ideas_file_has_frozen_queries_for_all_twelve():
    ideas = probes.load_ideas(ROOT / "data/ideas.csv")
    assert [i["id"] for i in ideas] == [f"H{k:02d}" for k in range(1, 13)]
    assert all(i["hn_phrases"] and i["gh_query"] and i["se_query"] for i in ideas)


def test_probes_cache_resume_and_blocked_not_worked_around(tmp_path):
    ideas = _ideas(3)
    tr = fake_transport({f"H{i:02d}": i for i in range(1, 4)})
    cache = probes.ProbeCache(tmp_path / "c.jsonl")
    probes.run_probes(ideas, cache, transport=tr, now=NOW, sleep_scale=0.0)
    n = len(tr.calls)
    assert n == 3 * 3 and all(f["status"] == "ok" for f in cache.facts.values())
    cache2 = probes.ProbeCache(tmp_path / "c.jsonl")           # resume: nothing is fetched again
    probes.run_probes(ideas, cache2, transport=tr, now=NOW, sleep_scale=0.0)
    assert len(tr.calls) == n
    blocked = probes.ProbeCache(None)
    probes.run_probes(ideas[:1], blocked, transport=lambda u, h: (403, "forbidden"), now=NOW, sleep_scale=0.0)
    assert {f["status"] for f in blocked.facts.values()} == {"blocked"}


def test_score_direction_and_calibration_harness(tmp_path):
    ids = [f"H{i:02d}" for i in range(1, 13)]
    ideas = _ideas()
    strength = {i: float(k + 1) for k, i in enumerate(ids)}          # demand grows with index; free alternatives too
    cache = probes.ProbeCache(None)
    probes.run_probes(ideas, cache, transport=fake_transport(strength), now=NOW, sleep_scale=0.0)
    sc = scoring.f_scores(list(cache.facts.values()))
    assert set(sc) == set(ids)
    y = {i: float(k) for k, i in enumerate(ids)}                      # reference that follows the same latent
    res = calibration.calibrate(sc, y, n_perm=500)
    assert res["n"] == 12 and np.isfinite(res["rho"])
    # a reference unrelated to the probes must not pass; a shuffled-probe control must not pass either
    rng = np.random.default_rng(3)
    y_rand = {i: float(v) for i, v in zip(ids, rng.permutation(12))}
    assert calibration.calibrate(sc, y_rand, n_perm=500)["verdict"] == "FAIL"
    assert calibration.stability(sc, sc)["verdict"] == "PASS"


def test_calibration_detects_a_planted_signal():
    ids = [f"H{i:02d}" for i in range(12)]
    rng = np.random.default_rng(0)
    y = {i: float(k) for k, i in enumerate(ids)}
    good = {i: y[i] + rng.normal(0, 0.5) for i in ids}
    bad = {i: float(v) for i, v in zip(ids, rng.permutation(12))}
    assert calibration.calibrate(good, y, n_perm=1000)["verdict"] == "PASS"
    assert calibration.calibrate(bad, y, n_perm=1000)["verdict"] == "FAIL"


def test_scoring_code_cannot_see_the_reference():
    src = (ROOT / "flyfoundry/phase1/scoring.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("calibration", "load_reference", "calibration_reference"):
        assert bad not in code.replace("NO reference verdicts (see calibration.py)", ""), bad
    assert "calibration" not in (ROOT / "flyfoundry/phase1/probes.py").read_text().lower().replace("calibration\"", "")
