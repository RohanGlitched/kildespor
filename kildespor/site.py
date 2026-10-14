"""Crawl a candidate website and decide whether it belongs to the exact legal entity."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from . import siteparse as sp
from .discovery import Candidate, registrable
from .http import Client
from .util import fold, name_tokens, norm_phone

MAX_PAGES = 9


@dataclass
class Proof:
    kind: str  # orgnr | phone | email | name_address | registry_declared
    detail: str
    url: str
    sha256: str
    retrieved_at: str
    strength: float


@dataclass
class SiteResult:
    candidate: Candidate
    status: str  # exact | ambiguous | rejected | unreachable | parked | blocked | other_entity
    reason: str
    home: sp.Page | None = None
    pages: list[sp.Page] = field(default_factory=list)
    proofs: list[Proof] = field(default_factory=list)
    other_orgnrs: list[str] = field(default_factory=list)
    js_shell: bool = False
    later: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return max((p.strength for p in self.proofs), default=0.0)

    @property
    def domain(self) -> str:
        return registrable(self.home.host()) if self.home else self.candidate.domain


async def fetch_page(client: Client, url: str, source: str = "website") -> tuple[sp.Page | None, str]:
    f = await client.get(source, url)
    if f.blocked:
        return None, "blocked:" + f.blocked
    if not f.ok:
        return None, f"http:{f.status or f.error}"
    ct = (f.content_type or "").lower()
    if ct and "html" not in ct and "xml" not in ct and "text/plain" not in ct:
        return None, "not_html"
    page = sp.parse(f.text(), url, f.final_url)
    page.sha256 = f.sha256
    page.retrieved_at = f.retrieved_at
    page.status = f.status
    return page, ""


async def crawl(client: Client, cand: Candidate, budget: float = 60.0) -> SiteResult:
    """Crawl with a hard time budget; a slow host can never hold up a company's research."""
    try:
        return await asyncio.wait_for(_crawl(client, cand), timeout=budget)
    except asyncio.TimeoutError:
        return SiteResult(cand, "unreachable", f"site did not answer within {budget:.0f}s")


async def _crawl(client: Client, cand: Candidate) -> SiteResult:
    home = None
    why = ""
    timeouts = 0
    for url in (f"https://{cand.domain}/", f"https://www.{cand.domain}/", f"http://www.{cand.domain}/", f"http://{cand.domain}/"):
        if cand.domain.startswith("www.") and "www.www." in url:
            continue
        home, why = await fetch_page(client, url)
        if home:
            break
        if why.startswith("blocked:robots"):
            return SiteResult(cand, "blocked", "robots.txt disallows our crawler")
        if "Timeout" in why:
            timeouts += 1
            if timeouts >= 2:
                break  # a host that times out twice is not going to answer the other variants either
        elif why.startswith("http:4") or why.startswith("http:5"):
            break  # the server answered: other variants rarely differ
    if not home:
        return SiteResult(cand, "unreachable", why or "no response")
    res = SiteResult(cand, "ambiguous", "", home=home, pages=[home])
    if sp.parked(home):
        res.status, res.reason = "parked", "parked, empty or placeholder page"
        return res
    final_reg = registrable(home.host())
    if final_reg != registrable(cand.domain) and cand.origin == "name_derived":
        # a guessed domain that forwards elsewhere: treat the destination as the candidate
        res.reason = f"redirects to {final_reg}"
    res.js_shell = len(home.text.split()) < 60 and len(home.links) < 8
    kinds = sp.internal_links(home, home.host())
    first: list[str] = []
    later: list[str] = []
    for kind in ("contact", "about", "privacy", "careers", "news", "people", "locations"):
        for i, (u, _) in enumerate(kinds.get(kind, [])[:2 if kind in ("contact", "about") else 1]):
            if u in first or u in later or u.rstrip("/") == home.final_url.rstrip("/"):
                continue
            (first if kind in ("contact", "about", "privacy") and i == 0 else later).append(u)
    # identity pages first; the rest only once the site is proven to be this entity
    for u in first[:3]:
        page, _ = await fetch_page(client, u)
        if page:
            res.pages.append(page)
    res.later = (first[3:] + later)[: MAX_PAGES - 1 - len(res.pages) + 1]
    return res


async def complete(client: Client, res: SiteResult) -> None:
    """Fetch the remaining priority pages of a verified site for extraction."""
    for u in getattr(res, "later", [])[: MAX_PAGES - len(res.pages)]:
        page, _ = await fetch_page(client, u)
        if page:
            res.pages.append(page)
    res.later = []


FORMS = {"AS": "AS", "ASA": "ASA", "ANS": "ANS", "DA": "DA", "SA": "SA", "BA": "BA", "NUF": "NUF", "STI": "", "ENK": ""}


def _exact_name_rx(name: str) -> re.Pattern | None:
    name = re.sub(r"\s+", " ", (name or "").strip())
    parts = name.split(" ")
    if len(parts) < 2 or parts[-1].upper() not in FORMS or not FORMS[parts[-1].upper()]:
        return None
    core = " ".join(parts[:-1])
    if len(core.replace(" ", "")) < 4:
        return None
    pat = r"(?<![\wæøåÆØÅ])" + r"\s+".join(re.escape(x) for x in parts) + r"(?![\wæøåÆØÅ])"
    return re.compile(pat, re.I)


def _domain_from_name(domain: str, toks: list[str]) -> bool:
    label = fold(domain.split(".")[0]).replace("-", "")
    joined = "".join(toks)
    return bool(label) and len(label) >= 4 and (label == joined or (len(toks) >= 2 and label == "".join(toks[:2])) or
                                              (label in joined and len(label) >= 0.6 * len(joined)))


