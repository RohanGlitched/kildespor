"""Turn a verified company site into claims."""
from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from . import siteparse as sp
from .claims import Claim, Evidence, Profile
from .discovery import registrable
from .http import Client
from .site import SiteResult
from .util import clip, fold, name_tokens, norm_phone, split_words

DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(20\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})\.?\s+(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember|"
                r"jan|feb|mar|apr|jun|jul|aug|sep|sept|okt|nov|des)\.?\s+(20\d{2})", re.I), "dmonth"),
]
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12}


def _ev(page: sp.Page, span: str, method: str, url: str | None = None) -> Evidence:
    return Evidence(url or page.final_url, "company_owned", page.retrieved_at, page.sha256, span, method,
                    final_url=page.final_url, http_status=page.status, source_name=page.host())


def _parse_date(text: str) -> date | None:
    for rx, kind in DATE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        try:
            if kind == "dmy":
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if kind == "ymd":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            mon = MONTHS[m.group(2).lower()[:3] if m.group(2).lower()[:3] in MONTHS else m.group(2).lower()[:4]]
            return date(int(m.group(3)), mon, int(m.group(1)))
        except (ValueError, KeyError):
            continue
    return None


def _iso(v: str | None) -> str | None:
    if not v:
        return None
    v = str(v).strip()
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(v).date().isoformat()
    except (TypeError, ValueError, IndexError):
        d = _parse_date(v)
        return d.isoformat() if d else None


def add_website(p: Profile, res: SiteResult) -> None:
    home = res.home
    best = max(res.proofs, key=lambda x: x.strength)
    ev = [Evidence(pr.url, "company_owned" if pr.kind != "registry_declared" else "official_registry",
                   pr.retrieved_at, pr.sha256, f"{pr.kind}: {pr.detail}", "identity_proof_" + pr.kind,
                   source_name=urlsplit(pr.url).hostname or "") for pr in res.proofs]
    url, domain = home.final_url, registrable(home.host())
    cand_domain = registrable(res.candidate.domain)
    if domain != cand_domain and urlsplit(home.final_url).path.strip("/"):
        # the company's own domain forwards to its page on another business's site (a chain's member profile,
        # a directory entry): the website is the company's own domain, not the other site
        url, domain = f"https://{res.candidate.domain.removeprefix('www.')}/", cand_domain
        res.foreign_host = True  # its links and profiles belong to that other business
    value = {"url": url, "domain": domain, "title": clip(home.title, 160),
             "discovered_via": res.candidate.origin, "identity_proof": sorted({pr.kind for pr in res.proofs})}
    if url != home.final_url:
        value["redirects_to"] = home.final_url
    if home.generator:
        value["generator"] = home.generator
    p.add(Claim("website", "official_website", value, ev, label="Official website", confidence=best.strength,
                key=f"website:official_website:{domain}"))


FOREIGN_PHONE = re.compile(r"\+\s?(?:46|45|44|49|358|31|32|33|34|39|41|43|48|1)[\s\d()-]{6,}")


def abroad(res: SiteResult, ent: dict) -> bool:
    """A foreign group's site (krouli.com: a Swedish head office, +46 numbers) that never shows this Norwegian
    company: its contacts, profiles, news and jobs are the group's."""
    if res.home.host().endswith(".no") or any(pr.kind == "orgnr" for pr in res.proofs):
        return False
    text = "\n".join(f"{pg.title}\n{pg.text}" for pg in res.pages)
    pc = (ent.get("forretningsadresse") or {}).get("postnummer")
    no_phone = r"(?<![\w#])(?:\+|00)\s?47[\s.]?\d{2}[\s.]?\d{2}[\s.]?\d{2}[\s.]?\d{2}(?!\d)|\(\+47\)"
    if re.search(no_phone, text) or (pc and re.search(rf"(?<!\d){pc}(?!\d)", text)):
        return False
    return bool(FOREIGN_PHONE.search(text))


