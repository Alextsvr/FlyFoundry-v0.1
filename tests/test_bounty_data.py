"""Data layer: listing validation, completeness, unlisting guard, dedupe, per-fact freshness, evidence, retention, migration."""
import json
import sqlite3
from datetime import timedelta

import pytest

from _bounty_common import *   # noqa: F401,F403
from flyfoundry.bounty_factory import detail, pipeline as P
from flyfoundry.bounty_factory.http import Fetcher
from flyfoundry.bounty_factory.model import Opportunity, norm_text, stable_id, canonical_url, sha256_text
from flyfoundry.bounty_factory.sources import devpost
from flyfoundry.bounty_factory.store import Store

T0 = "2026-10-15T12:00:00Z"
CFG2 = dict(CFG)


def run_discover(store, pages, now=NOW, **tk):
    t = make_transport(pages, **tk)
    return P.discover(store, CFG, fetcher(t), now, manual_path="/nonexistent.json", log=lambda *_: None), t


def n_listed(store):
    return sum(1 for o in store.all() if o.status == "listed")


# ---------- parsing basics
def test_prize_and_deadline_parsing():
    assert devpost.parse_prize("$<span data-currency-value>275</span>")[:2] == (275.0, "USD")
    assert devpost.parse_prize("₹ 15,000")[:2] == (15000.0, "INR")
    assert devpost.parse_deadline("Aug 16 - Oct 15, 2026") == "2026-10-15"
    assert devpost.parse_deadline("Dec 30, 2026 - Jan 15, 2027") == "2027-01-15"
    assert devpost.parse_deadline("garbage") is None


def test_unknown_fields_stay_unknown():
    o = devpost.to_opportunity({"id": 1, "title": "X", "url": "https://x.devpost.com/"}, "u")
    assert not o.fact("prize_amount").known() and not o.fact("deadline_date").known()


# ---------- 2.1 listing schema
def test_schema_validation():
    with pytest.raises(devpost.SchemaError):
        devpost.validate_page({})
    with pytest.raises(devpost.SchemaError):
        devpost.validate_page({"error": "rate limited"})
    with pytest.raises(devpost.SchemaError):
        devpost.validate_page({"hackathons": "nope"})
    items, meta = devpost.validate_page({"hackathons": [], "meta": {"total_count": 0}})
    assert items == []                                  # a valid, explicitly empty listing
    with pytest.raises(devpost.SchemaError):
        devpost.validate_page({"hackathons": [{"id": 1}, {"id": 2}, {"id": 3}, item(4, "ok")]})    # most items malformed


def test_http_200_with_wrong_schema_does_not_unlist_anything(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    pg = page([item(i, f"Hack {i}") for i in range(1, 9)])
    r, _ = run_discover(s, [pg])
    assert r["devpost"]["status"] == "ok" and n_listed(s) == 8
    r, _ = run_discover(s, [], list_body="{}", now=NOW + timedelta(days=1))
    assert r["devpost"]["status"] == "schema_error" and not r["devpost"]["complete"]
    assert n_listed(s) == 8
    r, _ = run_discover(s, [], list_body="<html>captcha</html>", now=NOW + timedelta(days=2))
    assert r["devpost"]["status"] != "ok" and n_listed(s) == 8


def test_source_failure_keeps_prior_data(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(i, f"Hack {i}") for i in range(1, 9)])])
    r, _ = run_discover(s, [], list_status=500, now=NOW + timedelta(days=1))
    assert r["devpost"]["status"] == "failed" and n_listed(s) == 8
    st = P.run_status(r, s, CFG)
    assert st["run_status"] == "source_unavailable" and st["exit_code"] == 4


def test_incomplete_listing_never_mass_unlists(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(i, f"Hack {i}") for i in range(1, 9)])])
    # page cap reached: listing claims 40 records but only 2 pages of 3 are served
    pages = [page([item(100 + i, f"New {i}") for i in range(3)], total=40, per_page=3, current=1),
             page([item(200 + i, f"Newer {i}") for i in range(3)], total=40, per_page=3, current=2)]
    cfg = dict(CFG, max_list_pages=2)
    r = P.discover(s, cfg, fetcher(make_transport(pages)), NOW + timedelta(days=1), manual_path="/nonexistent.json", log=lambda *_: None)
    assert r["devpost"]["status"] == "partial" and not r["devpost"]["complete"]
    assert all(o.status == "listed" for o in s.all())
    assert P.run_status(r, s, CFG)["exit_code"] == 3