def _tokens_present(tokens: list[str], hay: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", fold(hay)))
    return bool(tokens) and all(t in words for t in tokens)


def verify(res: SiteResult, ent: dict, subunits: list[dict], orgnr: str) -> SiteResult:
    if res.status in ("unreachable", "parked", "blocked"):
        return res
    sub_orgnrs = {u.get("organisation_number") for u in subunits if u.get("organisation_number")}
    reg_phones = {norm_phone(x) for x in [ent.get("telefon"), ent.get("mobil")] + [u.get("telefon") for u in subunits] +
                  [u.get("mobil") for u in subunits] if x} - {""}
    reg_emails = {x.lower() for x in [ent.get("epostadresse")] + [u.get("epost") for u in subunits] if x}
    toks = [t for t in name_tokens(ent.get("navn", "")) if t not in ("og",)]
    addr = ent.get("forretningsadresse") or {}
    postcodes = {addr.get("postnummer")} | {(u.get("address") or "")[-30:] for u in []}
    postcodes = {p for p in postcodes if p}
    street = fold((addr.get("adresse") or [""])[0]) if addr.get("adresse") else ""

    ours_seen = False
    others: dict[str, str] = {}
    for page in res.pages:
        hay = f"{page.title}\n{page.text}"
        for num, span in sp.orgnr_mentions(hay):
            if num == orgnr or num in sub_orgnrs:
                if not ours_seen:
                    res.proofs.append(Proof("orgnr", span, page.final_url, page.sha256, page.retrieved_at, 1.0))
                ours_seen = True
            elif sp.ORGNR_LABEL_RE.search(span):
                others.setdefault(num, span)
        for d, span in sp.phones(page):
            if d in reg_phones and not any(p.kind == "phone" for p in res.proofs):
                res.proofs.append(Proof("phone", span, page.final_url, page.sha256, page.retrieved_at, 0.96))
        for e in sp.emails(page):
            if e in reg_emails and not any(p.kind == "email" for p in res.proofs):
                res.proofs.append(Proof("email", e, page.final_url, page.sha256, page.retrieved_at, 0.95))
        if not any(p.kind == "name_address" for p in res.proofs) and _tokens_present(toks, hay):
            folded = fold(hay)
            has_post = any(re.search(rf"(?<!\d){pc}(?!\d)", hay) for pc in postcodes)
            has_street = bool(street) and len(street) > 5 and street in folded
            if has_post and has_street:
                res.proofs.append(Proof("name_address", f"{ent.get('navn')} · {street} · {', '.join(postcodes)}",
                                        page.final_url, page.sha256, page.retrieved_at, 0.93))
    # exact legal name with its legal form (e.g. "Fjellform AS") on a site whose domain comes from that name.
    # Names are unique in the register; letters æ/ø/å and punctuation are kept so "RA Service AS" != "RÅ SERVICE AS".
    if not res.proofs and not others:
        legal = _exact_name_rx(ent.get("navn", ""))
        label_ok = res.candidate.declared or _domain_from_name(res.domain, toks)
        if legal and label_ok:
            for page in res.pages:
                for hay in (page.site_name, page.title, page.text):
                    m = legal.search(hay or "")
                    if m:
                        span = (hay or "")[max(0, m.start() - 50): m.end() + 30].replace("\n", " ")
                        res.proofs.append(Proof("legal_name", span, page.final_url, page.sha256, page.retrieved_at, 0.9))
                        break
                if res.proofs:
                    break
    res.other_orgnrs = sorted(others)
    if others and not ours_seen:
        # the site names a different legal entity as its operator
        res.status = "other_entity"
        res.reason = "site states organisation number " + ", ".join(sorted(others)[:3])
        return res
    if res.proofs:
        res.status = "exact"
        res.reason = "; ".join(sorted({p.kind for p in res.proofs}))
        return res
    if res.candidate.origin in ("registry_website", "wikidata_website"):
        name_seen = any(_tokens_present(toks, f"{p.title} {p.site_name} {p.text[:20000]}") for p in res.pages)
        same_host = registrable(res.home.host()) == registrable(res.candidate.domain) if res.home else False
        if same_host or name_seen:
            res.proofs.append(Proof("registry_declared", f"hjemmeside: {res.candidate.detail}", res.home.final_url,
                                    res.home.sha256, res.home.retrieved_at, 0.9 if name_seen else 0.85))
            res.status = "exact"
            res.reason = "declared in the register" + (" and the legal name appears on the site" if name_seen else "")
            return res
    if res.candidate.origin in ("registry_email", "subunit_website", "subunit_email", "job_ad_homepage"):
        name_seen = any(_tokens_present(toks, f"{p.title} {p.site_name} {p.text[:20000]}") for p in res.pages)
        if name_seen and registrable(res.home.host()) == registrable(res.candidate.domain):
            res.proofs.append(Proof("registry_declared", f"registered e-mail domain {res.candidate.detail}; legal name on site",
                                    res.home.final_url, res.home.sha256, res.home.retrieved_at, 0.9))
            res.status = "exact"
            res.reason = "register e-mail domain and legal name on the site"
            return res
    res.status = "ambiguous"
    res.reason = res.reason or "no organisation number, registered phone, e-mail or address on the site"
    return res


def site_host(res: SiteResult) -> str:
    return (urlsplit(res.home.final_url).hostname or "") if res.home else ""