def add_site_claims(p: Profile, res: SiteResult, ent: dict) -> dict:
    """Contact, social, description, locations and hiring links from a verified site."""
    if abroad(res, ent):
        res.foreign_host = True  # news, careers and profiles skip it too
        p.notes["site_abroad"] = res.home.host()
        return {"socials": [], "feeds": [], "job_links": [], "news_pages": [], "hints": set(), "ent": ent, "host": ""}
    out = {"socials": [], "feeds": [], "job_links": [], "news_pages": [], "hints": _identity_hints(ent, res), "ent": ent,
           "host": "" if getattr(res, "foreign_host", False) else res.home.host()}
    site_reg = registrable(res.home.host())
    reg_phones = {norm_phone(x) for x in (ent.get("telefon"), ent.get("mobil")) if x}
    # company-owned profiles: when a site links several profiles on one platform (client portfolios, partners,
    # template leftovers), keep only those whose handle resembles the company's name, domain or brand
    found: dict[str, dict[str, tuple]] = {}
    # a site that also prints another entity's organisation number, or says it is run on another's behalf
    # (nemitek.no: "drives av NemiTek AS på vegne av" the trade association), carries that entity's profiles too
    shared = bool(res.other_orgnrs) or any(re.search(r"p[aå] vegne av|on behalf of", f"{pg.text}", re.I) for pg in res.pages[:3])
    if shared:
        out["host"] = ""  # JSON-LD sameAs profiles are skipped too
    for page in ([] if getattr(res, "foreign_host", False) or shared else res.pages):
        for platform, url, handle in sp.socials(page):
            found.setdefault(platform, {}).setdefault(url.lower().rstrip("/"), (platform, url, handle, page))
    hints = _identity_hints(ent, res)
    out["hints"] = hints
    for platform, items in found.items():
        host = res.home.host().removeprefix("www.")
        keep = [(k, v) for k, v in items.items() if handle_matches(v[2], ent, host)
                and not (len(v[2]) < len(host) and host.startswith(v[2].lower()) and "." in v[2])]
        for key, (platform, url, handle, page) in keep[:2]:
            out["socials"].append((platform, url, handle))
            p.add(Claim("social", "company_profile", {"platform": platform, "url": url, "handle": handle},
                        [_ev(page, f"link to {url} on {page.final_url}", "outbound_link")],
                        label=f"{platform.title() if platform != 'x' else 'X'} profile", confidence=0.95,
                        key=f"social:company_profile:{key}"))
    phones_kept = 0
    for page in res.pages:
        kind = _page_kind(page, res)
        for e in sp.emails(page)[:6]:
            dom = e.split("@")[-1]
            if (registrable(dom) == site_reg or e == (ent.get("epostadresse") or "").lower()) and sp.EMAIL_RE.fullmatch(e):
                p.add(Claim("contact", "email", e, [_ev(page, e, "page_text_or_mailto")], label="E-mail on the company site",
                            confidence=0.97, key=f"contact:email:{e}"))
        if kind not in ("home", "contact", "about"):
            continue  # privacy pages quote regulators, store lists quote retailers, investor pages quote analysts
        nums = sp.phones(page)
        crowded = len(nums) > 4
        for d, span in nums:
            if phones_kept >= 3 or (crowded and d not in reg_phones):
                continue
            phones_kept += 1
            p.add(Claim("contact", "phone", d, [_ev(page, span, "page_text_or_tel")], label="Phone on the company site",
                        confidence=0.97 if d in reg_phones else 0.9, key=f"contact:phone:{d}"))
        for node in page.jsonld:
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(x in ("Organization", "LocalBusiness", "Corporation", "Store", "Restaurant", "ProfessionalService",
                         "HomeAndConstructionBusiness", "MedicalBusiness", "AutomotiveBusiness", "FoodEstablishment",
                         "LodgingBusiness", "Dentist", "LegalService", "AccountingService", "RealEstateAgent") for x in types):
                _jsonld_org(p, page, node, out)
            if "JobPosting" in types:
                _jsonld_job(p, page, node)
            if any(x in ("NewsArticle", "BlogPosting", "Article", "PressRelease", "Event") for x in types):
                _jsonld_article(p, page, node)
        for u, text in sp.job_links(page):
            if u not in [x[0] for x in out["job_links"]]:
                out["job_links"].append((u, text, page))
        out["feeds"].extend(f for f in page.feeds if f not in out["feeds"])
        _postal_addresses(p, page, ent)
    _description(p, res)
    _careers(p, res, out)
    return out


