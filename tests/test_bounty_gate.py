"""Eligibility gate: stale confirmations, mandatory conditions, false hard rejects (audit findings 1.1-1.3)."""
import copy
from datetime import timedelta

import pytest

from _bounty_common import *   # noqa: F401,F403
from flyfoundry.bounty_factory import detail
from flyfoundry.bounty_factory.gate import evaluate as gate, ELIGIBLE, INELIGIBLE, NEEDS_REVIEW, REQUIRED, evidence_hash, deadline_status
from flyfoundry.bounty_factory.model import Opportunity

PART = CFG["participant"]


def codes(g, level=None):
    return [r["code"] for r in g["reasons"] if level is None or r["level"] == level]


def verified_opp():
    o = listed()
    o.set("rules_hash", RULES_HASH, "source_claim", "rules page", origin="rules")
    return o


# ---------- 1.2 mandatory conditions
def test_future_deadline_no_fee_and_geo_ok_is_not_enough():
    o = listed(fees_required=False, geo_eligible=True)
    g = gate(o, CFG, NOW, {})
    assert g["decision"] == NEEDS_REVIEW and not g["verified"]
    assert g["conditions_confirmed"] < len(REQUIRED)
    unknown = [c for c, s in g["conditions"].items() if s["status"] == "unknown"]
    for c in ("age_team", "tools_and_costs", "hardware", "wallet", "conflicts", "fees", "geography"):
        assert c in unknown                      # source claims alone never confirm these


def test_complete_current_review_makes_eligible():
    o = verified_opp()
    g = gate(o, CFG, NOW, review(o))
    assert g["decision"] == ELIGIBLE and g["verified"] and g["conditions_confirmed"] == len(REQUIRED)


def test_review_with_missing_condition_is_incomplete():
    o = verified_opp()
    rv = review(o)
    del rv[o.id]["conditions"]["hardware"]
    g = gate(o, CFG, NOW, rv)
    assert g["decision"] == NEEDS_REVIEW and "unconfirmed:hardware" in codes(g)


def test_not_applicable_needs_justification():
    o = verified_opp()
    g = gate(o, CFG, NOW, review(o, conditions={"wallet": {"status": "not_applicable", "note": "x"}}))
    assert g["decision"] == NEEDS_REVIEW and g["conditions"]["wallet"]["status"] == "unknown"
    g = gate(o, CFG, NOW, review(o, conditions={"wallet": {"status": "not_applicable", "note": "no blockchain component anywhere in the rules"}}))
    assert g["decision"] == ELIGIBLE and g["conditions"]["wallet"]["status"] == "not_applicable"


def test_excluded_condition_in_review_rejects():
    o = verified_opp()
    g = gate(o, CFG, NOW, review(o, conditions={"geography": {"status": "excluded", "note": "Latvia not listed"}}))
    assert g["decision"] == INELIGIBLE and "geo_excluded" in codes(g, "hard")


# ---------- 1.1 stale confirmations (the audit regression)
def test_old_manual_confirmation_does_not_override_new_contradiction():
    """Old review said fees none / geography ok. Later the source says fees_required=True and geo_eligible=False."""
    o = verified_opp()
    rv = review(o)
    assert gate(o, CFG, NOW, rv)["decision"] == ELIGIBLE
    o.set("fees_required", True, "source_claim", "Rules: a $25 entry fee applies", origin="rules")
    o.set("geo_eligible", False, "source_claim", "Open to US residents only", origin="rules")
    g = gate(o, CFG, NOW, rv)
    assert g["decision"] != ELIGIBLE
    assert g["decision"] == NEEDS_REVIEW
    c = codes(g, "review")
    assert "review_conflict:fees" in c and "review_conflict:geography" in c
    detail_txt = " ".join(r["detail"] for r in g["reasons"] if r["code"].startswith("review_conflict"))
    assert "says ok" in detail_txt and "$25 entry fee" in detail_txt and "US residents only" in detail_txt     # both sides kept


