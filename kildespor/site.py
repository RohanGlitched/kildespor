"""Crawl a candidate website and decide whether it belongs to the exact legal entity."""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from . import siteparse as sp
from .discovery import Candidate, registrable
from .http import Client
from .util import LEGAL_FORMS, fold, name_tokens, norm_phone, split_words

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


async def fetch_page(client: Client, url: str, source: str = "website", retries: int = 0) -> tuple[sp.Page | None, str]:
    f = await client.get(source, url)
    for _ in range(retries):  # only a rate limit is worth waiting for; a timeout or an error is not retried here
        if f.status != 429:
            break
        await asyncio.sleep(6.0)
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
        home, why = await fetch_page(client, url, retries=1)  # a 429 is retried once after a pause
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
    if len(home.text.split()) < 15 and (home.scripts or home.script_text):
        # a page drawn in the browser: read its page data and a couple of its own bundles, within a small budget
        try:
            await asyncio.wait_for(add_script_pages(client, res), timeout=12)
        except asyncio.TimeoutError:
            pass
    kinds = sp.internal_links(home, home.host())
    first: list[str] = []
    later: list[str] = []
    for kind in ("contact", "about", "privacy", "careers", "news", "people", "locations"):
        for i, (u, _) in enumerate(kinds.get(kind, [])[:2 if kind in ("contact", "about") else 1]):
            if u in first or u in later or u.rstrip("/") == home.final_url.rstrip("/"):
                continue
            (first if kind in ("contact", "about", "privacy") and (i == 0 or kind == "privacy") else later).append(u)
    # identity pages first; the rest only once the site is proven to be this entity
    for u in first[:4]:
        page, _ = await fetch_page(client, u)
        if page:
            res.pages.append(page)
    res.later = (first[3:] + later)[: MAX_PAGES - 1 - len(res.pages) + 1]
    return res


SCRIPT_HINT = re.compile(r"(main|app|index|page|layout|_app|bundle|site|footer|contact|kontakt)", re.I)
SCRIPT_SKIP = re.compile(r"(vendor|polyfill|runtime|framework|react|jquery|analytics|gtm|gtag|tag-?manager|cookie|consent|"
                         r"recaptcha|sentry|hotjar|webpack|swiper|slick|lodash|moment|three|chart|map)", re.I)
BUNDLE_SLOTS = asyncio.Semaphore(6)  # run-wide: bundle downloads never crowd out ordinary page fetches


async def add_script_pages(client: Client, res: SiteResult, limit: int = 2) -> None:
    """A site drawn in the browser keeps its text (footer, contact block, org.nr) in page data and script
    bundles. Their readable strings join the crawl as extra pages so the same identity rules can read them;
    each is a fetched, hashed, archived response like any other page."""
    home = res.home
    if home.script_text:
        data = sp.Page(url=home.url, final_url=home.final_url, title=home.title, text=home.script_text, site_name=home.site_name)
        data.sha256, data.retrieved_at, data.status, data.generator = home.sha256, home.retrieved_at, home.status, "page-data"
        res.pages.append(data)
    picks = sorted((u for u in home.scripts if not SCRIPT_SKIP.search(u.rsplit("/", 1)[-1])),
                   key=lambda u: (not SCRIPT_HINT.search(u.rsplit("/", 1)[-1]), len(u)))[:limit]
    for u in picks:
        async with BUNDLE_SLOTS:
            f = await client.get("website", u, max_body=1_200_000)
        if not f.ok or f.blocked:
            continue
        text = sp.js_text(f.text())
        if len(text) < 40:
            continue
        page = sp.Page(url=u, final_url=f.final_url, title=home.title, text=text[:300_000], site_name=home.site_name)
        page.sha256, page.retrieved_at, page.status, page.generator = f.sha256, f.retrieved_at, f.status, "script-bundle"
        res.pages.append(page)


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
    # the name is case-insensitive, the legal form is not: "Nemitek as part of" must not read as "NEMITEK AS"
    pat = (r"(?<![\wæøåÆØÅ])" + r"\s+".join("(?i:" + re.escape(x) + ")" for x in parts[:-1]) + r"\s+" +
           re.escape(parts[-1].upper()) + r"(?![\wæøåÆØÅ])")
    return re.compile(pat)


