"""Parser: a requirement must be tied to ITS amount / country / action (second independent review, P1-3). Families of inputs, not single strings."""
import itertools

import pytest

from _bounty_common import *   # noqa: F401,F403
from flyfoundry.bounty_factory import detail
from flyfoundry.bounty_factory.gate import evaluate as gate, INELIGIBLE, NEEDS_REVIEW

PART = CFG["participant"]


def join(parts, how):
    if how == "period":
        return " ".join(p.rstrip(".;") + "." for p in parts)
    if how == "semicolon":
        return "; ".join(p.rstrip(".;") for p in parts) + "."
    if how == "newline":
        return "\n".join(parts)
    if how == "html_list":
        return detail.visible_text("<ul>" + "".join(f"<li>{p}</li>" for p in parts) + "</ul>")
    if how == "html_paragraphs":
        return detail.visible_text("".join(f"<p>{p}</p>" for p in parts))
    raise ValueError(how)


SEPARATORS = ["period", "semicolon", "newline", "html_list", "html_paragraphs"]


def sig(text):
    return detail.analyse(text, PART)


def decide(text):
    o = listed()
    for k, v in sig(text).items():
        o.set(k, v["value"], "source_claim", v["evidence"], strength=v["strength"], origin="rules")
    g = gate(o, CFG, NOW, {})
    return g["decision"], [r["code"] for r in g["reasons"] if r["level"] == "hard"]


def firm_true(s, name):
    return name in s and s[name]["value"] is True and s[name]["strength"] != "weak"


# ---------- fees: the amount belongs to the fee, not to the prize pool
FEE_NONE = ["No registration fee is required", "There is no entry fee", "Registration fee: $0", "Participation is free of charge, no application fee"]
POOL = ["Prizes total $5000", "Total prize pool: $25,000", "Winners share $10,000 in cash prizes", "The grand prize is worth $50,000"]


@pytest.mark.parametrize("how,fee,pool", itertools.product(SEPARATORS, FEE_NONE, POOL))
@pytest.mark.parametrize("order", ["fee_first", "pool_first"])
def test_zero_or_negated_fee_next_to_prize_pool_is_never_a_fee(how, fee, pool, order):
    parts = [fee, pool] if order == "fee_first" else [pool, fee]
    s = sig(join(parts, how))
    assert not firm_true(s, "fees_required"), s
    assert decide(join(parts, how))[0] != INELIGIBLE


@pytest.mark.parametrize("fee,pool", [("No registration fee is required", "prizes total $5000"), ("Registration fee: $0", "prize pool $25,000")])
def test_same_sentence_comma_and_dash_joins(fee, pool):
    for joiner in (", ", " - ", " and ", " but ", " (", ": "):
        text = f"{fee}{joiner}{pool}" + (")" if joiner == " (" else "") + "."
        assert not firm_true(sig(text), "fees_required"), text


@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("fee", ["Registration fee is $50", "Entry fee: $25", "A $30 entry fee applies", "Participants must pay a registration fee of 20 USD", "Deposit of $100 is required"])
def test_real_fee_stays_a_firm_hard_reject_even_with_a_prize_pool(how, fee):
    text = join([fee, "Prizes total $5000"], how)
    assert firm_true(sig(text), "fees_required")
    dec, hard = decide(text)
    assert dec == INELIGIBLE and "fee_required" in hard


def test_fee_after_no_age_restriction_still_detected():
    assert firm_true(sig("There is no age restriction. Registration fee is $50."), "fees_required")


def test_contradictory_fee_wording_is_weak():
    s = sig("No registration fee of $50 applies.")
    assert not firm_true(s, "fees_required")


# ---------- geography: a cue is tied to the country named in its own segment
def geo(text):
    return sig(text)


@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("a,b", [("Residents of Latvia are eligible", "residents of Canada are not eligible"),
                                 ("Residents of Canada are not eligible", "residents of Latvia are eligible"),
                                 ("Residents of Latvia may participate", "residents of Brazil are excluded"),
                                 ("Residents of the United States are not eligible", "Residents of Latvia can participate")])
def test_latvia_included_other_country_excluded_is_not_an_exclusion_of_latvia(how, a, b):
    text = join([a, b], how)
    s = geo(text)
    assert "geo_excludes_participant" not in s, s
    assert decide(text)[0] != INELIGIBLE


@pytest.mark.parametrize("text", ["Residents of Latvia are eligible, residents of Canada are not eligible.",
                                  "Residents of Canada are not eligible, but residents of Latvia are.",
                                  "Latvia is eligible; Canada is not eligible.",
                                  "Latvia: eligible. Canada: not eligible.",
                                  "Eligible: Latvia, Estonia. Not eligible: Canada, Brazil."])