def test_review_expires():
    o = verified_opp()
    g = gate(o, CFG, NOW + timedelta(days=CFG["review_valid_days"] + 2), review(o))
    assert g["decision"] == NEEDS_REVIEW and "review_stale" in codes(g)


def test_review_bound_to_rules_version():
    o = verified_opp()
    rv = review(o)
    o.set("rules_hash", "b" * 64, "source_claim", "rules page changed", origin="rules")
    g = gate(o, CFG, NOW, rv)
    assert g["decision"] == NEEDS_REVIEW and "review_rules_changed" in codes(g)


def test_review_bound_to_participant_config():
    o = verified_opp()
    rv = review(o)
    cfg2 = copy.deepcopy(CFG)
    cfg2["participant"]["country_code"] = "DE"
    g = gate(o, cfg2, NOW, rv)
    assert g["decision"] == NEEDS_REVIEW and "review_participant_changed" in codes(g)
    cfg3 = copy.deepcopy(CFG)
    cfg3["available_hardware"] = ["cpu", "gpu"]
    assert "review_participant_changed" in codes(gate(o, cfg3, NOW, rv))


def test_legacy_review_is_kept_but_needs_re_review():
    o = verified_opp()
    legacy = {o.id: {"id": o.id, "reviewed_at": "2026-10-14", "fees_required": False, "geo_eligible": True, "evidence_url": "https://x"}}
    g = gate(o, CFG, NOW, legacy)
    assert g["decision"] == NEEDS_REVIEW and "review_legacy_incomplete" in codes(g)
    assert g["review_status"] == "review_legacy_incomplete"


def test_acknowledged_signal_clears_only_that_evidence():
    o = verified_opp()
    o.set("fees_required", True, "source_claim", "Rules: fee of $5 refunded on submission", origin="rules", strength="firm")
    assert gate(o, CFG, NOW, review(o))["decision"] == NEEDS_REVIEW        # contradiction is not silently overridden
    rv = review(o, acknowledged_signals=[{"fact": "fees_required", "evidence_sha256": evidence_hash(o.fact("fees_required").evidence)}])
    assert gate(o, CFG, NOW, rv)["decision"] == ELIGIBLE
    o.set("fees_required", True, "source_claim", "Rules: NEW fee of $50", origin="rules", strength="firm")           # different evidence -> not acknowledged
    assert gate(o, CFG, NOW, rv)["decision"] != ELIGIBLE


def test_human_entered_fact_vs_newer_source_claim_is_conflict():
    o = verified_opp()
    o.set("fees_required", False, "human_entered", "I read the rules", origin="human")
    o.facts["fees_required"].conflicts.append({"value": True, "evidence": "source now says fee", "at": "2026-10-15"})
    g = gate(o, CFG, NOW, {})
    assert g["conditions"]["fees"]["status"] == "contradicted" and g["decision"] != ELIGIBLE


# ---------- 1.3 false hard rejects: the five exact inputs
CASES = {
    "wallet_negation": "You do not need a crypto wallet to participate. No wallet is required.",
    "no_hardware": "No hardware is required. You can build a web app or a robot.",
    "fee_zero": "Registration fee: $0.",
    "geo_mixed": "Residents of Latvia are eligible. Residents of Canada are not eligible.",
    "age_and_fee": "There is no age restriction. Registration fee is $50.",
}


def sig(text):
    return detail.analyse(text, PART)


def test_wallet_negation_is_not_a_wallet_requirement():
    s = sig(CASES["wallet_negation"])
    assert s.get("token_or_wallet_required", {}).get("value") is not True


def test_hardware_alternative_is_not_a_hardware_requirement():
    s = sig(CASES["no_hardware"])
    hw = s.get("hardware_required")
    assert hw is None or hw["value"] is False or hw["strength"] == "weak"
    o = listed()
    for n, v in s.items():
        o.set(n, v["value"], "source_claim", v["evidence"], strength=v["strength"], origin="rules")
    assert INELIGIBLE != gate(o, CFG, NOW, {})["decision"]


def test_zero_fee_is_not_a_fee():
    s = sig(CASES["fee_zero"])
    assert s.get("fees_required", {}).get("value") is not True