def test_total_count_mismatch_is_partial(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    r, _ = run_discover(s, [page([item(i, f"H{i}") for i in range(1, 4)], total=10, per_page=24)])
    assert r["devpost"]["status"] == "partial" and r["devpost"]["total_count_claimed"] == 10


def test_pagination_repeat_is_detected(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    same = page([item(i, f"H{i}") for i in range(1, 4)], total=100, per_page=3)
    r, _ = run_discover(s, [same, same, same])
    assert r["devpost"]["status"] == "partial" and "repeated" in r["devpost"]["error"]


def test_duplicate_items_in_listing_are_counted(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    r, _ = run_discover(s, [page([item(1, "A"), item(1, "A"), item(2, "B")], total=2)])
    assert r["devpost"]["duplicate_items_in_listing"] == 1 and n_listed(s) == 2


def test_shrink_guard_blocks_suspicious_unlisting(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(i, f"Hack {i}") for i in range(1, 21)])])
    r, _ = run_discover(s, [page([item(1, "Hack 1")])], now=NOW + timedelta(days=1))
    assert n_listed(s) == 20 and r["devpost"]["status"] == "partial" and "suspicious shrink" in r["devpost"]["error"]


def test_small_normal_removal_is_marked_unlisted(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(i, f"Hack {i}") for i in range(1, 21)])])
    r, _ = run_discover(s, [page([item(i, f"Hack {i}") for i in range(1, 20)])], now=NOW + timedelta(days=1))
    assert r["devpost"]["status"] == "ok" and n_listed(s) == 19
    assert [o.status for o in s.all() if o.title == "Hack 20"] == ["unlisted"]


def test_robots_denied_is_blocked_not_bypassed(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    r, t = run_discover(s, [page([item(1, "A")])], robots="User-agent: *\nDisallow: /")
    assert r["devpost"]["status"] == "blocked_by_robots"
    assert not [u for u in t.calls if "/api/hackathons" in u]


# ---------- 2.2 dedupe
def test_unicode_normalization_and_empty_keys():
    assert norm_text("Хакатон «Мир»") == "хакатон мир"
    assert norm_text("Café  Hack") == norm_text("CAFÉ hack")
    cyr = Opportunity(id="a", source="m", source_key="1", url="https://a.example/1", title="Хакатон", organizer="Организатор")
    assert [k for k in cyr.dedupe_keys() if k.startswith("t:")] == ["t:хакатон|организатор"]
    empty = Opportunity(id="b", source="m", source_key="2", url="https://b.example/2", title="!!!", organizer="???")
    assert all(k.startswith("u:") for k in empty.dedupe_keys())
    nothing = Opportunity(id="c", source="m", source_key="3", url="https://c.example/3", title="Ok", organizer="")
    assert all(k.startswith("u:") for k in nothing.dedupe_keys())


def test_two_unrelated_non_latin_titles_do_not_collide(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    for i, (t, org) in enumerate([("!!!", "???"), ("***", "###")]):
        o = Opportunity(id=stable_id(f"https://e{i}.example/"), source="m", source_key=str(i), url=f"https://e{i}.example/", title=t, organizer=org)
        s.upsert(o, T0)
    assert len(s.all()) == 2


def _annual(url, deadline):
    o = Opportunity(id=stable_id(url), source="m", source_key=url, url=url, title="Global Hack", organizer="Acme")
    o.set("deadline_date", deadline, "source_claim", "t", origin="list")
    return o


def test_annual_event_same_title_different_deadline_not_merged(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    a, _ = s.upsert(_annual("https://globalhack.example/2025", "2025-10-01"), T0)
    b, out = s.upsert(_annual("https://globalhack.example/2026", "2026-10-30"), T0)
    assert a != b and out == "new" and len(s.all()) == 2
    assert s.get(a).possible_duplicates == [b] and s.get(b).possible_duplicates == [a]       # flagged, provenance kept


def test_same_title_same_deadline_other_url_merges_with_alias(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    a, _ = s.upsert(_annual("https://one.example/x", "2026-10-30"), T0)
    b, out = s.upsert(_annual("https://two.example/y", "2026-10-30"), T0)
    assert a == b and out == "duplicate_merged" and len(s.all()) == 1
    al = s.get(a).aliases[0]
    assert al["url"] == "https://two.example/y" and al["matched_by"] == "title+organizer+deadline"


# ---------- 2.3 per-fact freshness
def test_fact_last_confirmed_vs_record_last_seen(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(1, "A", prize="$100")])])
    run_discover(s, [page([item(1, "A", prize="$100")])], now=NOW + timedelta(days=1))
    o = s.all()[0]
    f = o.fact("prize_amount")
    assert o.last_seen.startswith("2026-10-16") and f.observed_at.startswith("2026-10-16") and f.changed_at.startswith("2026-10-15")


def test_changed_value_keeps_history(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(1, "A", prize="$100")])])
    run_discover(s, [page([item(1, "A", prize="$250")])], now=NOW + timedelta(days=1))
    f = s.all()[0].fact("prize_amount")
    assert f.value == 250.0 and f.history[-1]["value"] == 100.0 and f.history[-1]["end"] == "changed"
    assert any(c["field"] == "prize_amount" for c in s.all_changes())


