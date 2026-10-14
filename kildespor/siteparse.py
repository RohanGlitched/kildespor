"""Deterministic extraction from company web pages."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

ORGNR_RE = re.compile(r"(?<![\d])(\d{3})[\s .\-]?(\d{3})[\s .\-]?(\d{3})(?![\d])")
ORGNR_LABEL_RE = re.compile(r"(org(?:anisasjons)?\.?\s*-?\s*(?:nr|nummer|no)\.?|organi[sz]ation\s*(?:number|no\.?|nr)|company\s*(?:reg(?:istration)?\.?\s*)?(?:number|no\.?)|business\s*(?:id|number)|foretaksregisteret|enhetsregisteret|mva|vat)", re.I)
OPERATOR_RE = re.compile(r"(?:©|\(c\)|copyright|drevet av|driftet av|behandlingsansvarlig(?:\s+er)?|datakontroll[øo]r(?:\s+er)?|personvernansvarlig(?:\s+er)?|data\s*controller(?:\s+is)?|ansvarlig for (?:nettstedet|siden)|vilkårene gjelder(?:\s+for)?)[^\n]{0,80}?((?:[A-ZÆØÅ][\wæøåÆØÅ&.\-]*\s+){0,5}(?:AS|ASA|ANS|DA|SA|BA|NUF|IL|BBL|Gruppen|Group|Konsern|Idrettslag|Boligbyggelag|Forening|Stiftelse))(?![\wæøå])")
OPERATOR_AFTER_RE = re.compile(r"((?:[A-ZÆØÅ][\wæøåÆØÅ&.\-]*\s+){0,5}(?:AS|ASA|ANS|DA|SA|BA|NUF|IL|BBL|Gruppen|Group|Konsern|"
                               r"Idrettslag|Boligbyggelag|Forening|Stiftelse))\s+(?:er|is)\s+(?:the\s+)?(?:behandlingsansvarlig|"
                               r"data\s*controller|ansvarlig for (?:nettstedet|siden|behandlingen))")
LABELLED_NUMBER_RE = re.compile(r"(?:org(?:anisasjons)?\.?\s*-?\s*(?:nr|nummer|no)\.?|organi[sz]ation\s*(?:number|no\.?|nr)|foretaksregisteret)[\s:.]*((?:NO[\s\u00a0]?)?\d{3}[\s\u00a0.]?\d{3}[\s\u00a0.]?\d{3})", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d])(?:\+47[\s ]?|0047[\s ]?)?(\d{2}[\s ]?\d{2}[\s ]?\d{2}[\s ]?\d{2}|\d{3}[\s ]?\d{2}[\s ]?\d{3})(?![\d])")
POSTCODE_RE = re.compile(r"(?<![\d])(\d{4})[ \t ]+([A-ZÆØÅ][A-Za-zæøåÆØÅ\-]+(?:[ \t ][A-ZÆØÅ][A-Za-zæøåÆØÅ\-]+)?)")

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"^https?://(?:www\.|m\.|nb-no\.|no-nb\.)?(?:facebook|fb)\.com/(?!sharer|share|dialog|plugins|tr\b|groups/?$|events/?$|pages/?$|watch/?$|login|policy|help|privacy)([A-Za-z0-9.\-_/]+?)/?(?:[?#].*)?$", re.I),
    "instagram": re.compile(r"^https?://(?:www\.)?instagram\.com/(?!p/|explore|accounts|reel/|stories/)([A-Za-z0-9._]+)/?(?:[?#].*)?$", re.I),
    "linkedin": re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/(company|school|showcase)/([A-Za-z0-9\-_%.&+æøåÆØÅ]+)/?(?:[?#].*)?$", re.I),
    "youtube": re.compile(r"^https?://(?:www\.|m\.)?youtube\.com/(channel/[A-Za-z0-9_\-]+|@[A-Za-z0-9._\-]+|c/[A-Za-z0-9._\-]+|user/[A-Za-z0-9._\-]+)/?.*$", re.I),
    "x": re.compile(r"^https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/(?!intent|share|home|search|hashtag|i/)([A-Za-z0-9_]{1,15})/?(?:[?#].*)?$", re.I),
    "tiktok": re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)/?.*$", re.I),
    "pinterest": re.compile(r"^https?://(?:[a-z]{2}\.|www\.)?pinterest\.[a-z.]+/(?!pin/)([A-Za-z0-9_]+)/?(?:[?#].*)?$", re.I),
    "vimeo": re.compile(r"^https?://(?:www\.)?vimeo\.com/(?!\d+$)([A-Za-z0-9_]+)/?(?:[?#].*)?$", re.I),
    "snapchat": re.compile(r"^https?://(?:www\.)?snapchat\.com/add/([A-Za-z0-9._\-]+)/?.*$", re.I),
    "threads": re.compile(r"^https?://(?:www\.)?threads\.(?:net|com)/@([A-Za-z0-9._]+)/?.*$", re.I),
}
JOB_HOSTS = re.compile(r"(teamtailor\.com|jobylon\.com|webcruiter\.(?:no|com)|recman\.(?:no|page)|easycruit\.com|hrmanager\.no|"
                       r"jobbnorge\.no|finn\.no/job|arbeidsplassen\.nav\.no|varbi\.com|reachmee\.com|talentech|"
                       r"recruitee\.com|smartrecruiters\.com|workable\.com|lever\.co|greenhouse\.io|cvpartner|"
                       r"jobs\.personio|homerun\.co|career\.|careers\.|karriere\.|jobb\.)", re.I)
PRIORITY = [
    ("contact", re.compile(r"kontakt|contact|finn[-\s]?oss|find[-\s]?us|om[-\s]?oss/kontakt", re.I)),
    ("about", re.compile(r"om[-\s]?oss|om[-\s]?firma|om[-\s]?selskapet|about|historie|hvem[-\s]?er[-\s]?vi|who[-\s]?we", re.I)),
    ("people", re.compile(r"ansatte|medarbeidere|ledelse|leadership|management|team|people|styret|board|vare[-\s]?folk|v[åa]re[-\s]?ansatte", re.I)),
    ("careers", re.compile(r"karriere|career|jobb|jobs|ledige[-\s]?stillinger|stilling|vacanc|join[-\s]?us|bli[-\s]?med", re.I)),
    ("news", re.compile(r"nyheter|news|aktuelt|blogg|blog|presse|press|artikler|articles|investor|siste[-\s]?nytt", re.I)),
    ("privacy", re.compile(r"personvern|privacy|cookie|vilk[åa]r|terms|impressum|salgsbetingelser", re.I)),
    ("locations", re.compile(r"avdelinger|kontorer|offices|locations|lokasjoner|butikker|stores|finn[-\s]?butikk", re.I)),
]
PARKED = re.compile(r"(domain (?:is )?for sale|is parked|er parkert|parkert (?:hos|av)|parking page|dette domenet er|domenet er registrert|parked (?:free|domain)|this domain (?:is|has been) registered|"
                    r"kjøp domenet|buy this domain|under construction|kommer snart|coming soon|website is under|default web page|"
                    r"welcome to nginx|it works!|apache2 (?:ubuntu|debian) default|index of /|webhotell|domeneshop\.no/parkering|"
                    r"denne siden er under arbeid|nettsiden er under (?:arbeid|utvikling|oppbygging))", re.I)


@dataclass
class Page:
    url: str
    final_url: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    lang: str = ""
    text: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)  # (absolute url, anchor text)
    jsonld: list[dict] = field(default_factory=list)
    feeds: list[str] = field(default_factory=list)
    generator: str = ""
    sha256: str = ""
    retrieved_at: str = ""
    status: int = 0

    def host(self) -> str:
        return (urlsplit(self.final_url).hostname or "").lower()


def _clean_url(u: str) -> str:
    s = urlsplit(u)
    return urlunsplit((s.scheme, s.netloc.lower(), s.path or "/", s.query, ""))


def _flatten_jsonld(obj, out: list[dict]) -> None:
    if isinstance(obj, list):
        for x in obj:
            _flatten_jsonld(x, out)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            _flatten_jsonld(obj["@graph"], out)
        if "@type" in obj:
            out.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)) and v is not obj.get("@graph"):
                if isinstance(v, dict) and "@type" in v and v.get("@type") in ("JobPosting", "NewsArticle", "BlogPosting", "Event"):
                    out.append(v)


def parse(html: str, url: str, final_url: str) -> Page:
    tree = HTMLParser(html)
    p = Page(url=url, final_url=final_url)
    if tree.css_first("html"):
        p.lang = (tree.css_first("html").attributes.get("lang") or "")[:10]
    t = tree.css_first("title")
    p.title = re.sub(r"\s+", " ", t.text() if t else "").strip()[:300]
    for m in tree.css("meta"):
        a = m.attributes
        key = (a.get("name") or a.get("property") or "").lower()
        content = (a.get("content") or "").strip()
        if key in ("description", "og:description") and not p.description:
            p.description = content[:600]
        elif key == "og:site_name":
            p.site_name = content[:200]
        elif key == "generator":
            p.generator = content[:100]
    for s in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(s.text() or "{}", strict=False)
        except ValueError:
            continue
        _flatten_jsonld(data, p.jsonld)
    for ln in tree.css('link[rel="alternate"]'):
        typ = (ln.attributes.get("type") or "").lower()
        if "rss" in typ or "atom" in typ:
            href = ln.attributes.get("href")
            if href:
                p.feeds.append(urljoin(final_url, href))
    base = final_url
    b = tree.css_first("base")
    if b and b.attributes.get("href"):
        base = urljoin(final_url, b.attributes["href"])
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#")):
            continue
        if href.startswith(("mailto:", "tel:")):
            p.links.append((href, re.sub(r"\s+", " ", a.text() or "").strip()[:120]))
            continue
        try:
            absu = urljoin(base, href)
        except ValueError:
            continue
        if absu.startswith("http"):
            p.links.append((absu, re.sub(r"\s+", " ", a.text() or "").strip()[:120]))
    for node in tree.css("script, style, noscript, svg, template, iframe"):
        node.decompose()
    body = tree.body
    p.text = re.sub(r"[ \t ]+", " ", body.text(separator="\n") if body else "")
    p.text = re.sub(r"\n\s*\n+", "\n", p.text).strip()[:200_000]
    return p


def orgnr_mentions(text: str) -> list[tuple[str, str]]:
    """(orgnr, surrounding span) for 9-digit numbers that look like an organisation number."""
    out = []
    for m in ORGNR_RE.finditer(text):
        num = "".join(m.groups())
        if not valid_orgnr(num):
            continue
        span = text[max(0, m.start() - 60): m.end() + 30].replace("\n", " ")
        out.append((num, span))
    return out


def valid_orgnr(num: str) -> bool:
    if len(num) != 9 or not num.isdigit() or num[0] not in "89":
        return False
    w = [3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(d) * k for d, k in zip(num[:8], w))
    r = 11 - s % 11
    r = 0 if r == 11 else r
    return r != 10 and r == int(num[8])


def emails(page: Page) -> list[str]:
    found = []
    for href, _ in page.links:
        if href.lower().startswith("mailto:"):
            e = unquote(href[7:].split("?")[0]).strip().lower()
            if EMAIL_RE.fullmatch(e):
                found.append(e)
    for e in EMAIL_RE.findall(page.text):
        e = e.lower().strip(".")
        if not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            found.append(e)
    seen, out = set(), []
    for e in found:
        local = e.split("@")[0]
        if re.search(r"[-_.](se|dk|fi|uk|us|de|nl|pl)$", local):
            continue  # a foreign sister's mailbox
        if e not in seen and not e.startswith(("example@", "navn@", "name@", "your@", "din@")):
            seen.add(e)
            out.append(e)
    return out


YEAR_PAIR = re.compile(r"^(19|20)\d\d(19|20)\d\d$")


def _norwegian(raw: str) -> str:
    """8-digit Norwegian number from a tel: value or printed number, or "" when it is foreign or malformed."""
    raw = raw.strip()
    d = re.sub(r"\D", "", raw)
    if raw.startswith("+") or raw.startswith("00"):
        if d.startswith("0047"):
            d = d[4:]
        elif d.startswith("47"):
            d = d[2:]
        else:
            return ""  # another country's number
    elif len(d) == 10 and d.startswith("47"):
        d = d[2:]
    if len(d) != 8 or d[0] not in "2345679" or YEAR_PAIR.match(d):
        return ""
    return d


def phones(page: Page) -> list[tuple[str, str]]:
    """(8-digit Norwegian number, span). Foreign numbers, year pairs and numbers glued to more digits are skipped."""
    out: dict[str, str] = {}
    for href, text in page.links:
        if href.lower().startswith("tel:"):
            if re.search(r"fax|faks", text or "", re.I):
                continue
            d = _norwegian(unquote(href[4:]))
            if d:
                out.setdefault(d, f"{href[4:]} · {text}" if text else href[4:])
    for m in PHONE_RE.finditer(page.text):
        before = page.text[max(0, m.start() - 14): m.start()]
        if re.search(r"fax|faks|telefaks", page.text[max(0, m.start() - 16): m.start()], re.I):
            continue
        after = page.text[m.end(): m.end() + 3]
        if re.search(r"\+\s?\d{1,3}[\s\u00a0]?(?:\(0\)[\s\u00a0]?)?\d{0,4}[\s\u00a0]?$", before) and not re.search(r"\+\s?47[\s\u00a0]?$", before):
            continue  # follows a foreign country code
        if re.match(r"[\s\u00a0]?\d", after):
            continue  # part of a longer number
        d = re.sub(r"\D", "", m.group(1))
        if len(d) == 8 and d[0] in "2345679" and not YEAR_PAIR.match(d):
            ctx = page.text[max(0, m.start() - 40): m.end() + 10].replace("\n", " ")
            if re.search(r"tlf|telefon|phone|tel\.?|mobil|ring|sentralbord|\+47", ctx, re.I):
                out.setdefault(d, ctx)
    return list(out.items())


def socials(page: Page) -> list[tuple[str, str, str]]:
    """(platform, canonical url, handle)"""
    out: dict[tuple[str, str], tuple[str, str, str]] = {}
    for href, anchor in page.links:
        if re.search(r"\b(foto|photo|fotograf|photographer|design(?:et)? (?:av|by)|levert av|webdesign)\b", anchor or "", re.I):
            continue
        for platform, rx in SOCIAL_PATTERNS.items():
            m = rx.match(href)
            if not m:
                continue
            if platform == "linkedin":
                handle = f"{m.group(1).lower()}/{m.group(2)}"
                url = f"https://www.linkedin.com/{handle}"
            elif platform == "youtube":
                handle = m.group(1)
                url = f"https://www.youtube.com/{handle}"
            elif platform == "facebook":
                handle = m.group(1).strip("/")
                if handle.lower().startswith("profile.php") or handle.lower() in ("home.php",):
                    q = urlsplit(href).query
                    if "id=" not in q:
                        break
                    handle = "profile.php?" + q
                elif handle.lower().startswith(("p/", "pg/")) and handle.count("/") >= 1:
                    handle = handle.split("/")[1] if handle.lower().startswith("pg/") else "p/" + handle.split("/")[1]
                elif "/" in handle and not handle.lower().startswith(("pages/", "people/")):
                    handle = handle.split("/")[0]
                if handle.lower() in ("p", "pg", "policies", "business", "privacy", "legal", "terms", "ads", "help", "pages",
                                      "people", "watch", "groups", "events", "marketplace", "gaming", "login", "home.php"):
                    break
                url = f"https://www.facebook.com/{handle}"
            else:
                handle = m.group(1)
                base = {"instagram": "https://www.instagram.com/", "x": "https://x.com/", "tiktok": "https://www.tiktok.com/@",
                        "pinterest": "https://www.pinterest.com/", "vimeo": "https://vimeo.com/",
                        "snapchat": "https://www.snapchat.com/add/", "threads": "https://www.threads.net/@"}[platform]
                url = base + handle
            hl = handle.lower().split("/")[-1]
            if hl in ("", "share", "sharer", "home", "intent", "wix", "wix-com", "wixcom", "squarespace", "wordpress", "wordpressdotcom",
                      "shopify", "facebook", "meta", "instagram", "youtube", "linkedin", "tiktok", "twitter", "x", "privacy", "policies",
                      "business", "terms", "legal", "help", "about", "explore", "watch", "jobs", "feed", "hashtag", "search", "i",
                      "webflow", "godaddy", "one-com", "onecom", "domeneshop", "squarespace-inc", "hubspot", "mailchimp",
                      "elementor", "divi", "elegantthemes", "themeforest", "envato", "vimeo", "staff", "channel", "user", "c"):
                break
            out.setdefault((platform, url.lower()), (platform, url, handle))
            break
    return list(out.values())


def job_links(page: Page) -> list[tuple[str, str]]:
    out = []
    for href, text in page.links:
        if JOB_HOSTS.search(href) and not href.lower().startswith(("mailto:", "tel:")):
            out.append((_clean_url(href), text))
    return out


def internal_links(page: Page, site_host: str) -> dict[str, list[tuple[str, str]]]:
    """Priority internal links by kind."""
    def reg(h: str) -> str:
        parts = h.lower().strip(".").split(".")
        return ".".join(parts[-3:]) if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") else ".".join(parts[-2:])

    def same(h: str) -> bool:
        h = h.lower()
        return (h == site_host or h == "www." + site_host or site_host == "www." + h or h.endswith("." + site_host.removeprefix("www."))
                or (bool(h) and reg(h) == reg(site_host)))
    kinds: dict[str, list[tuple[str, str]]] = {k: [] for k, _ in PRIORITY}
    seen = set()
    for href, text in page.links:
        if href.startswith(("mailto:", "tel:")):
            continue
        s = urlsplit(href)
        if not same(s.hostname or "") or re.search(r"\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?|mp4|svg|webp)$", s.path, re.I):
            continue
        u = _clean_url(href)
        if u in seen:
            continue
        seen.add(u)
        hay = f"{s.path} {text}"
        for kind, rx in PRIORITY:
            if rx.search(hay):
                kinds[kind].append((u, text))
                break
    return kinds


def parked(page: Page) -> bool:
    words = len(page.text.split())
    hay = f"{page.title}\n{page.text[:3000]}"
    return bool(PARKED.search(hay)) and words < 400 or words < 12