def _identity_hints(ent: dict, res: SiteResult) -> set[str]:
    hints = {t for t in name_tokens(ent.get("navn", "")) if len(t) >= 3}
    label = fold(res.home.host().removeprefix("www.").split(".")[0]).replace("-", "")
    if len(label) >= 3:
        hints.add(label)
    return hints


FOREIGN_FORMS = re.compile(r"(?:^|[^a-z])(ltd|limited|gmbh|inc|llc|plc|ab|aps|oy|oyj|bv|srl|sas|sarl|corp)(?:[^a-z]|$)")


HANDLE_GENERIC = {"as", "asa", "sa", "ba", "da", "ans", "enk", "nuf", "no", "com", "norge", "norway", "official", "offisiell", "the",
                  "og", "and", "hq", "i", "pa", "by", "shop", "store", "butikk", "nettbutikk", "studio", "app"}
CONNECTORS = {"og", "i", "and", "the", "of", "for", "av", "pa", "til", "med"}


def handle_name(handle: str) -> str:
    """The name part of a profile handle: 'pages/Roger-Aamodt/123' -> 'Roger-Aamodt', 'p/Fidi-Video-100063' -> 'Fidi-Video',
    'company/roger-aamodt-bygg' -> 'roger-aamodt-bygg'."""
    segs = [s for s in unquote(handle.split("?")[0]).strip("/").split("/") if s]
    if not segs:
        return ""
    if segs[0].lower() == "pages" and len(segs) > 2 and segs[1].lower() == "category":
        name = segs[-1]  # pages/category/<kind>/<Name-id>
    elif segs[0].lower() in ("pages", "pg", "p", "company", "school", "showcase", "c", "user") and len(segs) > 1:
        name = segs[1]
    else:
        name = segs[-1]
    return re.sub(r"[-_.]?\d{6,}$", "", name.lstrip("@"))


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(text))


def _segments(rest: str, words: set[str]) -> bool:
    """True when `rest` is a run of allowed words (or digits)."""
    return split_words(rest, words) is not None


def handle_cores(ent: dict, host: str) -> tuple[set[str], set[str]]:
    """Name cores a company's own handle must carry, and the extra words a handle may add to a core."""
    words = name_tokens(ent.get("navn", ""))
    cores = {"".join(words), "".join(w for w in words if w not in CONNECTORS)}
    # a run of two or more of its own name words ('naesstransport' for ASBJØRN NÆSS TRANSPORT AS); a sister company
    # whose registered name is exactly that run is caught by the register check afterwards
    for i in range(len(words)):
        for j in range(i + 2, len(words) + 1):
            run = [w for w in words[i:j] if w not in CONNECTORS]
            if len(run) >= 2:
                cores.add("".join(run))
    label = _alnum((host or "").removeprefix("www.").split(".")[0])
    if label:
        cores.add(label)
    place = set()
    for key in ("forretningsadresse", "postadresse"):
        a = ent.get(key) or {}
        place |= set(name_tokens(a.get("kommune") or "")) | set(name_tokens(a.get("poststed") or ""))
    allowed = set(words) | HANDLE_GENERIC | place
    return {c for c in cores if len(c) >= 4}, allowed


def handle_matches(handle: str, ent: dict, host: str) -> bool:
    """A profile is the company's own only when its handle is the company's name or site name, optionally with the
    company's own name words, its place, a legal form or a generic suffix. 'rogeraamodteiendom' on the site of
    ROGER AAMODT BYGG AS fails: 'eiendom' names a sister company (ROGER AAMODT EIENDOM AS)."""
    name = handle_name(handle)
    if not name or name.endswith("-") or FOREIGN_FORMS.search(re.sub(r"([a-z])([A-Z])", r"\1 \2", name).lower()):
        return False  # truncated slug, or a handle naming a foreign company
    h = _alnum(name)
    if len(h) < 3:
        return False
    cores, allowed = handle_cores(ent, host)
    for c in cores:
        if h == c:
            return True
        if h.startswith(c) and _segments(h[len(c):], allowed):
            return True
        if h.endswith(c) and _segments(h[: -len(c)], allowed):
            return True
    return False


def _page_kind(page: sp.Page, res: SiteResult) -> str:
    if page is res.home or page.final_url.rstrip("/") == res.home.final_url.rstrip("/"):
        return "home"
    u = page.final_url.lower()
    if re.search(r"kontakt|contact|finn-oss|find-us", u):
        return "contact"
    if re.search(r"om-oss|about|om-firma|om-selskapet", u):
        return "about"
    return "other"


