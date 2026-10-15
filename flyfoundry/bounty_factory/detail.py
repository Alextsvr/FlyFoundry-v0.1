"""Detail pass: read the public overview and /rules pages and extract *signals*. Page text is untrusted data: it is only
pattern-matched sentence by sentence, never interpreted as instructions.

Each signal is `{"value", "evidence", "strength"}`. strength=firm needs an explicit requirement wording in the same sentence;
strength=weak is only a prompt for human review and can never cause a hard reject. Mentions, negations ("you do not need a
wallet"), zero amounts ("fee: $0") and alternatives ("or a robot") are not requirements. Absence of a signal = unknown."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from html.parser import HTMLParser

from .model import Opportunity, Fact, sha256_text

PARSER_VERSION = "detail-4"
WEAK_ONLY_KINDS = {"gpu"}     # GPUs are often provided as cloud credits: mention of a GPU only ever prompts a human read
PAGES = ("overview", "rules")
DEFAULT_PARTICIPANT = {"country_code": "LV", "country_names": ["latvia", "latvian"], "region_names": ["european union", "eu", "europe", "baltic", "baltics", "eea"]}
HARDWARE_KINDS = {
    "raspberry_pi": r"raspberry\s*pi", "arduino": r"arduino", "drone": r"drones?", "robot": r"robot(?:ic)?s?", "vr_headset": r"vr\s+headsets?|oculus|quest\s*[23]",
    "fpga": r"fpga", "gpu": r"gpus?|cuda", "iot_device": r"iot\s+devices?", "physical_device": r"physical\s+device|hardware\s+prototype",
}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def visible_text(html_text: str, limit: int = 60000) -> str:
    p = _Text()
    try:
        p.feed(html_text)
    except Exception:  # noqa: BLE001
        pass
    return re.sub(r"\s+", " ", " ".join(p.parts))[:limit]


def sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])|\n+", text or "") if s.strip()]


NEG = re.compile(r"\b(no|not|without|never|neither|nor|free of|waived?|don'?t|doesn'?t|isn'?t|aren'?t|won'?t)\b|n't", re.I)
REQ = re.compile(r"\b(must|required|requires?|need(?:s)? to|mandatory|you will need|have to|obligatory)\b", re.I)
ALT = re.compile(r"\b(or|either|alternatively|optional|optionally|can|may|could|choose|instead|one of)\b", re.I)
WALLET = re.compile(r"\b(connect(?:ing)?\s+(?:a\s+|your\s+)?wallet|wallet\s+signature|sign\s+(?:a\s+)?transactions?|mainnet\s+deploy\w*|gas\s+fees?)\b", re.I)
FEE_NOUN = re.compile(r"\b(?:(?:registration|entry|participation|application|submission|ticket|team)\s+fees?|deposits?|stake\s+(?:tokens?|funds)|(?:buy|purchase|hold)\s+[\w\s]{0,25}tokens?)\b", re.I)
AMOUNT = re.compile(r"(?:[$€£]\s?|(?:usd|eur|gbp)\s?)(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?(?:usd|eur|gbp|dollars?|euros?)", re.I)
PAID = re.compile(r"\b(paid\s+(?:plan|tier|api|subscription|license)|premium\s+(?:plan|subscription)|subscription|license\s+fee)\b", re.I)
NO_HW = re.compile(r"\bno\s+(?:special\s+|specific\s+|physical\s+)?hardware\b|\bhardware\s+(?:is|are)\s+not\s+required\b", re.I)
EXCL = re.compile(r"\b(not\s+eligible|ineligible|not\s+open\s+to|excluded|void\s+in|void\s+where|may\s+not\s+(?:participate|enter)|cannot\s+participate|not\s+permitted|are\s+prohibited)\b", re.I)
INCL = re.compile(r"\b(eligible|open\s+to|may\s+participate|can\s+participate|welcome)\b", re.I)
GEOWORD = re.compile(r"\b(residents?|citizens?|countr(?:y|ies)|region|jurisdiction|worldwide|globally|age\s+of\s+majority|at\s+least\s+\d+\s+years)\b", re.I)
EXCEPT = re.compile(r"\b(except|other\s+than|excluding|besides|apart\s+from)\b", re.I)
EMPLOYER = re.compile(r"\b(merchants?|payment\s+(?:provider|service\s+provider|processor)s?|PSP|acquirers?|iGaming|chargebacks?|settlement\s+reports?)\b", re.I)
DELIV = {"demo_video": r"\b(?:demo|pitch|presentation)\s+video\b|\bvideo\b", "public_repository": r"\b(?:github|gitlab|repository|repo|source\s+code)\b",
         "deployed_app": r"\b(?:deployed|live\s+demo|hosted|working\s+prototype|url\s+to\s+(?:your\s+)?(?:project|app))\b",
         "slides": r"\b(?:slides?|pitch\s+deck)\b", "written_description": r"\b(?:text\s+description|project\s+description|write-?up|README)\b"}


def _names(participant: dict) -> list:
    return [n.lower() for n in participant.get("country_names", []) + participant.get("region_names", [])] + [participant.get("country_code", "").lower()]


def _mentions(sentence: str, participant: dict) -> bool:
    t = sentence.lower()
    return any(n and re.search(r"\b" + re.escape(n) + r"\b", t) for n in _names(participant))


def _num(m: re.Match) -> float:
    return float((m.group(1) or m.group(2)).replace(",", ""))


def analyse(text: str, participant: dict | None = None) -> dict:
    """Pure function: text -> {fact_name: {"value", "evidence", "strength"}}. Absence means unknown, never 'no'."""
    P = participant or DEFAULT_PARTICIPANT
    out = {}
    S = sentences(text)
    ev = lambda s: "page text: " + s[:240]

    # --- wallet / on-chain
    firm = weak = neg = None
    for s in S:
        if WALLET.search(s):
            if NEG.search(s):
                neg = neg or s
            elif REQ.search(s):
                firm = firm or s
            else:
                weak = weak or s
    if firm and neg:
        out["token_or_wallet_required"] = {"value": True, "evidence": ev(firm) + " || contradicted by: " + ev(neg), "strength": "weak"}
    elif firm:
        out["token_or_wallet_required"] = {"value": True, "evidence": ev(firm), "strength": "firm"}
    elif weak:
        out["token_or_wallet_required"] = {"value": True, "evidence": ev(weak), "strength": "weak"}
    elif neg:
        out["token_or_wallet_required"] = {"value": False, "evidence": ev(neg), "strength": "firm"}

    # --- hardware
    none_s = next((s for s in S if NO_HW.search(s)), None)
    firm_k, weak_k = {}, {}
    for s in S:
        if NO_HW.search(s):
            continue
        for kind, rx in HARDWARE_KINDS.items():
            if re.search(r"\b(?:" + rx + r")\b", s, re.I):
                if NEG.search(s):
                    continue
                if kind in WEAK_ONLY_KINDS:
                    weak_k.setdefault(kind, s)
                elif REQ.search(s) and not ALT.search(s.replace("must", "")):
                    firm_k.setdefault(kind, s)
                elif REQ.search(s):
                    weak_k.setdefault(kind, s)
                elif not ALT.search(s):
                    weak_k.setdefault(kind, s)
    if firm_k and not none_s:
        out["hardware_required"] = {"value": sorted(firm_k), "evidence": ev(next(iter(firm_k.values()))), "strength": "firm"}
    elif firm_k or weak_k:
        ks = {**weak_k, **firm_k}
        out["hardware_required"] = {"value": sorted(ks), "evidence": ev(next(iter(ks.values()))) + (" || but also: " + ev(none_s) if none_s else ""), "strength": "weak"}
    elif none_s:
        out["hardware_required"] = {"value": False, "evidence": ev(none_s), "strength": "firm"}

    # --- fees (amount-aware; a zero amount or a negation is an explicit "no fee")
    pos_firm = pos_weak = none_claim = None
    for s in S:
        for m in FEE_NOUN.finditer(s):
            amt = AMOUNT.search(s)
            if amt:
                if _num(amt) == 0:
                    none_claim = none_claim or s
                else:
                    pos_firm = pos_firm or s
            elif NEG.search(s):
                none_claim = none_claim or s
            elif REQ.search(s) or re.search(r"\bpay\b", s, re.I):
                pos_firm = pos_firm or s
            else:
                pos_weak = pos_weak or s
            break
    if pos_firm:
        out["fees_required"] = {"value": True, "evidence": ev(pos_firm), "strength": "firm"}
        out["fee_text"] = {"value": pos_firm[:240], "evidence": "page text", "strength": "firm"}
    elif pos_weak:
        out["fees_required"] = {"value": True, "evidence": ev(pos_weak), "strength": "weak"}
        out["fee_text"] = {"value": pos_weak[:240], "evidence": "page text", "strength": "weak"}
    elif none_claim:
        out["fees_required"] = {"value": False, "evidence": ev(none_claim), "strength": "firm"}

    # --- paid tools
    pf = pw = None
    for s in S:
        if PAID.search(s) and not NEG.search(s):
            if REQ.search(s):
                pf = pf or s
            else:
                pw = pw or s
    if pf:
        out["paid_tool_required"] = {"value": True, "evidence": ev(pf), "strength": "firm"}
    elif pw:
        out["paid_tool_required"] = {"value": True, "evidence": ev(pw), "strength": "weak"}

    # --- geography (sentence level; inclusion and exclusion are separate claims)
    excerpts, excl_hit, incl_hit, excl_weak = [], None, None, None
    for s in S:
        if not GEOWORD.search(s) and not EXCL.search(s):
            continue
        is_excl, is_incl = bool(EXCL.search(s)), bool(INCL.search(s)) and not EXCL.search(s)
        if not (is_excl or is_incl) and not GEOWORD.search(s):
            continue
        excerpts.append(s[:200])
        if _mentions(s, P):
            if is_excl:
                if EXCEPT.search(s):
                    excl_weak = excl_weak or s
                else:
                    excl_hit = excl_hit or s
            elif is_incl:
                if EXCEPT.search(s):
                    excl_weak = excl_weak or s      # "open to the EU, except Latvia": ambiguous, needs a human
                else:
                    incl_hit = incl_hit or s
    if excerpts:
        out["geo_restriction_text"] = {"value": " || ".join(excerpts)[:600], "evidence": "page text excerpts (need a human read)", "strength": "weak"}
    if excl_hit:
        out["geo_excludes_participant"] = {"value": True, "evidence": ev(excl_hit), "strength": "firm"}
    elif excl_weak:
        out["geo_excludes_participant"] = {"value": True, "evidence": ev(excl_weak), "strength": "weak"}
    if incl_hit:
        out["geo_includes_participant"] = {"value": True, "evidence": ev(incl_hit), "strength": "weak"}

    m = next((x for x in (EMPLOYER.search(s) for s in S) if x), None)
    if m:
        out["employer_conflict"] = {"value": "keyword:" + m.group(0).lower(), "evidence": "page text keyword", "strength": "weak"}
    d = [k for k, rx in DELIV.items() if re.search(rx, text or "", re.I)]
    if d:
        out["deliverables"] = {"value": d, "evidence": "keywords present in page text (inferred; confirm in rules)", "strength": "weak"}
    return out


def _basis(name: str) -> str:
    return "inferred" if name in ("deliverables", "employer_conflict", "geo_includes_participant") else "source_claim"


def due(state: dict | None, now: datetime) -> bool:
    """Per-page recheck policy: ok/404 -> 7 days, 401/403 -> 3 days (no more than one attempt per run, never bypassed), transient (0/5xx) -> next run."""
    if not state:
        return True
    nd = state.get("next_due")
    try:
        return datetime.fromisoformat(nd.replace("Z", "+00:00")) <= now
    except (ValueError, AttributeError):
        return True


def next_due(status: int, now: datetime) -> str:
    days = 7 if status in (200, 404, 410) else (3 if status in (401, 403) else 0)
    return (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_detail(store, o: Opportunity, fetcher, run_id: int, now: datetime, participant: dict | None = None) -> dict:
    """Read the due pages of one opportunity. Raw responses (any status) are stored as observations; facts link to the
    observation they came from. Returns a summary; never raises on HTTP errors; robots/host blocks stop the pass (not bypassed)."""
    from .http import BudgetExceeded, HostBlocked, RobotsDenied
    now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    res = {"attempted": 0, "ok": 0, "failed": [], "blocked": False}
    per_page, refreshed = {}, set()
    for page in PAGES:
        if not due(o.detail.get(page), now):
            continue
        url = o.url.rstrip("/") + ("/" if page == "overview" else "/rules")
        try:
            status, body = fetcher.get_checked(url, "text/html")
        except (RobotsDenied, HostBlocked) as e:
            res["blocked"] = True
            res["failed"].append(f"{url}: {type(e).__name__}")
            break
        except BudgetExceeded as e:
            res["failed"].append(str(e))
            break
        res["attempted"] += 1
        obs = store.add_observation(run_id, o.source, o.id, url, now_s, body if status == 200 else (body or "")[:2000], kind=page, http_status=status, parser_version=PARSER_VERSION)
        store.set_detail_state(o.id, page, {"fetched_at": now_s, "http_status": status, "ok": status == 200, "observation_id": obs, "next_due": next_due(status, now)}, now_s)
        if status in (401, 403):
            res["blocked"] = True
        if status != 200:
            res["failed"].append(f"{url}: HTTP {status}")
            continue
        res["ok"] += 1
        text = visible_text(body)
        refreshed.add(page)
        per_page[page] = {"obs": obs, "signals": analyse(text, participant), "text": text}
    if not refreshed:
        return res
    facts = {}
    for page in ("overview", "rules"):            # rules wins over overview; firm wins over weak
        if page not in per_page:
            continue
        for name, sg in per_page[page]["signals"].items():
            cur = facts.get(name)
            if cur is None or page == "rules" or (cur.strength == "weak" and sg["strength"] == "firm"):
                facts[name] = Fact(sg["value"], _basis(name), sg["evidence"], sg["strength"], page, "", "", per_page[page]["obs"], PARSER_VERSION)
    if "overview" in per_page:
        facts["description_text"] = Fact(per_page["overview"]["text"][:1500], "source_claim", f"first 1500 chars of visible overview text fetched {now_s}", "", "overview", "", "", per_page["overview"]["obs"], PARSER_VERSION)
    if "rules" in per_page:
        facts["rules_hash"] = Fact(sha256_text(per_page["rules"]["text"]), "source_claim", "sha256 of visible rules-page text", "", "rules", "", "", per_page["rules"]["obs"], PARSER_VERSION)
    store.apply_facts(o.id, facts, refreshed, now_s)
    return res
