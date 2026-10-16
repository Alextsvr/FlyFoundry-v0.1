"""State database safety (second independent review, P1-1 and P1-2): read-only verification, safe migration of a REAL v1 state,
origin back-fill, withdrawal of vanished facts after migration. Fixture: tests/fixtures/bounty_v1_state.sqlite3 is a trimmed copy
(3 of 48 records) of the real state written by the v0.2.0 code (user_version 0, no origin on any fact)."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from _bounty_common import *   # noqa: F401,F403
from flyfoundry.bounty_factory import cli as C, pipeline as P
from flyfoundry.bounty_factory.model import Opportunity
from flyfoundry.bounty_factory.store import Store, inspect_db, migrate_file, SCHEMA_VERSION, backfill_origins

FIX = Path(__file__).parent / "fixtures" / "bounty_v1_state.sqlite3"
ROOT = Path(__file__).resolve().parent.parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def v1(tmp_path, name="state"):
    d = tmp_path / name
    d.mkdir()
    shutil.copy(FIX, d / "bounty.sqlite3")
    return d


def verify(d):
    return C.main_bounty(["verify-state", "--state-dir", str(d)])


# ---------- P1-1: verification is read-only and rejects junk
def test_fixture_is_a_real_legacy_database():
    r = inspect_db(FIX)
    assert r["status"] == "legacy" and r["version"] == 0 and r["opportunities"] == 3


def test_zero_byte_database_is_rejected_and_untouched(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "bounty.sqlite3").write_bytes(b"")
    assert verify(d) == 7
    assert (d / "bounty.sqlite3").stat().st_size == 0


def test_foreign_sqlite_is_rejected_and_untouched(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    c = sqlite3.connect(d / "bounty.sqlite3")
    c.execute("create table other(x)")
    c.commit()
    c.close()
    before = sha(d / "bounty.sqlite3")
    assert verify(d) == 7 and sha(d / "bounty.sqlite3") == before
    assert inspect_db(d / "bounty.sqlite3")["status"] == "foreign"


def test_not_sqlite_and_corrupt_are_rejected(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "bounty.sqlite3").write_bytes(b"garbage" * 300)
    assert verify(d) == 7 and inspect_db(d / "bounty.sqlite3")["status"] == "not_sqlite"
    shutil.copy(FIX, d / "bounty.sqlite3")
    raw = bytearray((d / "bounty.sqlite3").read_bytes())
    raw[4096 * 2:4096 * 2 + 200] = b"\xff" * 200
    (d / "bounty.sqlite3").write_bytes(bytes(raw))
    assert inspect_db(d / "bounty.sqlite3")["status"] in ("corrupt", "invalid_records", "incomplete")
    assert verify(d) == 7


@pytest.mark.parametrize("drop", ["observations", "keys", "changes", "source_runs", "opportunities"])
def test_missing_required_table_is_rejected(tmp_path, drop):
    d = v1(tmp_path)
    c = sqlite3.connect(d / "bounty.sqlite3")
    c.execute(f"drop table {drop}")
    c.commit()
    c.close()
    before = sha(d / "bounty.sqlite3")
    assert verify(d) == 7 and sha(d / "bounty.sqlite3") == before
    assert inspect_db(d / "bounty.sqlite3")["status"] == "incomplete"


def test_missing_required_column_is_rejected(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    c = sqlite3.connect(d / "bounty.sqlite3")
    c.executescript("create table source_runs(id); create table observations(id); create table opportunities(id,record); create table keys(key,opp_id); create table changes(id)")
    c.commit()
    c.close()
    assert inspect_db(d / "bounty.sqlite3")["status"] == "incomplete" and verify(d) == 7


def test_valid_empty_application_database_is_accepted(tmp_path):
    d = tmp_path / "s"
    Store(d / "bounty.sqlite3").close()
    assert inspect_db(d / "bounty.sqlite3")["status"] == "current" and verify(d) == 0


def test_newer_database_version_is_rejected(tmp_path):
    d = tmp_path / "s"
    Store(d / "bounty.sqlite3").close()
    c = sqlite3.connect(d / "bounty.sqlite3")
    c.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
    c.commit()
    c.close()
    assert inspect_db(d / "bounty.sqlite3")["status"] == "newer" and verify(d) == 7


def test_verify_state_never_modifies_a_legacy_database(tmp_path):
    d = v1(tmp_path)
    before = sha(d / "bounty.sqlite3")
    assert verify(d) == 0                                              # valid legacy: accepted with a warning, NOT migrated
    assert sha(d / "bounty.sqlite3") == before
    assert not list(d.glob("*.bak")) and not list(d.glob("*.migrating"))


def test_run_refuses_a_broken_state_and_leaves_everything_untouched(tmp_path, monkeypatch):
    d = tmp_path / "state"
    d.mkdir()
    (d / "bounty.sqlite3").write_bytes(b"")
    t = make_transport([page([item(1, "A")])])
    monkeypatch.setattr(C, "Fetcher", lambda **kw: fetcher(t))
    rc = C.main_bounty(["run", "--state-dir", str(d), "--out", str(tmp_path / "out"), "--reviews", str(tmp_path / "r.json"), "--manual", str(tmp_path / "m.json"), "--now", "2026-10-15T12:00:00Z"])
    assert rc == 7 and (d / "bounty.sqlite3").stat().st_size == 0
    assert t.calls == []                                               # not even a request was made
    assert not (tmp_path / "out").exists()
    assert json.loads((tmp_path / "out-diagnostics" / "status.json").read_text())["run_status"] == "invalid_state"


def test_absent_database_is_a_normal_first_run(tmp_path, monkeypatch):
    t = make_transport([page([item(i, f"H{i}") for i in range(1, 4)])])
    monkeypatch.setattr(C, "Fetcher", lambda **kw: fetcher(t))
    d = tmp_path / "state"
    rc = C.main_bounty(["run", "--state-dir", str(d), "--out", str(tmp_path / "out"), "--reviews", str(tmp_path / "r.json"), "--manual", str(tmp_path / "m.json"), "--now", "2026-10-15T12:00:00Z", "--no-detail"])
    assert rc == 0 and inspect_db(d / "bounty.sqlite3")["status"] == "current"


# ---------- migration of the real legacy state
def test_explicit_migration_keeps_data_and_makes_a_backup(tmp_path):
    d = v1(tmp_path)
    db = d / "bounty.sqlite3"
    orig = sha(db)
    before = [r for r in sqlite3.connect(db).execute("select id, record from opportunities order by id")]
    res = migrate_file(db)
    assert res["migrated"] and res["records"] == 3 and sha(res["backup"]) == orig                 # backup is byte-identical to the original
    assert inspect_db(db)["status"] == "current"
    s = Store(db)
    assert s.integrity() == [] and [o.id for o in s.all()] == [b[0] for b in before]
    for (oid, rec), o in zip(before, sorted(s.all(), key=lambda x: x.id)):
        old = json.loads(rec)
        assert o.title == old["title"] and o.first_seen == old["first_seen"]
        for n, f in old["facts"].items():
            if f.get("value") is not None:
                assert o.fact(n).value == f["value"] and o.fact(n).observed_at == f.get("observed_at", "")        # nothing invented or dropped
                assert o.fact(n).origin == "list" and o.fact(n).observation_id is None                    # origin recovered, no invented link
    s.close()


def test_failed_migration_leaves_original_untouched(tmp_path, monkeypatch):
    d = v1(tmp_path)
    db = d / "bounty.sqlite3"
    orig = sha(db)
    from flyfoundry.bounty_factory import store as S
    monkeypatch.setattr(S.Store, "integrity", lambda self: ["injected problem"])
    with pytest.raises(RuntimeError):
        migrate_file(db)
    assert sha(db) == orig and not (d / "bounty.sqlite3.migrating").exists()


def test_run_migrates_legacy_state_with_backup_then_drops_it_after_next_success(tmp_path, monkeypatch):
    d = v1(tmp_path, "state")
    orig = sha(d / "bounty.sqlite3")
    monkeypatch.setattr(C, "Fetcher", lambda **kw: fetcher(make_transport([page([item(1, "A")])])))
    args = ["run", "--state-dir", str(d), "--out", str(tmp_path / "out"), "--reviews", str(tmp_path / "r.json"), "--manual", str(tmp_path / "m.json"), "--no-detail"]
    C.main_bounty(args + ["--now", "2026-10-15T12:00:00Z"])
    bak = d / "bounty.sqlite3.premigration.bak"
    assert bak.exists() and sha(bak) == orig
    C.main_bounty(args + ["--now", "2026-10-16T12:00:00Z"])
    assert not bak.exists()


# ---------- P1-2: origins and withdrawal after migration
def legacy_update(d, **facts):
    """apply a fresh list observation (new code path) to the first record of the migrated state"""
    s = Store(d / "bounty.sqlite3")
    o0 = s.all()[0]
    n = Opportunity(id=o0.id, source=o0.source, source_key=o0.source_key, url=o0.url, title=o0.title, organizer=o0.organizer)
    for k, v in facts.items():
        n.set(k, v, "source_claim", "Devpost list API test", origin="list")
    s.upsert(n, "2026-10-16T00:00:00Z")
    s.close()
    return o0.id


def test_full_cycle_v1_migration_update_vanish_reopen(tmp_path):
    d = v1(tmp_path)
    migrate_file(d / "bounty.sqlite3")
    s = Store(d / "bounty.sqlite3")
    o0 = s.all()[0]
    assert o0.fact("prize_amount").known() and o0.fact("deadline_date").known()
    prize, deadline = o0.fact("prize_amount").value, o0.fact("deadline_date").value
    s.close()
    # 1. the source still shows the same values: confirmed, not withdrawn
    legacy_update(d, prize_amount=prize, deadline_date=deadline)
    s = Store(d / "bounty.sqlite3")
    f = s.get(o0.id).fact("prize_amount")
    assert f.known() and f.value == prize and f.origin == "list" and f.observed_at == "2026-10-16T00:00:00Z"
    s.close()
    # 2. both values disappear from the source
    legacy_update(d, prize_amount=None, deadline_date=None)
    s = Store(d / "bounty.sqlite3")
    o = s.get(o0.id)
    for name, old in (("prize_amount", prize), ("deadline_date", deadline)):
        f = o.fact(name)
        assert not f.known() and f.status == "withdrawn" and f.last_value == old and f.history[-1]["end"] == "withdrawn"
    # 3. the withdrawn value takes no part in ranking or eligibility
    from flyfoundry.bounty_factory.scoring import prize_usd
    from flyfoundry.bounty_factory.gate import evaluate, deadline_status
    assert prize_usd(o, CFG) is None and deadline_status(o, NOW) == "unknown"
    assert "deadline_unknown" in [r["code"] for r in evaluate(o, CFG, NOW, {})["reasons"]]
    ev = P.evaluate(s, CFG, {}, NOW)
    row = [r for r in ev["rows"] if r["opp"].id == o0.id][0]
    assert row["score_a"] is None and row["crit"]["reward_amount"][0] is None
    s.close()
    # 4. reopen: nothing is resurrected and the migration is not repeated
    s = Store(d / "bounty.sqlite3")
    assert not s.get(o0.id).fact("prize_amount").known() and s.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION and s.integrity() == []
    s.close()


def test_already_migrated_v2_database_with_empty_origins_is_repaired(tmp_path):
    """The state written by the first CI run (code 0.2.1) already has user_version 2 and facts without origin."""
    d = v1(tmp_path)
    s = Store(d / "bounty.sqlite3")               # opens with the CURRENT code, then we simulate the old v2 result:
    s.close()
    c = sqlite3.connect(d / "bounty.sqlite3")
    rows = c.execute("select id, record from opportunities").fetchall()
    for oid, rec in rows:
        r = json.loads(rec)
        for f in r["facts"].values():
            f["origin"] = ""
            f["status"] = "current"
        c.execute("update opportunities set record=? where id=?", (json.dumps(r), oid))
    c.execute("PRAGMA user_version=2")
    c.commit()
    c.close()
    assert inspect_db(d / "bounty.sqlite3")["status"] == "legacy"
    migrate_file(d / "bounty.sqlite3")
    s = Store(d / "bounty.sqlite3")
    assert all(f.origin == "list" for o in s.all() for n, f in o.facts.items() if n == "prize_amount")
    s.close()


def test_unprovable_legacy_detail_value_becomes_historical_not_current():
    o = Opportunity(id="bf-x", source="devpost", source_key="1", url="https://x.devpost.com/", title="X", organizer="O")
    o.set("fees_required", False, "source_claim", "page text: Entry is free.")           # no origin: which page? which observation? unknown
    o.set("prize_amount", 100.0, "source_claim", "Devpost list API https://devpost.com/api/x: prize_amount='$100'")
    o.set("fee_text", "x", "human_entered", "typed")
    backfill_origins(o)
    f = o.fact("fees_required")
    assert not f.known() and f.status == "historical_unverified" and f.last_value is False and f.history[-1]["end"] == "historical_unverified"
    assert f.observed_at == "" and f.observation_id is None                                # nothing invented
    assert o.fact("prize_amount").known() and o.fact("prize_amount").origin == "list"
    assert o.fact("fee_text").origin == "human"
    gate_dec = __import__("flyfoundry.bounty_factory.gate", fromlist=["x"]).evaluate(o, CFG, NOW, {})
    assert gate_dec["conditions"]["fees"]["status"] == "unknown"                           # does NOT count as "no fee" any more


def test_human_confirmation_survives_migration_and_new_contradiction_is_kept(tmp_path):
    d = v1(tmp_path)
    c = sqlite3.connect(d / "bounty.sqlite3")
    oid, rec = c.execute("select id, record from opportunities limit 1").fetchone()
    r = json.loads(rec)
    r["facts"]["fees_required"] = {"value": False, "basis": "human_confirmed", "evidence": "I read the rules", "observed_at": "2026-10-14T00:00:00Z"}
    c.execute("update opportunities set record=? where id=?", (json.dumps(r), oid))
    c.commit()
    c.close()
    migrate_file(d / "bounty.sqlite3")
    s = Store(d / "bounty.sqlite3")
    f = s.get(oid).fact("fees_required")
    assert f.known() and f.value is False and f.basis == "human_confirmed" and f.origin == "human"
    n = Opportunity(id=oid, source="devpost", source_key="x", url=s.get(oid).url, title="t", organizer="o")
    n.set("fees_required", True, "source_claim", "Rules: $20 fee", strength="firm", origin="rules")
    s.apply_facts(oid, dict(n.facts), {"rules"}, "2026-10-16T00:00:00Z")
    f = s.get(oid).fact("fees_required")
    assert f.value is False and f.conflicts and f.conflicts[0]["value"] is True                 # human value kept, contradiction recorded
    s.close()


# ---------- a refused state must not be published over the remote (state scripts + the verify command together)
BASH = shutil.which("bash")
GIT = shutil.which("git")


@pytest.mark.skipif(sys.platform == "win32" or not (BASH and GIT), reason="state scripts are Linux/bash only; not supported on Windows")
def test_refused_state_never_overwrites_remote(tmp_path):
    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "PATH": __import__("os").environ["PATH"]}
    run = lambda cmd, cwd: subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    bare, work = tmp_path / "r.git", tmp_path / "w"
    run(["git", "init", "-q", "--bare", str(bare)], tmp_path)
    run(["git", "init", "-q", "-b", "main", str(work)], tmp_path)
    (work / "scripts").mkdir()
    for n in ("state_restore.sh", "state_save.sh"):
        shutil.copy(ROOT / "scripts" / n, work / "scripts" / n)
    (work / "README").write_text("x")
    for c in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], ["remote", "add", "origin", str(bare)], ["push", "-q", "origin", "main"]):
        run(["git", *c], work)
    verify_cmd = f'{sys.executable} -m flyfoundry bounty verify-state --state-dir "$1"'
    good = work / "state"
    Store(good / "bounty.sqlite3").close()
    e = dict(env, STATE_VERIFY=verify_cmd, STATE_BRANCH="flyfoundry-bounty-state", PYTHONPATH=str(ROOT))
    r = subprocess.run(["bash", "scripts/state_save.sh", "origin", "state", "m"], cwd=work, env=e, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    head = run(["git", "--git-dir", str(bare), "rev-parse", "refs/heads/flyfoundry-bounty-state"], tmp_path).stdout
    (good / "bounty.sqlite3").write_bytes(b"")                                       # the state is now damaged
    r = subprocess.run(["bash", "scripts/state_save.sh", "origin", "state", "m2"], cwd=work, env=e, capture_output=True, text=True)
    assert r.returncode == 1
    assert run(["git", "--git-dir", str(bare), "rev-parse", "refs/heads/flyfoundry-bounty-state"], tmp_path).stdout == head