def _jsonld_org(p: Profile, page: sp.Page, node: dict, out: dict) -> None:
    same = node.get("sameAs") or []
    if isinstance(same, str):
        same = [same]
    if not out.get("host"):
        same = []  # the site forwards to another business's page: its profiles are that business's
    for s in same:
        if not isinstance(s, str):
            continue
        fake = sp.Page(url=page.url, final_url=page.final_url, links=[(s, "")])
        for platform, url, handle in sp.socials(fake):
            if not handle_matches(handle, out.get("ent") or {}, out.get("host", "")):
                continue  # template leftovers, or a sister company's profile
            p.add(Claim("social", "company_profile", {"platform": platform, "url": url, "handle": handle},
                        [_ev(page, f"JSON-LD sameAs: {s}", "jsonld_sameAs")], label=f"{platform.title()} profile",
                        confidence=0.96, key=f"social:company_profile:{url.lower().rstrip('/')}"))
    if node.get("name"):
        p.add(Claim("identity", "public_brand", str(node["name"])[:120],
                    [_ev(page, f"JSON-LD {node.get('@type')} name: {node['name']}", "jsonld")], label="Public brand name",
                    confidence=0.9, key=f"identity:public_brand:{fold(str(node['name']))[:80]}"))
    rating = node.get("aggregateRating")
    if isinstance(rating, dict) and rating.get("ratingValue"):
        p.add(Claim("activity", "self_published_rating", {"rating": rating.get("ratingValue"), "count": rating.get("reviewCount") or rating.get("ratingCount"),
                                                         "best": rating.get("bestRating")},
                    [_ev(page, f"aggregateRating {rating}", "jsonld")], label="Rating shown on the company's own site",
                    confidence=0.8, attributes={"note": "self-published by the company; not an independent review score"}))
    hours = node.get("openingHours") or node.get("openingHoursSpecification")
    if hours:
        txt = hours if isinstance(hours, str) else str(hours)[:300]
        p.add(Claim("locations", "opening_hours", clip(txt, 200), [_ev(page, f"openingHours: {clip(txt, 200)}", "jsonld")],
                    label="Opening hours", confidence=0.9))


def _jsonld_job(p: Profile, page: sp.Page, node: dict) -> None:
    """JobPosting markup is published by the careers source (sources/careers.py), which checks the hiring organisation
    against this company, skips postings past their deadline and open applications, and quotes the posting itself.
    Publishing it here as well would skip those checks."""
    return None


def _jsonld_article(p: Profile, page: sp.Page, node: dict) -> None:
    """Company news is built in news.py from article pages, feeds and the WordPress API: a home or contact page
    marked up as an Article (often dated when the site was made) is not a news item."""
    return None


STREET_WORD = (r"^(?:vei|veien|veg|vegen|gate|gata|gaten|plass|plassen|vn\.?|gt\.?|allé|alle|brygge|bryggen|torget|"
               r"stredet|bakken|svingen|tunet|ringen|haugen|lia|åsen|kaien|\d+[a-z]?)$")


def _own_postcodes(p: Profile, ent: dict) -> set[str]:
    """Postcodes of the registered business and postal address and of every registered workplace."""
    codes = {(ent.get(k) or {}).get("postnummer") for k in ("forretningsadresse", "postadresse")}
    for u in p.notes.get("subunits") or []:
        codes |= set(re.findall(r"(?<!\d)\d{4}(?!\d)", str(u.get("address") or "")))
    return {c for c in codes if c}


