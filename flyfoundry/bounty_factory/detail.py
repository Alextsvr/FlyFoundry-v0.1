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

PARSER_VERSION = "detail-5"
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

    BLOCK = {"p", "div", "li", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "section", "article", "dd", "dt", "table", "hr", "blockquote", "pre"}

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK and not self.skip:
            self.parts.append("\n")
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.BLOCK and not self.skip:
            self.parts.append("\n")
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
    t = " ".join(p.parts)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)                      # keep line breaks: list items and paragraphs are separate statements
    return re.sub(r"\s*\n\s*", "\n", t).strip()[:limit]


def sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])|\n+|;\s+|\s[•·]\s", text or "") if s.strip()]


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


def _words(t: str) -> int:
    return len(re.findall(r"[\w$€£%.'-]+", t))


DESCRIBES = re.compile(r"[,;:.]|\b(about|how\s+to|explain\w*|describ\w*|tutorials?|guides?|essays?|blogs?|posts?|write|writing|document\w*|demonstrat\w*|show\w*|present\w*|discuss\w*|review|submit\w*|create|build|prepare|produce|record|upload|compar\w*|analy\w+|research)\b", re.I)
COPULA = re.compile(r"^\s*(?:[\w-]+\s+){0,2}?(?:is|are|be|being|will\s+be|to\s+be)\s*(?:also|always|strictly|absolutely)?\s*$|^\s*$", re.I)


def governs(s: str, m: re.Match, before: int = 5, after: int = 3) -> bool:
    """True only if a requirement cue (must/required/...) DIRECTLY governs the matched item: the cue sits within `before` words in front of it
    with no punctuation or 'describing' word in between ("You must connect a wallet"), or follows it after a bare copula ("A wallet is required").
    "You must submit a video about how to connect a wallet" is NOT governed: the requirement is the video."""
    pre = s[:m.start()]
    last = None
    for r in REQ.finditer(pre):
        last = r
    if last is not None:
        gap = pre[last.end():]
        if _words(gap) <= before and not DESCRIBES.search(gap):
            return True
    r = REQ.search(s, m.end())
    if r is not None:
        gap = s[m.end():r.start()]
        if _words(gap) <= after and COPULA.match(gap) is not None:
            return True
    return False


def negated(s: str, m: re.Match) -> bool:
    """A negation attached to this item: within 30 chars before it (same clause) or right after it ("fee is not required")."""
    pre = re.split(r"[,;:.]", s[max(0, m.start() - 30):m.start()])[-1]
    post = re.split(r"[,;:.]", s[m.end():m.end() + 25])[0]
    return bool(NEG.search(pre) or NEG.search(post))


PRIZE_CTX = re.compile(r"\b(prizes?|pool|awards?|totals?|worth|win(?:ners?|ning)?|grand|cash|rewards?|bount(?:y|ies)|up\s+to|valued)\b", re.I)


def amount_for(s: str, m: re.Match):
    """The money amount attached to THIS fee noun, or None. Attached = directly after it ("fee: $50", "fee of 50 USD", "fee is $50")
    or directly before it ("$50 entry fee"), in the same clause, and not described as a prize/pool/total."""
    for a in AMOUNT.finditer(s):
        if a.start() >= m.end():
            gap = s[m.end():a.start()]
            if len(gap) <= 25 and not re.search(r"[,;.]", gap) and not PRIZE_CTX.search(gap):
                if not PRIZE_CTX.search(s[max(0, a.start() - 12):a.start()]):
                    return a
        elif a.end() <= m.start() and m.start() - a.end() <= 3:
            return a
    return None


NAME_BREAK = re.compile(r"\b(but|while|whereas|however|although|though|and\s+residents)\b|[;.!?]", re.I)


