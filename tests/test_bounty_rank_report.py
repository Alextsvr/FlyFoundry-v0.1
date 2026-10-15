"""Scoring, effort estimator, reports, atomic publishing, run status and state integrity (audit findings 3.x and 4.1/4.3)."""
import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from _bounty_common import *   # noqa: F401,F403
from flyfoundry.bounty_factory import cli as C, pipeline as P
from flyfoundry.bounty_factory.brief import build_brief
from flyfoundry.bounty_factory.feasibility import estimate
from flyfoundry.bounty_factory.gate import evaluate as gate
from flyfoundry.bounty_factory.scoring import criteria, score_b, baseline_a, sensitivity, effort_scenarios, kendall_tau, A_DEFINITION, review_priority
from flyfoundry.bounty_factory.store import Store


def rich(**over):
    o = listed(prize_amount=5000.0, prize_currency="USD", prize_count=2, registrations_count=100, themes=["Machine Learning/AI"])
    o.title = "Python data dashboard challenge"
    for k, v in over.items():
        o.set(k, v, "source_claim", "t", origin="rules")
    return o


# ---------- 3.1 / 3.2 estimator and criteria
def test_unread_requirements_give_wide_low_confidence_range():
    e = estimate(rich(), CFG)
    assert e["requirements_read"] == "none" and e["confidence"] == "very_low"
    assert e["hours_high"] / e["hours_low"] >= 5
    assert e["template_is_hypothesis"] is True


def test_template_match_does_not_narrow_before_rules_are_read():
    a = estimate(rich(), CFG)
    b = estimate(rich(themes=["data dashboard analytics visualization"]), CFG)
    assert (a["hours_low"], a["hours_high"]) == (b["hours_low"], b["hours_high"]) or b["hours_high"] / b["hours_low"] >= 5


def test_rules_read_narrows_range():
    o = rich()
    o.set("rules_hash", RULES_HASH, "source_claim", "r", origin="rules")
    o.set("deliverables", ["github_repo"], "inferred", "kw", strength="weak", origin="rules")
    o.detail["rules"] = {"ok": True, "http_status": 200, "fetched_at": "2026-10-15T00:00:00Z"}
    e0, e1 = estimate(rich(), CFG), estimate(o, CFG)
    assert e1["requirements_read"] == "rules" and (e1["hours_high"] - e1["hours_low"]) < (e0["hours_high"] - e0["hours_low"])


def test_platform_mentions_add_hours_once_each():
    base = estimate(rich(), CFG)
    o = rich()
    o.title += " on AWS"
    e = estimate(o, CFG)
    assert e["platform_mentions"] and e["hours_low"] > base["hours_low"]
    assert sum("AWS" in r or "aws" in r.lower() for r in e["risks"]) == 1


def test_criteria_fill_is_not_evidence_completeness():
    o = rich()
    e = estimate(o, CFG)
    sb = score_b(criteria(o, e, CFG, NOW), CFG["weights"])
    assert "criteria_fill" in sb and "coverage" not in sb
    assert "free_resources" in sb["unknown"]                       # free-resources can never be inferred from a template match
    g = gate(o, CFG, NOW, {})
    assert g["decision"] == "NEEDS_REVIEW" and g["conditions_confirmed"] < g["conditions_total"]


def test_free_resources_weight_is_zero():
    assert CFG["weights"]["free_resources"] == 0


def test_baseline_a_is_declared_pool_over_mid_hours():
    o = rich()
    e = estimate(o, CFG)
    assert baseline_a(o, e, CFG) == pytest.approx(5000 / e["hours_mid"])
    assert "declared" in A_DEFINITION.lower() and "not" in A_DEFINITION.lower()
    assert baseline_a(opp(), e, CFG) is None


def test_sensitivity_states_its_scope_and_effort_scenarios_exist():
    items = {f"i{n}": (rich(prize_amount=1000.0 * (n + 1)), None) for n in range(5)}
    crits = {}
    for i, (o, _) in items.items():
        crits[i] = criteria(o, estimate(o, CFG), CFG, NOW)
    s = sensitivity(crits, CFG["weights"])
    assert "weights" in json.dumps(s).lower()
    sc = effort_scenarios({i: (o, estimate(o, CFG)) for i, (o, _) in items.items()}, CFG, NOW)
    assert "top_set_stable" in sc


def test_review_priority_is_separate_from_development_priority():
    o = rich()
    e = estimate(o, CFG)
    g = gate(o, CFG, NOW, {})
    rp = review_priority(o, e, g, CFG, NOW)
    assert rp["value"] is not None
    assert review_priority(listed(deadline_date="2026-01-01"), e, gate(listed(deadline_date="2026-01-01"), CFG, NOW, {}), CFG, NOW)["value"] is None