def _postal_addresses(p: Profile, page: sp.Page, ent: dict) -> None:
    own = _own_postcodes(p, ent)
    for m in list(sp.POSTCODE_RE.finditer(page.text))[:6]:
        if m.group(1) not in own:
            continue  # a chain or group site lists other businesses' shops: only the company's own places count
        line_start = page.text.rfind("\n", 0, m.start()) + 1
        line_end = page.text.find("\n", m.end())
        line = page.text[line_start: line_end if line_end > 0 else m.end() + 40].strip()
        prev_start = page.text.rfind("\n", 0, max(0, line_start - 1)) + 1
        prev = page.text[prev_start: line_start].strip()
        street_rx = re.compile(r"[A-Za-zæøåÆØÅ.\- ]{3,}(?:vei|veien|veg|vegen|gate|gata|gaten|plass|plassen|vn\.?|gt\.?|allé|alle|brygge|bryggen|torget|stredet|bakken|svingen|tunet|ringen|haugen|lia|åsen|vegen|kaien)\s*\d+[A-Za-z]?", re.I)
        street = street_rx.search(line) or street_rx.search(prev)
        if not street:
            continue
        prev2 = page.text[page.text.rfind("\n", 0, max(0, prev_start - 1)) + 1: prev_start]
        if re.search(r"\bc\s*/\s*o\b|\bv/\s|\bpostboks\b", f"{prev2} {prev} {line}", re.I):
            continue  # an address "care of" a manager, accountant or law firm is theirs, not the company's
        words = street.group(0).split()
        # "Gården har adresse Grinivegen 12" -> "Grinivegen 12": cut a lead-in up to its last lowercase word
        # ("Kong Oscars gate 3" keeps its street word "gate")
        cut = max((i for i, w in enumerate(words[:-1]) if w.islower() and not re.search(STREET_WORD, w)), default=-1)
        addr = f"{' '.join(words[cut + 1:])}, {m.group(1)} {m.group(2)}"
        if len(addr) > 90:
            continue
        p.add(Claim("locations", "address_on_site", addr, [_ev(page, clip(prev + ' ' + line, 200), "address_pattern")],
                    label="Address on the company site", confidence=0.88, key=f"locations:address_on_site:{fold(addr)}"))


def _description(p: Profile, res: SiteResult) -> None:
    home = res.home
    if home.description and len(home.description) > 30:
        p.add(Claim("description", "site_description", clip(home.description, 400),
                    [_ev(home, home.description, "meta_description")], label="How the company describes itself", confidence=0.9))
    for page in res.pages[1:]:
        if re.search(r"om[-\s]?oss|about", page.final_url, re.I) and page.description and page.description != home.description:
            p.add(Claim("description", "about_page", clip(page.description, 400),
                        [_ev(page, page.description, "meta_description")], label="About page summary", confidence=0.88))
            break
    if home.title:
        p.add(Claim("identity", "site_title", clip(home.title, 160), [_ev(home, home.title, "html_title")], label="Website title",
                    confidence=0.9))


def _careers(p: Profile, res: SiteResult, out: dict) -> None:
    """The company's own careers page and its own recruitment account, from a verified site that is the company's own.
    A careers page must have a careers path ('karriere', 'ledige-stillinger', 'jobb-hos-oss', ...; never 'utstilling',
    'timebestilling' or 'kort-vei-til-jobb'), careers wording, and must not list jobs at other businesses."""
    from .sources.careers import Who, _label, careers_page_reason, careers_span, recruitment_account
    if getattr(res, "foreign_host", False):
        return  # the domain forwards to another business's site
    ent = p.notes.get("entity") or {}
    label = _label(res.home.host())
    who = Who(ent, p.notes.get("subunits") or [], p.orgnr, [label] + ([res.home.site_name] if res.home.site_name else []))
    pages = [pg for pg in res.pages[1:] if careers_page_reason(pg, who, label) is None]
    pages.sort(key=lambda pg: urlsplit(pg.final_url).path.count("/"))
    for page in pages:
        span = careers_span(page)
        if span:
            p.add(Claim("jobs", "careers_page", {"url": page.final_url, "title": clip(page.title, 140)},
                        [_ev(page, span, "careers_page")], label="Careers page", confidence=0.92,
                        key=f"jobs:careers_page:{page.final_url.lower().rstrip('/')}"))
            break
    seen: set[str] = set()
    for page in res.pages:
        for u, text in page.links:
            platform = recruitment_account(u, who, label, registrable(res.home.host()))
            key = u.lower().split("#")[0].rstrip("/")
            account = urlsplit(key).hostname or key  # one link per recruitment account
            if not platform or account in seen or len(seen) >= 2:
                continue
            seen.add(account)
            p.add(Claim("jobs", "recruitment_channel", {"url": u, "platform": platform, "text": clip(text, 80)},
                        [_ev(page, f"link to {u} ({text})", "outbound_link")], label="Recruitment page linked from the site",
                        confidence=0.9, key=f"jobs:recruitment_channel:{key}"))
