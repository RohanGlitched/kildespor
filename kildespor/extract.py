"""Turn a verified company site into claims."""
from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from . import siteparse as sp
from .claims import Claim, Evidence, Profile
from .discovery import registrable
from .http import Client
from .site import SiteResult
from .util import clip, fold, name_tokens, norm_phone

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
    value = {"url": home.final_url, "domain": registrable(home.host()), "title": clip(home.title, 160),
             "discovered_via": res.candidate.origin, "identity_proof": sorted({pr.kind for pr in res.proofs})}
    if home.generator:
        value["generator"] = home.generator
    p.add(Claim("website", "official_website", value, ev, label="Official website", confidence=best.strength,
                key=f"website:official_website:{registrable(home.host())}"))


def add_site_claims(p: Profile, res: SiteResult, ent: dict) -> dict:
    """Contact, social, description, locations and hiring links from a verified site."""
    out = {"socials": [], "feeds": [], "job_links": [], "news_pages": []}
    site_reg = registrable(res.home.host())
    reg_phones = {norm_phone(x) for x in (ent.get("telefon"), ent.get("mobil")) if x}
    # company-owned profiles: when a site links several profiles on one platform (client portfolios, partners,
    # template leftovers), keep only those whose handle resembles the company's name, domain or brand
    found: dict[str, dict[str, tuple]] = {}
    for page in res.pages:
        for platform, url, handle in sp.socials(page):
            found.setdefault(platform, {}).setdefault(url.lower().rstrip("/"), (platform, url, handle, page))
    hints = _identity_hints(ent, res)
    for platform, items in found.items():
        keep = list(items.items())
        if len(keep) > 1:
            keep = [(k, v) for k, v in keep if _resembles(v[2], hints)]
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
    for x in (res.home.site_name, res.home.title.split("|")[0].split(" - ")[0]):
        hints |= {t for t in name_tokens(x or "") if len(t) >= 4}
    return hints


def _resembles(handle: str, hints: set[str]) -> bool:
    h = re.sub(r"[^a-z0-9]", "", fold(handle.split("?")[0].split("/")[-1]))
    return bool(h) and any(x in h or (len(h) >= 4 and h in x) for x in hints)


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
    for s in same:
        if not isinstance(s, str):
            continue
        fake = sp.Page(url=page.url, final_url=page.final_url, links=[(s, "")])
        for platform, url, handle in sp.socials(fake):
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
    title = node.get("title")
    if not title:
        return
    posted = _iso(node.get("datePosted"))
    loc = node.get("jobLocation")
    city = ""
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        a = loc.get("address") or {}
        city = a.get("addressLocality", "") if isinstance(a, dict) else ""
    v = {"title": clip(str(title), 160), "url": node.get("url") or page.final_url, "location": city,
         "valid_through": _iso(node.get("validThrough")), "source": "company site JobPosting"}
    p.add(Claim("jobs", "job_posting", v, [_ev(page, f"JobPosting: {title} datePosted {node.get('datePosted')}", "jsonld")],
                label="Job posting", effective_date=posted, key=f"jobs:job_posting:{fold(str(title))[:80]}:{posted}"))


def _jsonld_article(p: Profile, page: sp.Page, node: dict) -> None:
    headline = node.get("headline") or node.get("name")
    when = _iso(node.get("datePublished") or node.get("startDate") or node.get("dateCreated"))
    if not headline or not when:
        return
    url = node.get("url") or node.get("mainEntityOfPage") or page.final_url
    if isinstance(url, dict):
        url = url.get("@id") or page.final_url
    p.add(Claim("activity", "company_news", {"title": clip(str(headline), 200), "url": str(url), "source": "company site"},
                [_ev(page, f"{node.get('@type')}: {headline} ({when})", "jsonld")], label="Company news",
                effective_date=when, key=f"activity:company_news:{fold(str(headline))[:80]}"))