def test_mixed_country_statements_do_not_exclude_latvia_firmly(text):
    s = geo(text)
    assert not (s.get("geo_excludes_participant") and s["geo_excludes_participant"]["strength"] != "weak"), s
    assert decide(text)[0] != INELIGIBLE


@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("text", ["Residents of Latvia are not eligible", "Residents of Canada, Latvia and Brazil are not eligible", "Persons in Latvia may not participate",
                                  "Latvian residents are excluded", "Residents of the EU are not eligible"])
def test_explicit_exclusion_of_the_participant_is_still_a_hard_reject(how, text):
    t = join([text, "Prizes total $5000"], how)
    assert decide(t) == (INELIGIBLE, ["geo_excluded"]), sig(t)


@pytest.mark.parametrize("text", ["Not eligible: residents of Latvia", "Open to the EU, except Latvia", "Everyone is eligible excluding residents of Latvia"])
def test_reordered_or_exception_wording_is_weak_review_not_reject(text):
    s = geo(text)
    assert s.get("geo_excludes_participant", {}).get("strength") == "weak", s
    dec, hard = decide(text)
    assert dec == NEEDS_REVIEW and not hard


# ---------- wallet: mentioning a wallet in a task is not a wallet requirement for participation
@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("text", ["You must submit a video about how to connect a wallet", "Write a tutorial that explains how to connect your wallet",
                                  "Your project should help users connect a wallet", "Describe how users sign transactions in your app"])
def test_wallet_in_task_description_is_not_a_participation_requirement(how, text):
    t = join([text, "Entry is free"], how)
    s = sig(t)
    assert not firm_true(s, "token_or_wallet_required"), s
    assert decide(t)[0] != INELIGIBLE


@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("text", ["You must connect a wallet to participate", "Participants are required to sign transactions on mainnet", "A wallet signature is required to submit",
                                  "You will need to connect your wallet", "Gas fees are required for deployment"])
def test_explicit_wallet_requirement_is_still_firm_and_rejected(how, text):
    t = join([text, "Prizes total $5000"], how)
    assert firm_true(sig(t), "token_or_wallet_required")
    assert decide(t) == (INELIGIBLE, ["wallet_or_token_required"])


def test_wallet_negation_variants():
    for t in ("You do not need to connect a wallet.", "No wallet signature is required.", "Connecting a wallet is not required."):
        s = sig(t)
        assert s.get("token_or_wallet_required", {}).get("value") is not True, t


# ---------- hardware and paid tools: same linkage
@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("text", ["You must submit a video of a robot", "Your project may control a drone", "Write an essay about the Raspberry Pi"])
def test_hardware_named_in_a_task_is_not_a_hardware_requirement(how, text):
    s = sig(join([text, "Entry is free"], how))
    assert not firm_true(s, "hardware_required"), s


@pytest.mark.parametrize("how", SEPARATORS)
@pytest.mark.parametrize("text,kind", [("You must bring a Raspberry Pi", "raspberry_pi"), ("An Arduino board is required", "arduino"), ("Participants need to have a drone", "drone")])
def test_explicit_hardware_requirement_is_still_firm_and_rejected(how, text, kind):
    t = join([text, "Prizes total $5000"], how)
    s = sig(t)
    assert s["hardware_required"]["strength"] == "firm" and kind in s["hardware_required"]["value"]
    assert decide(t) == (INELIGIBLE, ["hardware_unavailable"])


@pytest.mark.parametrize("text", ["You must have a paid subscription to the API", "A paid plan is required", "Participants are required to hold a premium subscription"])
def test_explicit_paid_tool_requirement_is_firm(text):
    assert firm_true(sig(text), "paid_tool_required")


@pytest.mark.parametrize("text", ["You must submit a report comparing paid plan prices", "Describe how a subscription model could work"])
def test_paid_tool_named_in_a_task_is_not_a_requirement(text):
    assert not firm_true(sig(text), "paid_tool_required")


# ---------- visible_text keeps list/paragraph boundaries
def test_html_blocks_become_separate_statements():
    t = detail.visible_text("<ul><li>No registration fee</li><li>Prizes total $5000</li></ul><p>Residents of Latvia are eligible</p><script>x=1</script>")
    assert t.split("\n") == ["No registration fee", "Prizes total $5000", "Residents of Latvia are eligible"]


@pytest.mark.parametrize("how", SEPARATORS)
def test_no_hardware_with_optional_robot_alternative_stays_no_hardware(how):
    s = sig(join(["No hardware is required", "You can build a web app or a robot"], how))
    assert s["hardware_required"]["value"] is False and s["hardware_required"]["strength"] == "firm"