def test_vanished_value_is_withdrawn_not_fresh(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(1, "A", prize="$100")])])
    run_discover(s, [page([item(1, "A", prize=None)])], now=NOW + timedelta(days=1))
    f = s.all()[0].fact("prize_amount")
    assert not f.known() and f.status == "withdrawn" and f.last_value == 100.0
    assert f.history[-1]["end"] == "withdrawn"


# ---------- 2.4 evidence and detail policy
RULES = "<html><body><h1>Rules</h1><p>Entry is free. You do not need to connect a wallet.</p><p>You must submit a GitHub repo.</p></body></html>"


def seed_one(tmp_path, **kw):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(1, "A", **kw)])])
    return s


def detail_pass(s, status_map=None, now=NOW, body=RULES):
    calls = []

    def d(url):
        calls.append(url)
        if status_map and url in status_map:
            return status_map[url], "denied"
        return 200, body
    t = make_transport([], detail=d)
    f = fetcher(t)
    return P.enrich_details(s, CFG, f, now, log=lambda *_: None), calls, f


def test_detail_stores_raw_evidence_and_links_facts(tmp_path):
    s = seed_one(tmp_path)
    r, calls, _ = detail_pass(s)
    assert r["pages_ok"] == 2
    o = s.all()[0]
    f = o.fact("rules_hash")
    obs = s.observation(f.observation_id)
    assert obs["http_status"] == 200 and obs["raw_hash"] == sha256_text(s.raw(obs["id"])) and obs["parser_version"] == detail.PARSER_VERSION
    assert obs["url"].endswith("/rules") and f.parser_version == detail.PARSER_VERSION
    assert o.fact("token_or_wallet_required").value is False and o.fact("token_or_wallet_required").observation_id


def test_overview_success_does_not_delay_rules_recheck(tmp_path):
    s = seed_one(tmp_path)
    t0 = NOW
    r, calls, _ = detail_pass(s, status_map={"https://h1.devpost.com/rules": 500}, now=t0)
    o = s.all()[0]
    assert o.detail["overview"]["ok"] and not o.detail["rules"]["ok"]
    assert detail.due(o.detail["rules"], t0 + timedelta(minutes=1))                 # transient failure: retried on the next run
    assert not detail.due(o.detail["overview"], t0 + timedelta(days=1))              # overview fine for 7 days
    r2, calls2, _ = detail_pass(s, now=t0 + timedelta(hours=6))
    assert calls2 == ["https://h1.devpost.com/rules"] and r2["pages_ok"] == 1