def _domain_from_name(domain: str, toks: list[str]) -> bool:
    label = fold(domain.split(".")[0]).replace("-", "")
    joined = "".join(toks)
    prefixes = {"".join(toks[:k]) for k in range(1, len(toks) + 1)}
    return bool(label) and len(label) >= 4 and (label == joined or (len(toks) >= 2 and label == "".join(toks[:2])) or
                                              (label in joined and len(label) >= 0.6 * len(joined)) or
                                              (label in prefixes and len(label) >= 6))


def _tokens_present(tokens: list[str], hay: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", fold(hay)))
    return bool(tokens) and all(t in words for t in tokens)


MINOR = {"og", "i", "pa", "av", "for", "the", "and"}


def _jsonld_names(page: sp.Page) -> list[str]:
    out = []
    for node in page.jsonld:
        kind = str(node.get("@type", ""))
        if any(k in kind for k in ("Organization", "Corporation", "LocalBusiness", "WebSite", "Store", "Restaurant")):
            for key in ("name", "legalName", "alternateName"):
                v = node.get(key)
                if isinstance(v, str):
                    out.append(v)
    return out


FOREIGN_FORMS = {"inc", "llc", "ltd", "limited", "gmbh", "aps", "oy", "oyj", "bv", "nv", "srl", "sarl", "plc", "corp",
                 "corporation", "pty", "kft", "ag", "sas", "lda", "spa"}


def foreign_entity(value: str) -> bool:
    """A title or name that carries a foreign company form ("Kriss Consulting Inc") names another legal entity."""
    return bool(set(re.findall(r"[a-z]+", fold(value or ""))) & FOREIGN_FORMS)


def declared_name_proof(home: sp.Page, ent: dict) -> str:
    """The text that names the entity on a declared site's home page (quoted as the evidence span), or "".

    Every distinctive legal-name token must appear together in one identity field. A one-word name needs at
    least five letters, a home page with real content, and the word in the title, site name or host name."""
    core = [t for t in name_tokens(ent.get("navn", "")) if t not in MINOR]
    if not core:
        return ""
    host_label = (home.host() or "").removeprefix("www.").rsplit(".", 1)[0]
    fields = [("title", home.title), ("site name", home.site_name), ("description", home.description),
              *[("JSON-LD name", n) for n in _jsonld_names(home)], ("host name", host_label.replace("-", " ").replace(".", " "))]
    for label, value in fields:
        words = set(re.findall(r"[a-z0-9]+", fold(value or "")))
        if not words or foreign_entity(value):
            continue
        if len(core) >= 2 and all(t in words for t in core):
            return sp_clip(value)
        if len(core) == 1 and len(core[0]) >= 5 and core[0] in words and label in ("title", "site name", "host name") \
                and len(home.text) >= 300:
            return sp_clip(value)
    return ""


def full_name_label(res: "SiteResult", toks: list[str]) -> bool:
    core = [t for t in toks if t not in MINOR]
    joined = "".join(core)
    host = res.home.host() if res.home else res.candidate.domain
    return len(joined) >= 6 and fold(registrable(host).split(".")[0]).replace("-", "") == joined


def full_name_domain_proof(res: "SiteResult", ent: dict) -> str:
    """For a guessed domain: the home-page text naming the company, or "" (see verify)."""
    core = [t for t in name_tokens(ent.get("navn", "")) if t not in MINOR]
    joined = "".join(core)
    label = fold(registrable(res.home.host()).split(".")[0]).replace("-", "")
    if not core or label != joined or len(joined) < 8 or (len(core) == 1 and len(joined) < 10):
        return ""
    named = ""
    for value in (res.home.title, res.home.site_name, *_jsonld_names(res.home)):
        if foreign_entity(value):
            continue
        words = set(re.findall(r"[a-z0-9]+", fold(value or "")))
        squashed = re.sub(r"[^a-z0-9]", "", fold(value or ""))
        if all(t in words for t in core) or (len(core) >= 2 and joined in squashed):
            named = value
            break
    if not named:
        return ""
    addr = ent.get("forretningsadresse") or ent.get("postadresse") or {}
    postcode = addr.get("postnummer") or ""
    # a town that is itself part of the name proves nothing ("Sandnes Elektriske" in Sandnes): the postcode must
    towns = [t for t in (fold(x) for x in (addr.get("poststed"), addr.get("kommune")) if x) if not set(t.split()) & set(core)]
    text = fold(" ".join(f"{p.title} {p.text}" for p in res.pages))
    words = set(re.findall(r"[a-z0-9]+", text))
    if (postcode and re.search(rf"(?<!\d){postcode}(?!\d)", text)) or any(all(w in words for w in t.split()) for t in towns):
        return sp_clip(named)
    return ""


STRONG_PROOFS = {"orgnr", "phone", "email", "name_address", "name_street", "registry_declared_name"}
NOT_PLACES = {"email", "epost", "mail", "telefon", "fax", "mobil", "kr", "nok", "eur", "usd", "kontakt", "web", "www", "the",
              "and", "og", "for", "til", "fra", "med", "kunder", "ansatte", "medlemmer", "timer", "kvm", "meter", "liter",
              "stk", "personer", "studenter", "elever", "barn", "dager", "uker", "januar", "februar", "mars", "april", "mai",
              "juni", "juli", "august", "september", "oktober", "november", "desember", "copyright", "alle", "all"}
POSTPLACE = re.compile(r"(?<!\d)(\d{4})\s+([A-ZÆØÅ][A-Za-zÆØÅæøå\-]{2,})")
HOSTED_PLATFORMS = re.compile(r"\.(wixsite\.com|weebly\.com|blogspot\.com|wordpress\.com|squarespace\.com|webflow\.io|godaddysites\.com|"
                              r"jimdofree\.com|jimdosite\.com|mystrikingly\.com|business\.site|simplesite\.com|sites\.google\.com|"
                              r"carrd\.co|123hjemmeside\.no|hjemmeside\.no)$")


def place_conflict(res: "SiteResult", ent: dict, subunits: list[dict]) -> str:
    """A Norwegian postcode and town on the site that is none of ours (registered address, postal address or a
    registered workplace), when the site never shows one of ours: the site is somebody else's ("5911 Alversund"
    on dekkhuset.no for DEKK HUSET AS of Oppaker). Returns the first such place, or ""."""
    pcs, towns = set(), set()
    for a in (ent.get("forretningsadresse") or {}, ent.get("postadresse") or {}):
        if a.get("postnummer"):
            pcs.add(a["postnummer"])
        towns |= {fold(a[k]) for k in ("poststed", "kommune") if a.get(k)}
    for u in subunits:
        address = u.get("address") or ""
        pcs |= set(re.findall(r"(?<!\d)\d{4}(?!\d)", address))
        tail = re.sub(r"^\s*\d{4}\s*", "", address.split(",")[-1]).strip()
        towns |= {fold(x) for x in (tail, u.get("municipality")) if x}
    first_words = {t.split()[0] for t in towns if t}
    foreign = ""
    for page in res.pages[:8]:
        if page.generator == "script-bundle":
            continue
        for pc, town in POSTPLACE.findall(f"{page.text}\n{page.title}"):
            if 1950 <= int(pc) <= 2030:
                continue  # years ("2024 Oslo") look like postcodes
            t = fold(town)
            if t in NOT_PLACES or t.startswith(("e-", "tlf", "tel", "mob", "org", "post")):
                continue  # "3114 E-mail", "1234 Telefon": a number before a label, not a postcode and town
            if pc in pcs or t in towns or t in first_words:
                return ""
            foreign = foreign or f"{pc} {town}"
    return foreign


def sp_clip(value: str, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def verify(res: SiteResult, ent: dict, subunits: list[dict], orgnr: str, people: list[dict] | None = None) -> SiteResult:
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
    streets = [fold(x) for x in (addr.get("adresse") or []) if x and not fold(x).startswith(("c/o", "co ", "c /o"))]
    streets = [x for x in streets if len(x) > 5 and re.search(r"\d", x)] or [x for x in streets if len(x) > 5]
    street = streets[0] if streets else ""

    ours_seen = False
    others: dict[str, str] = {}
    for page in res.pages:
        hay = f"{page.title}\n{page.text}"
        for num, span in sp.orgnr_mentions(hay):
            if num == orgnr or num in sub_orgnrs:
                if not ours_seen:
                    if page.generator in ("script-bundle", "page-data"):
                        # quote only the line that carries the number: it occurs verbatim in the archived script
                        digits9 = re.compile(r"\D*".join(num))
                        span = next((ln.strip() for ln in page.text.splitlines() if digits9.search(ln)), span)
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
            has_street = any(st in folded for st in streets)
            if has_post and has_street:
                res.proofs.append(Proof("name_address", f"{ent.get('navn')} · {street} · {', '.join(postcodes)}",
                                        page.final_url, page.sha256, page.retrieved_at, 0.93))
            elif has_street and re.search(r"\d", street) and (res.candidate.declared or full_name_label(res, toks)):
                # the registered street line with its house number, without the postcode, on a site whose domain
                # spells the whole name or that the entity declared ("Torpebaugen 4" on norsktrafoservice.com)
                res.proofs.append(Proof("name_street", f"{ent.get('navn')} · {street}",
                                        page.final_url, page.sha256, page.retrieved_at, 0.92))
    # exact legal name with its legal form (e.g. "Fjellform AS") on a site whose domain comes from that name.
    # Names are unique in the register; letters æ/ø/å and punctuation are kept so "RA Service AS" != "RÅ SERVICE AS".
    if not res.proofs and not others:
        legal = _exact_name_rx(ent.get("navn", ""))
        label_ok = res.candidate.declared or _domain_from_name(res.domain, toks)
        place_words = {fold(x) for x in (addr.get("poststed"), addr.get("kommune")) if x}
        if legal and label_ok:
            all_text = fold(" ".join(f"{p.title} {p.text}" for p in res.pages))
            words_all = set(re.findall(r"[a-z0-9]+", all_text))
            place_ok = any(re.search(rf"(?<!\d){pc}(?!\d)", all_text) for pc in postcodes) or \
                any(all(w in words_all for w in t.split()) for t in place_words)
            for page in (res.pages if place_ok else []):
                for hay in (page.site_name, page.title, page.text):
                    m = legal.search(hay or "")
                    if m:
                        span = (hay or "")[max(0, m.start() - 50): m.end() + 30].replace("\n", " ")
                        res.proofs.append(Proof("legal_name", span, page.final_url, page.sha256, page.retrieved_at, 0.9))
                        break
                if res.proofs:
                    break
    if not res.proofs and not others:
        label_ok = res.candidate.declared or _domain_from_name(res.domain, toks)
        form = ((ent.get("organisasjonsform") or {}).get("kode") or "").upper()
        town_words = {fold(x) for x in (addr.get("poststed"), addr.get("kommune")) if x}
        # housing co-ops, foundations and other forms without "AS" in the name: the exact full name plus the registered town
        if label_ok and form not in FORMS and len(toks) >= 2:
            full = re.compile(r"(?<![\wæøåÆØÅ])" + r"\s+".join(re.escape(x) for x in ent.get("navn", "").split()) + r"(?![\wæøåÆØÅ])", re.I)
            for page in res.pages:
                hay = "\n".join((page.site_name, page.title, page.text))
                m = full.search(hay)
                words = set(re.findall(r"[a-z0-9]+", fold(hay)))
                if m and any(all(w in words for w in t.split()) for t in town_words):
                    res.proofs.append(Proof("legal_name_town", hay[max(0, m.start() - 40): m.end() + 40].replace("\n", " "),
                                            page.final_url, page.sha256, page.retrieved_at, 0.9))
                    break
        # a current role holder from the role register named on the site, plus every legal-name token
        persons = [x["name"] for x in (people or []) if x.get("kind") == "person" and len(x.get("name", "").split()) >= 2]
        # a company named after a person ("STIAN SÆTHER AS"): the person's own sites and sole proprietorship carry
        # the same words, so naming the role holder proves nothing
        named_after = any(set(re.findall(r"[a-z0-9]+", fold(n))) == set(toks) for n in persons)
        if not res.proofs and persons and not named_after:
            for page in res.pages:
                hay = "\n".join((page.title, page.site_name, page.text))
                if not _tokens_present(toks, hay):
                    continue
                f_hay = " " + " ".join(re.findall(r"[a-z0-9]+", fold(hay))) + " "
                hits = []
                for name in persons:
                    parts = re.findall(r"[a-z0-9]+", fold(name))
                    if person_named(parts, f_hay):
                        hits.append(name)
                if hits:
                    first = re.findall(r"[a-zæøå0-9]+", hits[0].lower())
                    m = re.search(r"\b" + re.escape(first[0]) + r"\b.{0,40}" + re.escape(first[-1]), hay, re.I | re.S)
                    excerpt = hay[max(0, m.start() - 40): m.end() + 40].replace("\n", " ") if m else hits[0]
                    res.proofs.append(Proof("role_holder_and_name", excerpt,
                                            page.final_url, page.sha256, page.retrieved_at, 0.9 if len(hits) >= 2 else 0.88))
                    break
    # A website the entity itself declared in the register whose home page identifies it by its whole legal name
    # (title, site name, description, Organization JSON-LD or host name) — the rule of Builderr's own identity
    # gate. Kept stricter: the other-entity and sibling checks still apply, and co-ops still need the number.
    if not res.proofs and res.candidate.origin in ("registry_website", "subunit_website") and res.home:
        proof = declared_name_proof(res.home, ent)
        if proof:
            res.proofs.append(Proof("registry_declared_name", proof, res.home.final_url, res.home.sha256,
                                    res.home.retrieved_at, 0.9))
    # A guessed domain that spells the whole name, whose home page names the company in full, on a site that
    # also states the registered town or postcode. Namesakes elsewhere fail the town; sister companies fail the
    # sibling check that follows; co-ops still need their number.
    if not res.proofs and res.candidate.origin == "name_derived" and res.home:
        proof = full_name_domain_proof(res, ent)
        if proof:
            res.proofs.append(Proof("name_domain_town", proof, res.home.final_url, res.home.sha256,
                                    res.home.retrieved_at, 0.9))
    if not ours_seen:
        own = re.sub(r"[^a-z0-9 ]", "", fold(ent.get("navn", ""))).strip()
        own_core = " ".join(name_tokens(ent.get("navn", "")))
        for page in res.pages:
            hay = f"{page.title}\n{page.text}"
            for m in list(sp.OPERATOR_RE.finditer(hay)) + list(sp.OPERATOR_AFTER_RE.finditer(hay)):
                named = re.sub(r"[^a-z0-9 ]", "", fold(m.group(1))).strip()
                named_core = " ".join(name_tokens(m.group(1)))
                if named and named != own and named_core != own_core:
                    others.setdefault("operator:" + m.group(1).strip(), m.group(0)[:120])
                    break
            # any labelled organisation number that is not ours, even one that fails the checksum
            for m in sp.LABELLED_NUMBER_RE.finditer(hay):
                num = re.sub(r"\D", "", m.group(1))[-9:]
                if len(num) == 9 and num != orgnr and num not in sub_orgnrs:
                    others.setdefault(num, m.group(0)[:80])
    # phone and e-mail prove contact, not identity: a group switchboard or an owner's mobile is shared.
    # Without the organisation number they also need every distinctive word of the legal name on the site.
    if not ours_seen and res.proofs:
        site_text = " ".join(f"{p.site_name} {p.title} {p.text}" for p in res.pages)
        name_ok = _tokens_present([t for t in toks if t not in ("og", "i", "pa", "av")], site_text)
        if not name_ok:
            res.proofs = [p for p in res.proofs if p.kind not in ("phone", "email")]
    # housing co-ops and section owners' associations: managers' sites look plausible, so only the number proves it
    form = ((ent.get("organisasjonsform") or {}).get("kode") or "").upper()
    if form in ("BRL", "ESEK", "BBL", "SAM") or fold(ent.get("navn", "")).startswith(("sameiet", "boligsameiet", "eierseksjonssameiet")):
        if not ours_seen:
            res.proofs = []
    res.other_orgnrs = sorted(others)
    if others and not ours_seen:
        # the site names a different legal entity as its operator
        res.status = "other_entity"
        res.reason = "site states organisation number " + ", ".join(sorted(others)[:3])
        return res
    if res.proofs and not any(p.kind in STRONG_PROOFS for p in res.proofs):
        # name-only proofs: a free-hosting subdomain or a site placed in another town is somebody else's
        host = res.home.host() if res.home else ""
        elsewhere = place_conflict(res, ent, subunits)
        if HOSTED_PLATFORMS.search("." + host) or elsewhere:
            res.reason = f"name proof refused: the site is placed in {elsewhere}" if elsewhere else \
                "name proof refused on a free-hosting subdomain"
            res.proofs = []
    if res.proofs:
        res.status = "exact"
        res.reason = "; ".join(sorted({p.kind for p in res.proofs}))
        return res
    # A website or e-mail domain declared in the register is not proof on its own: managers, parents, chains and
    # sister companies are often declared (audit: 2 of 12 such sites were the entity's own). It stays a registry fact.
    res.status = "ambiguous"
    res.reason = res.reason or "no organisation number, registered phone, e-mail or address on the site"
    return res


def person_named(parts: list[str], folded: str) -> bool:
    """A registered person's name in folded text: in full, or the first name with any trailing part of the
    rest ("Andreas Greve-Isdahl" for Andreas Alnæs Greve-Isdahl; "Kari Olsen" for Kari Marie Olsen)."""
    if len(parts) < 2:
        return False
    if f" {' '.join(parts)} " in folded:
        return True
    return any(f" {parts[0]} {' '.join(parts[k:])} " in folded for k in range(1, len(parts)))


def _company_link(res: "SiteResult", ent: dict, subunits: list[dict], people: list[dict] | None) -> bool:
    """Something on the site that ties it to this company beyond its name: a registered role holder's full
    name, the registered phone or e-mail, or the registered street or postcode."""
    text = " ".join(f"{p.title} {p.text}" for p in res.pages if p.generator != "script-bundle")
    folded = " " + " ".join(re.findall(r"[a-z0-9]+", fold(text))) + " "
    for x in people or []:
        parts = re.findall(r"[a-z0-9]+", fold(x.get("name", "")))
        if x.get("kind") == "person" and person_named(parts, folded):
            return True
    phones = {norm_phone(v) for v in [ent.get("telefon"), ent.get("mobil")] + [u.get("telefon") for u in subunits] if v} - {""}
    emails = {v.lower() for v in [ent.get("epostadresse")] + [u.get("epost") for u in subunits] if v}
    for page in res.pages:
        if any(d in phones for d, _ in sp.phones(page)) or any(e in emails for e in sp.emails(page)):
            return True
    addr = ent.get("forretningsadresse") or {}
    streets = [fold(s) for s in addr.get("adresse") or [] if s and re.search(r"\d", s) and not fold(s).startswith("c/o")]
    pc = addr.get("postnummer") or ""
    return any(s in fold(text) for s in streets) or bool(pc and re.search(rf"(?<!\d){pc}(?!\d)", text))


async def unique_name_check(client: Client, res: SiteResult, ent: dict, orgnr: str, subunits: list[dict],
                            people: list[dict] | None = None) -> SiteResult:
    """A guessed domain that spells the whole name, whose home page is titled with that name, on a Norwegian
    site, is the company's own when no other active entity or workplace in the register carries that name
    (or a longer name that starts with it). The register search is the proof that the name is unambiguous."""
    if res.status != "ambiguous" or res.candidate.origin != "name_derived" or not res.home or res.other_orgnrs:
        return res
    form = ((ent.get("organisasjonsform") or {}).get("kode") or "").upper()
    if form in ("BRL", "ESEK", "BBL", "SAM") or fold(ent.get("navn", "")).startswith(("sameiet", "boligsameiet", "eierseksjonssameiet")):
        return res
    core = [t for t in name_tokens(ent.get("navn", "")) if t not in MINOR]
    joined = "".join(core)
    host = res.home.host()
    label = fold(registrable(host).split(".")[0]).replace("-", "")
    norwegian = host.endswith(".no")  # a .com may negotiate "no" from our Accept-Language: not proof of anything
    if not core or label != joined or len(joined) < 8 or not norwegian or len(res.home.text) < 200:
        return res
    named = ""
    for value in (res.home.title, res.home.site_name, *_jsonld_names(res.home)):
        if foreign_entity(value):
            continue
        words = set(re.findall(r"[a-z0-9]+", fold(value or "")))
        if all(t in words for t in core) or (len(core) >= 2 and joined in re.sub(r"[^a-z0-9]", "", fold(value or ""))):
            named = value
            break
    if not named:
        return res
    own = {orgnr} | {u.get("organisation_number") for u in subunits}
    # search the name as written and squashed: "DEKK HUSET" must find "DEKKHUSET AS" (and the reverse)
    queries = list(dict.fromkeys([" ".join(core), joined]))
    for kind, query in [(k, q) for q in queries for k in ("enheter", "underenheter")]:
        f = await client.get("brreg", f"https://data.brreg.no/enhetsregisteret/api/{kind}?size=50&navn={quote(query)}",
                             headers={"Accept": "application/json"}, check_robots=False, retries=1)
        if not f.ok:
            return res  # cannot show the name is unique: stay ambiguous
        try:
            rows = (json.loads(f.body).get("_embedded") or {}).get(kind) or []
        except ValueError:
            return res
        for r in rows:
            if r.get("organisasjonsnummer") in own or r.get("overordnetEnhet") in own or r.get("slettedato") or r.get("konkurs"):
                continue
            other = "".join(t for t in name_tokens(r.get("navn", "")) if t not in MINOR and t not in LEGAL_FORMS)  # "ENK STIAN SÆTHER"
            if other.startswith(joined):
                res.reason = f"the name is shared with {r.get('navn')} ({r.get('organisasjonsnummer')})"
                return res
    elsewhere = place_conflict(res, ent, subunits)
    if elsewhere:
        res.reason = f"name proof refused: the site is placed in {elsewhere}"
        return res
    if not _company_link(res, ent, subunits, people):
        # a webshop with only a brand name and a free-mail address could be anyone's (a domain bought or sold)
        res.reason = "unique name, but nothing on the site ties it to this company (no role holder, contact or address)"
        return res
    res.proofs.append(Proof("unique_name_domain", sp_clip(named), res.home.final_url, res.home.sha256, res.home.retrieved_at, 0.9))
    res.status, res.reason = "exact", "unique_name_domain"
    return res


PAGE_WORDS = {"hjem", "home", "forside", "startside", "hovedside", "velkommen", "welcome", "start", "index", "om oss",
              "about", "about us", "kontakt", "kontakt oss", "contact", "contact us", "nyheter", "news", "tjenester", "services",
              "produkter", "products", "meny", "menu", "hjemmeside", "front page", "frontpage", "aktuelt", "blogg", "blog"}


async def sibling_check(client: Client, res: SiteResult, ent: dict, orgnr: str, subunits: list[dict]) -> SiteResult:
    """A site proven without the organisation number is withheld when its brand stem is the exact name of
    another active entity (sister companies share addresses, phones and owners)."""
    if res.status != "exact" or any(p.kind == "orgnr" for p in res.proofs):
        return res
    # the site prints our exact registered name with its legal form ("Okkenhaug Bil AS"): an entity named like the
    # brand in ANOTHER municipality is a namesake; one in our municipality is treated as the site's owner
    legal = _exact_name_rx(ent.get("navn", ""))
    named_on_site = bool(legal and any(legal.search(f"{p.site_name}\n{p.title}\n{p.text}") for p in res.pages))
    own_muni = fold(((ent.get("forretningsadresse") or ent.get("postadresse") or {}).get("kommune")) or "")
    own = {orgnr} | {u.get("organisation_number") for u in subunits}
    stems: list[str] = []
    own_toks = name_tokens(ent.get("navn", ""))
    label = res.domain.split(".")[0]
    if label and label != res.domain:
        # "ryfylkebygg" is searched as "ryfylke bygg": the register's name search needs the words apart
        parts_ = split_words(fold(label).replace("-", ""), set(own_toks))
        if parts_ and len(parts_) >= 2:
            stems.append(" ".join(parts_))
        stems.append(label.replace("-", " "))
    for page in res.pages[:1]:
        # the brand is the title part that is not a page word ("Hjem - Driftstorget" is Driftstorget's home page)
        parts = [x for x in re.split(r"\s+[|–—-]\s+|\s*\|\s*", page.title or "") if x.strip()]
        brand = next((x for x in parts if fold(x.strip()) not in PAGE_WORDS), "")
        brand = re.sub(r"^\s*(velkommen til|welcome to|hjem\s*[-–]?)\s+", "", brand or "", flags=re.I)
        for x in (page.site_name, brand):
            core = " ".join(name_tokens(x or ""))
            if core and len(core) >= 4 and core not in PAGE_WORDS:
                stems.append(core)
    own_core = " ".join(own_toks)
    squash = lambda s: re.sub(r"[^a-z0-9]", "", s)  # noqa: E731  "G-TEK" and "GTEK" are one brand
    own_street = fold(" ".join((ent.get("forretningsadresse") or {}).get("adresse") or []))
    for stem in dict.fromkeys(stems):
        if " ".join(name_tokens(stem)) == own_core or squash(stem) == squash(own_core):
            continue
        f = await client.get("brreg", "https://data.brreg.no/enhetsregisteret/api/enheter?size=20&navn=" + quote(stem),
                             headers={"Accept": "application/json"}, check_robots=False, retries=1)
        if not f.ok:
            continue
        try:
            rows = (json.loads(f.body).get("_embedded") or {}).get("enheter") or []
        except ValueError:
            continue
        for r in rows:
            if r.get("organisasjonsnummer") in own or r.get("slettedato") or r.get("konkurs"):
                continue
            other_core = " ".join(name_tokens(r.get("navn", "")))
            # another entity declared this very domain as its website (RYFYLKE-BYGG AS for ryfylkebygg.no)
            their_site = re.sub(r"^(https?://)?(www\.)?", "", (r.get("hjemmeside") or "").lower()).split("/")[0]
            if their_site and their_site == res.domain.removeprefix("www.") and not res.candidate.declared:
                res.status = "other_entity"
                res.reason = f"{r.get('navn')} ({r.get('organisasjonsnummer')}) declares {their_site} as its website"
                res.other_orgnrs = [r.get("organisasjonsnummer")]
                return res
            # sister companies at our own registered address whose names carry the site's brand (VOLT HARVEST I, II,
            # III and GROUP at one address): name and address on the site cannot tell which of them it belongs to
            their_street = fold(" ".join((r.get("forretningsadresse") or {}).get("adresse") or []))
            stem_core = " ".join(name_tokens(stem))
            if (own_street and their_street == own_street and stem_core and len(stem_core) >= 4
                    and f" {stem_core} " in f" {other_core} " and not res.candidate.declared):
                res.status = "ambiguous"
                res.reason = (f"{r.get('navn')} ({r.get('organisasjonsnummer')}) shares our registered address and the "
                              f"brand '{stem}'; without the organisation number on the site it is not certain whose site it is")
                res.other_orgnrs = [r.get("organisasjonsnummer")]
                return res
            if other_core and other_core == " ".join(name_tokens(stem)):
                other_muni = fold(((r.get("forretningsadresse") or r.get("postadresse") or {}).get("kommune")) or "")
                if named_on_site and own_muni and other_muni and other_muni != own_muni:
                    continue
                res.status = "other_entity"
                res.reason = f"brand stem '{stem}' is the registered name of {r.get('navn')} ({r.get('organisasjonsnummer')})"
                res.other_orgnrs = [r.get("organisasjonsnummer")]
                return res
    return res


def site_host(res: SiteResult) -> str:
    return (urlsplit(res.home.final_url).hostname or "") if res.home else ""