def geo_claim(s: str, P: dict):
    """-> (kind, strength): kind 'excl' | 'incl' | None for the CONFIGURED participant geography in one sentence.
    Each exclusion/inclusion cue owns the segment of text since the previous cue; the participant counts only if named in that segment
    ("Residents of Latvia are eligible, residents of Canada are not eligible" -> Latvia included, no exclusion). A name that only follows a
    cue ("Not eligible: residents of Latvia") is a weaker, reordered claim. EXCEPT wording ("EU except Latvia") is always weak."""
    t = s
    names = []
    for n in _names(P):
        if n:
            for m in re.finditer(r"\b" + re.escape(n) + r"\b", t, re.I):
                names.append((m.start(), m.end()))
    if not names:
        return None, ""
    ex = EXCEPT.search(t)
    if ex is not None:
        if any(st >= ex.end() for st, _ in names):
            return "excl", "weak"
        if EXCL.search(t) is None:
            return "incl", "weak"
    cues = [(m.start(), m.end(), "excl") for m in EXCL.finditer(t)]
    spans = [(a, b) for a, b, _ in cues]
    cues += [(m.start(), m.end(), "incl") for m in INCL.finditer(t) if not any(a <= m.start() < b for a, b in spans)]
    cues.sort()
    prev, found = 0, {}
    for i, (a, b, kind) in enumerate(cues):
        seg0 = max([prev] + [prev + m.end() for m in re.finditer(r"[.!?;]", t[prev:a])])      # a segment never spans a sentence boundary
        if any(seg0 <= st < a for st, _ in names):
            found[kind] = max(found.get(kind, ""), "direct")
        else:
            nxt = cues[i + 1][0] if i + 1 < len(cues) else len(t)
            after = [(st, en) for st, en in names if b <= st < nxt]
            if after and not NAME_BREAK.search(t[b:after[0][0]]) and _words(t[b:after[0][0]]) <= 6:
                found.setdefault(kind, "reordered")
        prev = b
    if "excl" in found:
        return "excl", ("firm" if found["excl"] == "direct" else "weak")
    if "incl" in found:
        return "incl", "weak"
    return None, ""


def analyse(text: str, participant: dict | None = None) -> dict:
    """Pure function: text -> {fact_name: {"value", "evidence", "strength"}}. Absence means unknown, never 'no'."""
    P = participant or DEFAULT_PARTICIPANT
    out = {}
    S = sentences(text)
    ev = lambda s: "page text: " + s[:240]

    # --- wallet / on-chain: a requirement counts as FIRM only if the requirement cue directly governs the wallet action (see governs())
    firm = weak = neg = None
    for s in S:
        for m in WALLET.finditer(s):
            if negated(s, m):
                neg = neg or s
            elif governs(s, m):
                firm = firm or s
            else:
                weak = weak or s            # mentioned (e.g. in a task description) but not provably mandatory for participation
            break
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
            m = re.search(r"\b(?:" + rx + r")\b", s, re.I)
            if not m:
                continue
            if negated(s, m):
                continue
            if kind in WEAK_ONLY_KINDS:
                weak_k.setdefault(kind, s)
            elif governs(s, m):
                (weak_k if ALT.search(s.replace("must", "")) else firm_k).setdefault(kind, s)
            elif not ALT.search(s):
                weak_k.setdefault(kind, s)              # named without a cue tying it to participation; an "or/can/optional" statement is ignored
    if firm_k and not none_s:
        out["hardware_required"] = {"value": sorted(firm_k), "evidence": ev(next(iter(firm_k.values()))), "strength": "firm"}
    elif firm_k or weak_k:
        ks = {**weak_k, **firm_k}
        out["hardware_required"] = {"value": sorted(ks), "evidence": ev(next(iter(ks.values()))) + (" || but also: " + ev(none_s) if none_s else ""), "strength": "weak"}
    elif none_s:
        out["hardware_required"] = {"value": False, "evidence": ev(none_s), "strength": "firm"}

    # --- fees: an amount counts only when it is attached to THIS fee noun (not a prize pool in the same sentence)
    pos_firm = pos_weak = none_claim = None
    for s in S:
        for m in FEE_NOUN.finditer(s):
            amt = amount_for(s, m)
            neg_f = negated(s, m)
            if amt is not None and _num(amt) == 0:
                none_claim = none_claim or s
            elif amt is not None:
                if neg_f:
                    pos_weak = pos_weak or s            # "no fee ... $50": contradictory wording, a human decides
                else:
                    pos_firm = pos_firm or s
            elif neg_f:
                none_claim = none_claim or s
            elif governs(s, m) or re.search(r"\bpay\b", s[max(0, m.start() - 40):m.end() + 40], re.I):
                pos_firm = pos_firm or s
            else:
                pos_weak = pos_weak or s
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
        m = PAID.search(s)
        if m and not negated(s, m):
            if governs(s, m):
                pf = pf or s
            else:
                pw = pw or s
    if pf:
        out["paid_tool_required"] = {"value": True, "evidence": ev(pf), "strength": "firm"}
    elif pw:
        out["paid_tool_required"] = {"value": True, "evidence": ev(pw), "strength": "weak"}

    # --- geography: every inclusion/exclusion cue is tied to the place names in ITS OWN segment (not to the whole sentence)
    excerpts, excl_hit, incl_hit, excl_weak = [], None, None, None
    for s in S:
        if not (GEOWORD.search(s) or EXCL.search(s) or INCL.search(s) or EXCEPT.search(s)):
            continue
        excerpts.append(s[:200])
        if not _mentions(s, P):
            continue
        kind, strength = geo_claim(s, P)
        if kind == "excl":
            if strength == "firm":
                excl_hit = excl_hit or s
            else:
                excl_weak = excl_weak or s
        elif kind == "incl":
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