def test_kendall_tau_basic():
    assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == -1.0


# ---------- brief honesty
def test_brief_is_provisional_for_unverified_and_names_unknowns(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    s.upsert(rich(), T0 := "2026-10-15T12:00:00Z")
    ev = P.evaluate(s, CFG, {}, NOW)
    r = ev["rows"][0]
    txt = build_brief(r, T0, provisional=True)
    assert "PROVISIONAL" in txt and "UNVERIFIED" in txt.upper()
    assert "template" in txt.lower()


# ---------- CLI integration: atomic outputs, manifests, status, exit codes, state
def fake_fetcher(monkeypatch, pages, **tk):
    t = make_transport(pages, **tk)
    monkeypatch.setattr(C, "Fetcher", lambda **kw: fetcher(t))
    return t


def bounty(tmp_path, *extra, now="2026-10-15T12:00:00Z", action="run"):
    args = [action, "--state-dir", str(tmp_path / "state"), "--out", str(tmp_path / "out"), "--reviews", str(tmp_path / "reviews.json"),
            "--manual", str(tmp_path / "manual.json"), "--now", now, *extra]
    return C.main_bounty(args)


def pages8(prefix="Hack"):
    return [page([item(i, f"{prefix} {i}") for i in range(1, 9)])]


def test_first_run_without_state_publishes_verified_set(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    assert bounty(tmp_path, "--no-detail") == 0
    out = tmp_path / "out"
    assert C.verify_manifest(out) == []
    m = json.loads((out / "manifest.json").read_text())
    assert m["run_status"]["run_status"] == "success" and m["code_version"]["package"] and m["run_id"] and len(m["files"]) >= 5
    assert (tmp_path / "state" / "latest" / "manifest.json").exists()
    assert C.main_bounty(["verify-state", "--state-dir", str(tmp_path / "state")]) == 0
    j = json.loads((out / "opportunities.json").read_text())
    assert "valid_opportunities_found" not in json.dumps(j) and "eligible_confirmed" in (out / "metrics.json").read_text()


def test_second_run_with_restored_state_updates_and_keeps_history(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    p2 = [page([item(i, f"Hack {i}", prize="$9,000" if i == 1 else "$5,000") for i in range(1, 9)])]
    fake_fetcher(monkeypatch, p2)
    assert bounty(tmp_path, "--no-detail", now="2026-10-16T12:00:00Z") == 0
    s = Store(tmp_path / "state" / "bounty.sqlite3")
    o = [x for x in s.all() if x.title == "Hack 1"][0]
    assert o.fact("prize_amount").value == 9000.0 and o.fact("prize_amount").history[-1]["value"] == 5000.0
    assert s.integrity() == []
    s.close()


def test_source_failure_with_prior_data_exit_4_keeps_last_good_outputs(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    before = json.loads((tmp_path / "out" / "manifest.json").read_text())
    fake_fetcher(monkeypatch, [], list_status=503)
    rc = bounty(tmp_path, "--no-detail", now="2026-10-16T12:00:00Z")
    assert rc == 4
    after = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert after["run_status"]["run_status"] == "source_unavailable"          # report clearly says it is built from older data
    assert "OLDER" in after["run_status"]["message"]
    html = (tmp_path / "out" / "report.html").read_text()
    assert "SOURCE_UNAVAILABLE" in html and "STALE" in html
    assert C.verify_manifest(tmp_path / "out") == []
    s = Store(tmp_path / "state" / "bounty.sqlite3")
    assert sum(o.status == "listed" for o in s.all()) == 8
    s.close()


def test_no_data_exit_5(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, [], list_status=503)
    assert bounty(tmp_path, "--no-detail") == 5


def test_schema_error_exit_4_not_empty_listing(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    fake_fetcher(monkeypatch, [], list_body="{}")
    assert bounty(tmp_path, "--no-detail", now="2026-10-16T12:00:00Z") == 4
    s = Store(tmp_path / "state" / "bounty.sqlite3")
    assert sum(o.status == "listed" for o in s.all()) == 8
    s.close()


def test_partial_exit_3(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, [page([item(1, "A")], total=50, per_page=1), page([], total=50, per_page=1, current=2)])
    assert bounty(tmp_path, "--no-detail") == 3


def test_stale_briefs_disappear(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    assert bounty(tmp_path, "--no-detail", "--provisional-briefs", "3") == 0
    b1 = sorted(p.name for p in (tmp_path / "out" / "briefs").glob("*.md"))
    assert len(b1) == 3
    # the top-3 set changes (bigger prizes on other records) -> briefs of the former top 3 must not linger
    p2 = [page([item(i, f"Hack {i}", prize="$<span data-currency-value>9,000</span>" if i >= 6 else "$100") for i in range(1, 9)])]
    fake_fetcher(monkeypatch, p2)
    assert bounty(tmp_path, "--no-detail", "--provisional-briefs", "3", now="2026-10-16T12:00:00Z") == 0
    b2 = sorted(p.name for p in (tmp_path / "out" / "briefs").glob("*.md"))
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert len(b2) == 3 and set(b2) != set(b1)
    assert {f"{i}.md" for i in m["briefs"]} == set(b2)
    assert not (tmp_path / "out.new").exists() and not (tmp_path / "out.old").exists()
    assert len(list((tmp_path / "out" / "prompts").glob("*.md"))) == 3


def test_failed_generation_keeps_last_good_set_and_writes_diagnostics(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    good = json.loads((tmp_path / "out" / "manifest.json").read_text())
    monkeypatch.setattr(C, "render_html", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rc = bounty(tmp_path, "--no-detail", now="2026-10-16T12:00:00Z")
    assert rc == 6
    assert json.loads((tmp_path / "out" / "manifest.json").read_text())["run_id"] == good["run_id"]
    assert C.verify_manifest(tmp_path / "out") == []
    assert (tmp_path / "out-diagnostics" / "error.md").exists()
    assert not (tmp_path / "out.new").exists()


def test_publish_dir_recovers_from_crash_between_renames(tmp_path):
    final, old = tmp_path / "out", tmp_path / "out.old"
    old.mkdir()
    (old / "x").write_text("last good")
    C.recover_dir(final)                                                    # crash happened after final -> .old
    assert (final / "x").read_text() == "last good" and not old.exists()


def test_manifest_detects_tampering_and_unlisted_files(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "a.txt").write_text("a")
    C.write_manifest(d, "r1", NOW, {"run_status": "success"}, [], {})
    assert C.verify_manifest(d) == []
    (d / "a.txt").write_text("changed")
    (d / "stale.md").write_text("old brief")
    problems = C.verify_manifest(d)
    assert any("hash mismatch" in p for p in problems) and any("unlisted" in p for p in problems)


def test_verify_state_flags_corrupt_sqlite(tmp_path):
    st = tmp_path / "state"
    st.mkdir()
    (st / "bounty.sqlite3").write_bytes(b"not a database" * 100)
    assert C.main_bounty(["verify-state", "--state-dir", str(st)]) == 7
    assert C.main_bounty(["verify-state", "--state-dir", str(tmp_path / "empty")]) == 7


def test_evaluate_only_never_fetches(tmp_path, monkeypatch):
    t = fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    t.calls.clear()
    assert bounty(tmp_path, action="evaluate") == 0
    assert t.calls == []
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert m["run_status"]["run_status"] == "evaluate_only"


def test_report_shows_status_and_unverified_wording(tmp_path, monkeypatch):
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    html = (tmp_path / "out" / "report.html").read_text()
    assert "UNVERIFIED" in html and "Check these first" in html and "Ready to build" in html
    assert "criteria" in html.lower()


def test_review_priority_penalises_hardware_or_engine_mismatch():
    plain, vr = rich(), rich()
    vr.title = "Meta VR Start Developer Competition"
    e = estimate(plain, CFG)
    a = review_priority(plain, e, gate(plain, CFG, NOW, {}), CFG, NOW)
    b = review_priority(vr, e, gate(vr, CFG, NOW, {}), CFG, NOW)
    assert b["value"] < a["value"] and b["tech_mismatch_keywords"]


def test_verify_state_accepts_legacy_latest_without_manifest_but_not_a_broken_manifest(tmp_path, monkeypatch):
    """Regression for the first CI run: the state branch written by v0.2.0 has latest/ without manifest.json."""
    fake_fetcher(monkeypatch, pages8())
    bounty(tmp_path, "--no-detail")
    st = tmp_path / "state"
    (st / "latest" / "manifest.json").unlink()
    assert C.main_bounty(["verify-state", "--state-dir", str(st)]) == 0
    bounty(tmp_path, "--no-detail", now="2026-10-16T12:00:00Z")                      # next run replaces latest/ with a verified set
    assert (st / "latest" / "manifest.json").exists()
    (st / "latest" / "report.html").write_text("tampered")
    assert C.main_bounty(["verify-state", "--state-dir", str(st)]) == 7