def test_403_uses_longer_backoff_and_circuit_breaker(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    run_discover(s, [page([item(i, f"H{i}") for i in range(1, 6)])])
    r, calls, f = detail_pass(s, status_map={f"https://h{i}.devpost.com/{p}": 403 for i in range(1, 6) for p in ("", "rules")})
    assert len([c for c in calls]) == 1 and r["blocked"] and f.denied_hosts          # first 403 stops the pass: no hammering, no bypass
    o = [x for x in s.all() if x.detail][0]
    assert o.detail["overview"]["http_status"] == 403
    assert not detail.due(o.detail["overview"], NOW + timedelta(days=2)) and detail.due(o.detail["overview"], NOW + timedelta(days=3, minutes=1))


def test_not_due_next_due_values():
    assert detail.next_due(200, NOW).startswith("2026-10-22")
    assert detail.next_due(404, NOW).startswith("2026-10-22")
    assert detail.next_due(403, NOW).startswith("2026-10-18")
    assert detail.next_due(500, NOW).startswith("2026-10-15T12:00")
    assert detail.next_due(0, NOW).startswith("2026-10-15T12:00")


def test_rules_change_updates_hash_and_keeps_history(tmp_path):
    s = seed_one(tmp_path)
    detail_pass(s)
    h1 = s.all()[0].fact("rules_hash").value
    detail_pass(s, now=NOW + timedelta(days=8), body=RULES.replace("Entry is free.", "Entry fee: $20."))
    o = s.all()[0]
    assert o.fact("rules_hash").value != h1 and o.fact("rules_hash").history[-1]["value"] == h1
    assert o.fact("fees_required").value is True


# ---------- retention and migration
def test_prune_bounds_growth_keeps_referenced_evidence(tmp_path):
    s = seed_one(tmp_path)
    detail_pass(s)
    run = s.start_run("devpost", T0)
    for d in range(40):
        s.add_observation(run, "devpost", "k", "https://x/list", f"2025-0{1 + d // 28}-{1 + d % 28:02d}T00:00:00Z", "z" * 1000, kind="list", http_status=200)
    s.db.commit()
    ref = s.all()[0].fact("rules_hash").observation_id
    out = s.prune(NOW)
    assert out["raw_dropped"] > 0 or out["observations_deleted"] > 0
    assert s.raw(ref)                                            # referenced evidence survives
    assert s.integrity() == []


def test_prune_caps_change_log(tmp_path):
    s = Store(tmp_path / "s.sqlite3")
    for i in range(50):
        s._log("x", T0, "f", i, i + 1)
    s.db.commit()
    assert s.prune(NOW, max_changes=10)["changes_deleted"] == 40


def test_migration_of_old_v1_database(tmp_path):
    p = tmp_path / "old.sqlite3"
    c = sqlite3.connect(p)
    c.executescript("""
CREATE TABLE source_runs(id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT, status TEXT, http_status INTEGER, n_records INTEGER, complete INTEGER, requests INTEGER, error TEXT);
CREATE TABLE observations(id INTEGER PRIMARY KEY, run_id INTEGER, source TEXT, source_key TEXT, url TEXT, fetched_at TEXT, raw_hash TEXT, raw_text TEXT);
CREATE TABLE opportunities(id TEXT PRIMARY KEY, canonical TEXT, record TEXT, first_seen TEXT, last_seen TEXT);
CREATE TABLE keys(key TEXT PRIMARY KEY, opp_id TEXT);
CREATE TABLE changes(id INTEGER PRIMARY KEY, opp_id TEXT, at TEXT, field TEXT, old TEXT, new TEXT);
""")
    rec = {"id": "bf-old", "source": "devpost", "source_key": "1", "url": "https://old.devpost.com/", "title": "Old", "organizer": "Org", "kind": "hackathon",
           "facts": {"deadline_date": {"value": "2026-11-30", "basis": "source_claim", "evidence": "x", "observed_at": "2026-10-01T00:00:00Z"}},
           "first_seen": "2026-10-01T00:00:00Z", "last_seen": "2026-10-01T00:00:00Z", "status": "listed", "aliases": [], "observation_ids": [], "detail_fetched_at": ""}
    c.execute("INSERT INTO opportunities VALUES('bf-old','old.devpost.com',?,?,?)", (json.dumps(rec), "a", "b"))
    c.execute("INSERT INTO observations(id,run_id,source,source_key,url,fetched_at,raw_hash,raw_text) VALUES(1,1,'devpost','u','https://x','t','h','raw')")
    c.commit()
    c.close()
    s = Store(p)
    o = s.get("bf-old")
    assert o.fact("deadline_date").value == "2026-11-30" and s.raw(1) == "raw"
    assert s.db.execute("PRAGMA user_version").fetchone()[0] == 2 and s.integrity() == []
    assert s.find_strong(Opportunity(id="z", source="d", source_key="9", url="https://old.devpost.com", title="Old", organizer="Org")) == "bf-old"
    s.close()
    Store(p).close()                                                                 # opening again is a no-op