def _postal_addresses(p: Profile, page: sp.Page, ent: dict) -> None:
    for m in list(sp.POSTCODE_RE.finditer(page.text))[:6]:
        line_start = page.text.rfind("\n", 0, m.start()) + 1
        line_end = page.text.find("\n", m.end())
        line = page.text[line_start: line_end if line_end > 0 else m.end() + 40].strip()
        prev_start = page.text.rfind("\n", 0, max(0, line_start - 1)) + 1
        prev = page.text[prev_start: line_start].strip()
        street_rx = re.compile(r"[A-Za-zæøåÆØÅ.\- ]{3,}(?:vei|veien|veg|vegen|gate|gata|gaten|plass|plassen|vn\.?|gt\.?|allé|alle|brygge|bryggen|torget|stredet|bakken|svingen|tunet|ringen|haugen|lia|åsen|vegen|kaien)\s*\d+[A-Za-z]?", re.I)
        street = street_rx.search(line) or street_rx.search(prev)
        if not street:
            continue
        addr = f"{street.group(0).strip()}, {m.group(1)} {m.group(2)}"
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
    for page in res.pages[1:]:
        if re.search(r"karriere|career|jobb|jobs|stilling|vacanc", page.final_url, re.I):
            p.add(Claim("jobs", "careers_page", {"url": page.final_url, "title": clip(page.title, 140)},
                        [_ev(page, page.title or page.final_url, "careers_page")], label="Careers page", confidence=0.92,
                        key=f"jobs:careers_page:{page.final_url.lower().rstrip('/')}"))
            break
    for u, text, page in out["job_links"][:3]:
        host = urlsplit(u).hostname or ""
        p.add(Claim("jobs", "recruitment_channel", {"url": u, "platform": registrable(host), "text": clip(text, 80)},
                    [_ev(page, f"link to {u} ({text})", "outbound_link")], label="Recruitment page linked from the site",
                    confidence=0.9, key=f"jobs:recruitment_channel:{u.lower()}"))


async def add_feed_items(client: Client, p: Profile, res: SiteResult, feeds: list[str], ent: dict, limit: int = 12) -> int:
    """Dated news items from the company's own RSS/Atom feed."""
    site_reg = registrable(res.home.host())
    tried = 0
    added = 0
    candidates = [f for f in feeds if registrable(urlsplit(f).hostname or "") == site_reg and "comments" not in f.lower()]
    if not candidates and "wordpress" in (res.home.generator or "").lower():
        candidates = [res.home.final_url.rstrip("/") + "/feed/"]
    for feed in candidates[:2]:
        tried += 1
        f = await client.get("website_feed", feed, max_body=1_500_000)
        if not f.ok:
            continue
        try:
            root = ET.fromstring(f.body)
        except ET.ParseError:
            continue
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for it in items[:limit]:
            def g(tag: str) -> str:
                el = it.find(tag)
                if el is None:
                    el = it.find("{http://www.w3.org/2005/Atom}" + tag)
                if el is None:
                    return ""
                return (el.text or el.attrib.get("href") or "").strip()
            title = g("title")
            link = g("link")
            when = _iso(g("pubDate") or g("published") or g("updated"))
            if not title or not when:
                continue
            ev = Evidence(feed, "company_owned", f.retrieved_at, f.sha256, f"{title} — {when}", "rss_item",
                          final_url=f.final_url, http_status=f.status, source_name=urlsplit(feed).hostname or "")
            if p.add(Claim("activity", "company_news", {"title": clip(title, 200), "url": link or feed, "source": "company feed"},
                           [ev], label="Company news", effective_date=when, key=f"activity:company_news:{fold(title)[:80]}")):
                added += 1
        if added:
            break
    return added


def news_from_pages(p: Profile, res: SiteResult, limit: int = 10) -> int:
    """Dated headlines from news/blog listing pages (link text next to a date)."""
    added = 0
    for page in res.pages[1:]:
        if not re.search(r"nyhet|news|aktuelt|blogg|blog|presse|artikl|siste", page.final_url, re.I):
            continue
        lines = page.text.split("\n")
        link_by_text = {t.strip().lower(): u for u, t in page.links if t and len(t) > 15}
        for i, line in enumerate(lines):
            d = _parse_date(line)
            if not d or d.year < 2015 or d > date.today():
                continue
            window = [x.strip() for x in lines[max(0, i - 2): i + 3] if x.strip()]
            title = next((w for w in window if w.lower() in link_by_text and len(w) > 15), None)
            if not title:
                continue
            p.add(Claim("activity", "company_news", {"title": clip(title, 200), "url": link_by_text[title.lower()],
                                                      "source": "company news page"},
                        [_ev(page, f"{title} {line.strip()}", "news_listing_date")], label="Company news",
                        effective_date=d.isoformat(), confidence=0.85, key=f"activity:company_news:{fold(title)[:80]}"))
            added += 1
            if added >= limit:
                return added
    return added