def test_latvia_eligible_canada_not_is_not_exclusion_of_participant():
    s = sig(CASES["geo_mixed"])
    assert not s.get("geo_excludes_participant")
    assert s.get("geo_includes_participant", {}).get("value") is True
    o = listed()
    for n, v in s.items():
        o.set(n, v["value"], "source_claim", v["evidence"], strength=v["strength"], origin="rules")
    assert gate(o, CFG, NOW, {})["decision"] != INELIGIBLE


def test_no_age_restriction_does_not_hide_a_fee():
    s = sig(CASES["age_and_fee"])
    assert s["fees_required"]["value"] is True and s["fees_required"]["strength"] != "weak"
    o = listed()
    for n, v in s.items():
        o.set(n, v["value"], "source_claim", v["evidence"], strength=v["strength"], origin="rules")
    g = gate(o, CFG, NOW, {})
    assert g["decision"] == INELIGIBLE and "fee_required" in codes(g, "hard")


@pytest.mark.parametrize("text,kind", [("A GPU is required to train the model.", "gpu"), ("You must bring a Raspberry Pi.", None), ("Participants must use the GPU credits provided.", "gpu")])
def test_hardware_judged_against_participant_config(text, kind):
    s = sig(text)
    hw = s.get("hardware_required")
    assert hw is not None
    o = listed()
    o.set("hardware_required", hw["value"], "source_claim", hw["evidence"], strength=hw["strength"], origin="rules")
    g = gate(o, CFG, NOW, {})
    if isinstance(hw["value"], list) and hw["strength"] != "weak":
        assert set(hw["value"]) - set(CFG["available_hardware"])
        assert g["decision"] == INELIGIBLE and "hardware_unavailable" in codes(g, "hard")
    else:
        assert g["decision"] == NEEDS_REVIEW


def test_hardware_available_in_config_is_not_a_blocker():
    o = listed()
    o.set("hardware_required", ["cpu"], "source_claim", "A laptop CPU is enough", strength="firm", origin="rules")
    assert "hardware_unavailable" not in codes(gate(o, CFG, NOW, {}))


def test_weak_signal_never_hard_rejects():
    o = listed()
    o.set("fees_required", True, "source_claim", "maybe a fee", strength="weak", origin="rules")
    o.set("token_or_wallet_required", True, "source_claim", "maybe wallet", strength="weak", origin="rules")
    g = gate(o, CFG, NOW, {})
    assert g["decision"] == NEEDS_REVIEW and not codes(g, "hard")


# ---------- deadline / basics
def test_deadline_windows():
    assert deadline_status(listed(deadline_date="2026-10-10"), NOW) == "expired"
    assert deadline_status(listed(deadline_date="2026-10-15"), NOW) == "ambiguous"
    assert deadline_status(listed(deadline_date="2026-12-01"), NOW) == "open"
    assert deadline_status(opp(), NOW) == "unknown"


def test_expired_and_invite_only_are_hard():
    assert gate(listed(deadline_date="2026-01-01"), CFG, NOW, {})["decision"] == INELIGIBLE
    assert "invite_only" in codes(gate(listed(invite_only=True), CFG, NOW, {}), "hard")


def test_payments_domain_requires_conflict_confirmation():
    o = verified_opp()
    o.title = "Global Payments Merchant Hackathon"
    rv = review(o)
    rv[o.id]["conditions"]["conflicts"] = {"status": "ok", "note": "no merchant contact or employer data needed per rules"}
    assert gate(o, CFG, NOW, rv)["decision"] == ELIGIBLE
    assert gate(o, CFG, NOW, {})["decision"] == NEEDS_REVIEW
    assert "possible_employer_conflict" in codes(gate(o, CFG, NOW, {}))


def test_unlisted_goes_to_review():
    o = verified_opp()
    o.status = "unlisted"
    g = gate(o, CFG, NOW, review(o))
    assert g["decision"] == NEEDS_REVIEW and "unlisted" in codes(g)
