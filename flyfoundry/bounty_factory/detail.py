"""Detail pass: fetch the public event page (and /rules) and extract *signals*. Page text is untrusted data: it is only
pattern-matched, never interpreted as instructions. Every signal keeps the matching snippet as evidence."""
from __future__ import annotations

import re
from html.parser import HTMLParser

from .model import Opportunity

NEG = re.compile(r"(\bno\b|\bnot\b|\bwithout\b|free of|\bzero\b|n't|\bnever\b|waive)", re.I)


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


FEE = re.compile(r"((registration|entry|participation|application|submission|ticket)\s+fee|pay\s+(a|an|the)?\s*[\w\s]{0,20}fee|"
                 r"\bdeposit\b|\bstake\s+(tokens?|funds)|(buy|purchase|hold)\s+[\w\s]{0,25}tokens?)", re.I)
PAID = re.compile(r"(requires?|must\s+(have|purchase|buy)|need)\s+[\w\s,]{0,40}(paid|premium|subscription|license fee)", re.I)
GEO_EXCL = re.compile(r"(not\s+open\s+to|void\s+in|void\s+where|excluded|ineligible|may\s+not\s+participate|not\s+eligible|"
                      r"residents?\s+of[^.]{0,200}(are\s+not|cannot)|sanctioned)[^.]{0,250}", re.I)
GEO_ANY = re.compile(r"(residents?\s+of|citizens?\s+of|eligible\s+countries|must\s+reside|open\s+to\s+(residents|participants)\s+(of|in)|"
                     r"age\s+of\s+majority|at\s+least\s+(18|19|21)\s+years)[^.]{0,250}", re.I)
EMPLOYER = re.compile(r"\b(merchants?|payment\s+(provider|service\s+provider|processor)s?|PSP|acquirers?|iGaming|chargebacks?|settlement\s+reports?)\b", re.I)
HARDWARE = re.compile(r"\b(raspberry\s*pi|arduino|drone|robot(ic)?s?|vr\s+headset|oculus|quest\s*[23]|physical\s+device|hardware\s+(prototype|required)|"
                      r"iot\s+device|fpga)\b", re.I)
WALLET = re.compile(r"\b(connect\s+(a\s+)?wallet|wallet\s+signature|sign\s+(a\s+)?transaction|mainnet\s+deploy|gas\s+fees?)\b", re.I)
DELIV = {"demo_video": r"\b(demo|pitch|presentation)\s+video\b|\bvideo\b", "public_repository": r"\b(github|gitlab|repository|repo|source\s+code)\b",
         "deployed_app": r"\b(deployed|live\s+demo|hosted|working\s+prototype|url\s+to\s+(your\s+)?(project|app))\b",
         "slides": r"\b(slides?|pitch\s+deck)\b", "written_description": r"\b(text\s+description|project\s+description|write-?up|README)\b"}


def snippet(text: str, m: re.Match, pad: int = 60) -> str:
    return text[max(0, m.start() - pad): m.end() + pad].strip()


def first_unnegated(rx: re.Pattern, text: str):
    for m in rx.finditer(text):
        if not NEG.search(text[max(0, m.start() - 40): m.end() + 5]):
            return m
    return None


def analyse(text: str) -> dict:
    """Pure function: text -> {signal: (value, evidence)}. Absence of a signal means *unknown*, never 'no'."""
    out = {}
    m = first_unnegated(FEE, text)
    if m:
        out["fees_required"] = (True, f"page text: ...{snippet(text, m)}...")
        out["fee_text"] = (snippet(text, m), "page text")
    m = first_unnegated(PAID, text)
    if m:
        out["paid_tool_required"] = (True, f"page text: ...{snippet(text, m)}...")
    m = GEO_EXCL.search(text)
    g = GEO_ANY.search(text)
    if m or g:
        parts = [snippet(text, x, 20) for x in (m, g) if x]
        out["geo_restriction_text"] = (" || ".join(parts)[:600], "page text (excerpt; needs human reading)")
    m = EMPLOYER.search(text)
    if m:
        out["employer_conflict"] = ("keyword:" + m.group(0).lower(), f"page text: ...{snippet(text, m)}...")
    m = HARDWARE.search(text)
    if m:
        out["hardware_required"] = (m.group(0).lower(), f"page text: ...{snippet(text, m)}...")
    m = WALLET.search(text)
    if m:
        out["token_or_wallet_required"] = (True, f"page text: ...{snippet(text, m)}...")
    d = [k for k, rx in DELIV.items() if re.search(rx, text, re.I)]
    if d:
        out["deliverables"] = (d, "keywords present in page text (inferred; confirm in rules)")
    return out


def enrich(o: Opportunity, fetcher, now: str, pages=("", "rules")) -> dict:
    """Fetch public pages for one opportunity (robots-checked). Returns {'pages_ok': n, 'errors': [...]}. Never raises on HTTP errors."""
    texts, errors, ok = [], [], 0
    for suffix in pages:
        url = o.url.rstrip("/") + ("/" + suffix if suffix else "/")
        try:
            status, body = fetcher.get_checked(url, "text/html")
        except Exception as e:  # noqa: BLE001 - robots denial / budget: recorded, not fatal
            errors.append(f"{url}: {type(e).__name__}: {e}")
            break
        if status == 200:
            ok += 1
            texts.append(visible_text(body))
        else:
            errors.append(f"{url}: HTTP {status}")
    if texts:
        text = " ".join(texts)
        for name, (val, ev) in analyse(text).items():
            basis = "inferred" if name in ("deliverables", "employer_conflict", "hardware_required") else "source_claim"
            o.set(name, val, basis, ev)
        o.set("description_text", text[:1500], "source_claim", f"first 1500 chars of visible page text fetched {now}")
        o.detail_fetched_at = now
    return {"pages_ok": ok, "errors": errors}
