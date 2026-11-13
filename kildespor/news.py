"""Dated company news from the company's own verified website.

Only a site already verified as the exact company's (and not another business's page the company's domain
forwards to) is read. Three ways in, cheapest first, all through the polite Client (robots.txt, per-host limits,
archived responses):

1. WordPress REST API: /wp-json/wp/v2/posts with the post's publish date ("date", never "modified").
2. RSS/Atom feeds the site links on its own domain: <pubDate> or <published> only. A feed's <updated> or
   <lastBuildDate> is when the feed was rebuilt, not when the article was published.
3. News listing pages (nyheter, aktuelt, news, blogg, presse, ...): article links under that section, opened one
   by one; the publish date comes from the article itself (JSON-LD datePublished, article:published_time,
   a <time> next to the headline or a "Publisert" date in the header). A date printed next to a link in the
   listing is trusted only when the articles we opened agree with their listing dates.

Every item needs a real headline and a publish date between 2010 and today, on the company's own registrable
domain. Default posts ("Hello world!", "Hei verden!"), menu labels, contact/service/product/category pages and
template listings (every item on one date) are refused. At most one "news_page" claim names the site's news
section when it holds an article we published, as Builderr's own crawler counts that page.
"""
from __future__ import annotations

import asyncio
import html as htmlmod
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from selectolax.parser import HTMLParser

from . import siteparse as sp
from .claims import Claim, Evidence, Profile
from .discovery import registrable
from .http import Client, Fetched
from .util import clip, fold

MAX_ITEMS = 10          # company news items per company
MAX_REQUESTS = 7        # extra requests per verified site
MAX_ARTICLES = 4        # article pages opened from a listing
BUDGET_S = 35.0         # wall-clock cap for one site
EARLIEST = date(2010, 1, 1)
SOURCE = "website_news"

# a path segment that names a news section ("/nyheter", "/blogg", "/aktuelt-og-presse")
SECTION_SEG = re.compile(r"^(?:nyheter|nyhet|aktuelt|news|newsroom|blogg|blog|presse|press|pressemeldinger|press-releases|"
                         r"artikler|artikkel|articles|arkiv|siste-nytt|nyheter-og-[a-z0-9-]+|aktuelt-og-[a-z0-9-]+|"
                         r"nyheter-[a-z0-9-]+|aktuelt-[a-z0-9-]+)$")
# Builderr's own crawler counts a page whose path matches this as company-owned activity
BUILDERR_SECTION = re.compile(r"/(news|press|aktuelt|nyheter|artikler|blog)(/|$)", re.I)
# path segments that make a URL a non-article (contact, services, products, archives by category/tag/author, paging)
REJECT_SEG = {
    "kontakt", "kontakt-oss", "contact", "contact-us", "om-oss", "om", "about", "about-us", "hvem-er-vi",
    "tjenester", "tjeneste", "services", "service", "produkter", "produkt", "products", "product", "shop", "butikk",
    "nettbutikk", "category", "categories", "kategori", "kategorier", "tag", "tags", "stikkord", "emne", "emner",
    "author", "authors", "forfatter", "page", "side", "feed", "rss", "wp-json", "wp-admin", "wp-login.php", "login",
    "logg-inn", "cart", "handlekurv", "kasse", "checkout", "personvern", "privacy", "personvernerklaering",
    "personvernerklaring", "cookies", "cookie", "vilkar", "terms", "search", "sok", "sitemap", "ansatte",
    "karriere", "jobb", "ledige-stillinger", "careers", "jobs", "referanser", "prosjekter-kategori",
}
DEFAULT_TITLE = re.compile(r"^(?:hello world|hei verden|hallo verden|hallo welt|hej verden|hej varlden|hei maailma|"
                           r"witaj,? swiecie|hola,? mundo|ola,? mundo|bonjour,? (?:tout )?le monde|ciao,? mondo|"
                           r"merhaba dunya|privet,? mir|hallo wereld|hello,? world|"
                           r"(?:velkommen|welcome) (?:til|to) (?:wordpress|min (?:blogg|nettside))|sample page|eksempelside|"
                           r"example page|eksempel side|eksempelinnlegg|testinnlegg|test ?post|test|untitled|uten tittel|"
                           r"(?:no|ingen) title|ingen tittel|elementor #?\d+|auto draft|utkast|draft|blog post title (?:one|two|three|four)|"
                           r".*\b(?:kommer snart|coming soon|under construction|under oppbygging)\b.*)\W*$")
DEFAULT_SLUG = {"hello-world", "hei-verden", "hallo-verden", "hallo-welt", "sample-page", "eksempelside", "example-page",
                "witaj-swiecie", "hola-mundo", "ola-mundo", "bonjour-tout-le-monde", "ciao-mondo", "hallo-wereld",
                "merhaba-dunya", "hej-varlden", "hej-verden"}
MENU_LABELS = {
    "les mer", "les hele saken", "read more", "nyheter", "news", "aktuelt", "blogg", "blog", "kontakt", "kontakt oss",
    "om oss", "hjem", "forside", "se alle", "vis alle", "alle nyheter", "flere nyheter", "se alle nyheter", "neste", "forrige",
    "next", "previous", "more", "mer", "presse", "arkiv", "nyhetsarkiv", "siste nytt", "pressemeldinger", "artikler",
    "tjenester", "produkter", "våre tjenester", "våre produkter", "ledige stillinger", "karriere", "meny", "menu",
    "all news", "latest news", "siste nyheter", "nyheter og aktuelt", "aktuelt og nyheter", "newsroom", "press releases",
}
NOT_PUBLISH = re.compile(r"(oppdatert|updated|sist endret|endret|modified|revidert|last edited)\W{0,3}$", re.I)
ARTICLE_TYPES = {"Article", "NewsArticle", "BlogPosting", "PressRelease", "Report", "ReportageNewsArticle",
                 "AnalysisNewsArticle", "TechArticle", "SocialMediaPosting", "LiveBlogPosting", "ScholarlyArticle"}
META_PUBLISHED = ("article:published_time", "og:published_time", "og:article:published_time", "datepublished",
                  "publish_date", "publishdate", "pubdate", "dc.date.issued", "dcterms.issued", "parsely-pub-date",
                  "sailthru.date")

MONTHS = {"januar": 1, "january": 1, "jan": 1, "februar": 2, "february": 2, "feb": 2, "mars": 3, "march": 3, "mar": 3,
          "april": 4, "apr": 4, "mai": 5, "may": 5, "juni": 6, "june": 6, "jun": 6, "juli": 7, "july": 7, "jul": 7,
          "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10, "october": 10, "okt": 10, "oct": 10,
          "november": 11, "nov": 11, "desember": 12, "december": 12, "des": 12, "dec": 12}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
TEXT_DATES = [
    (re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.\s?(20\d{2})(?![\d])"), "dmy"),
    (re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})\.?\s+(" + _MON + r")\.?,?\s+(20\d{2})(?!\d)", re.I), "dmonth"),
    (re.compile(r"(?<![a-z])(" + _MON + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})(?!\d)", re.I), "monthd"),
]


def today() -> date:
    return date.today()


# --- small helpers ---------------------------------------------------------------------------------------------

def parse_text_date(text: str) -> tuple[date, str] | None:
    """The first date written in running text, with the text as it appears ("12. mars 2024", "03.05.2024")."""
    best: tuple[int, date, str] | None = None
    for rx, kind in TEXT_DATES:
        for m in rx.finditer(text or ""):
            try:
                if kind == "dmy":
                    d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                elif kind == "ymd":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif kind == "dmonth":
                    d = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
                else:
                    d = date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
            except (ValueError, KeyError):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), d, m.group(0))
            break
    return (best[1], best[2]) if best else None


def parse_machine_date(v) -> date | None:
    """ISO 8601 or RFC 822 date as feeds, APIs and meta tags write it."""
    if not v or not isinstance(v, str):
        return None
    v = v.strip()
    if v.startswith("0000"):
        return None
    try:
        return _local(datetime.fromisoformat(v.replace("Z", "+00:00")))
    except ValueError:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    try:
        return _local(parsedate_to_datetime(v))
    except (TypeError, ValueError, IndexError):
        return None


def _local(dt: datetime) -> date:
    """The date as the stamp writes it. Sites differ in which day they show for a post stamped near midnight UTC
    (Wix shows the UTC day, WordPress the Norwegian one), so the stamp's own day is kept: it is the day the
    quoted evidence shows. Where an article page is opened, the day it shows readers wins (see dates_on_pages)."""
    return dt.date()


def date_ok(d: date | None) -> bool:
    return d is not None and EARLIEST <= d <= today()


def norm_url(u: str) -> str:
    s = urlsplit(u.strip())
    host = (s.hostname or "").lower().removeprefix("www.")
    return f"{host}{s.path.rstrip('/') or '/'}" + (f"?{s.query}" if s.query else "")


def untrack(u: str) -> str:
    """The link without campaign parameters (feeds add ?utm_source=rss)."""
    s = urlsplit(u)
    if not s.query:
        return u
    q = "&".join(x for x in s.query.split("&") if not x.lower().startswith(("utm_", "fbclid=", "gclid=")))
    return urlunsplit((s.scheme, s.netloc, s.path, q, s.fragment))


def segments(u: str) -> list[str]:
    return [fold(x) for x in urlsplit(u).path.lower().split("/") if x]


def section_index(u: str) -> int:
    """Index of the first path segment that names a news section, or -1."""
    for i, s in enumerate(segments(u)):
        if SECTION_SEG.match(s):
            return i
    return -1


def url_rejected(u: str) -> str:
    """Why a URL cannot be an article ("" when it can)."""
    s = urlsplit(u)
    segs = segments(u)
    if not segs:
        return "home page"
    bad = next((x for x in segs if x in REJECT_SEG), "")
    if bad:
        return f"'{bad}' page"
    if re.search(r"(?:^|&)(?:page|paged|side)=\d+", s.query):
        return "page number"
    if re.fullmatch(r"\d{1,3}|p\d{1,3}|page-?\d{1,3}|side-?\d{1,3}", segs[-1]):
        return "page number"
    if segs[-1] in DEFAULT_SLUG or re.search(r"sample-(?:item|post|page|article)|lorem-ipsum|dummy-(?:post|text)", segs[-1]):
        return "default post"
    if re.search(r"%20|\s", s.path):
        return "malformed link"
    if re.search(r"\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?|mp4|svg|webp|xml)$", s.path, re.I):
        return "file"
    return ""


def title_rejected(title: str, site_names: set[str] = frozenset()) -> str:
    t = re.sub(r"\s+", " ", title or "").strip()
    f = fold(t).strip(" .!:")
    if DEFAULT_TITLE.match(f):
        return "default post"
    if len(t) < 12:
        return "title under 12 characters"
    if f in {fold(x) for x in MENU_LABELS}:
        return "menu label"
    if f in site_names:
        return "site name, not a headline"
    parts = [fold(x).strip(" .!:") for x in re.split(r"\s+[|–—-]\s+|\s*\|\s*|\s+::\s+", t) if x.strip()]
    labels = {fold(x) for x in MENU_LABELS}
    if len(parts) > 1 and all(x in labels or x in site_names for x in parts):
        return "section page title ('News - Company'), not a headline"
    return ""


def clean_title(title: str, site_names: set[str]) -> str:
    """The headline without the site name the page title carries ("Ny avtale - Firma AS" -> "Ny avtale").
    Only a leading or trailing site-name part is cut, so the result stays a literal piece of the page."""
    t = re.sub(r"\s+", " ", htmlmod.unescape(title or "")).strip()
    sep = r"(?:\s+[|–—-]\s+|\s*\|\s*|\s+::\s+|:\s+)"
    m = re.match(r"^(.*?)" + sep + r"(.+)$", t)
    if m and fold(m.group(1)).strip(" .!:") in site_names and len(m.group(2)) >= 12:
        t = m.group(2)
    m = re.match(r"^(.+)" + sep + r"(.*?)$", t)
    if m and fold(m.group(2)).strip(" .!:") in site_names and len(m.group(1)) >= 12:
        t = m.group(1)
    return t


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


@dataclass
class Item:
    title: str
    url: str
    published: str
    source: str  # company website | company feed | company WordPress API
    evidence: Evidence
    confidence: float = 0.95
    page_evidence: Evidence | None = None  # the article page itself, when it was opened and shows the date


@dataclass
class Run:
    """State for one site: the request budget, what was refused (for tests and traces)."""
    client: Client
    site_reg: str
    origin: str
    site_names: set[str]
    left: int = MAX_REQUESTS
    rejects: list[tuple[str, str]] = field(default_factory=list)
    listings: dict[str, sp.Page] = field(default_factory=dict)  # fetched or crawled section pages by norm_url

    async def get(self, url: str, **kw) -> Fetched | None:
        if self.left <= 0:
            return None
        self.left -= 1
        return await self.client.get(SOURCE, url, **kw)

    def same_site(self, u: str) -> bool:
        h = (urlsplit(u).hostname or "").lower()
        return bool(h) and registrable(h) == self.site_reg

    def reject(self, what: str, why: str) -> None:
        self.rejects.append((why, clip(what, 120)))


def _ev(f: Fetched, span: str, method: str) -> Evidence:
    return Evidence(f.url, "company_owned", f.retrieved_at, f.sha256, span, method, final_url=f.final_url,
                    http_status=f.status, source_name=(urlsplit(f.final_url or f.url).hostname or ""))


def _page_ev(page: sp.Page, span: str, method: str) -> Evidence:
    return Evidence(page.final_url, "company_owned", page.retrieved_at, page.sha256, span, method,
                    final_url=page.final_url, http_status=page.status, source_name=page.host())


def template_listing(items: list[Item], run: Run, where: str) -> list[Item]:
    """A listing or feed whose every item carries one date is a template (the build date), not publish dates."""
    if len(items) >= 3 and len({i.published for i in items}) == 1:
        run.reject(where, f"every item dated {items[0].published} (template)")
        return []
    return items


def is_wordpress(res) -> bool:
    for page in res.pages[:4]:
        if "wordpress" in (page.generator or "").lower():
            return True
        hay = " ".join(page.scripts[:40]) + " " + " ".join(u for u, _ in page.links[:300])
        if "/wp-content/" in hay or "/wp-includes/" in hay or "/wp-json/" in hay:
            return True
    return False


# --- 1. WordPress REST API ----------------------------------------------------------------------------------------

def parse_wp_posts(raw: str, f: Fetched, run: Run) -> list[Item]:
    try:
        posts = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(posts, list):
        return []
    out: list[Item] = []
    for post in posts[:MAX_ITEMS]:
        if not isinstance(post, dict):
            continue
        link = untrack(str(post.get("link") or ""))
        title = strip_tags((post.get("title") or {}).get("rendered", "") if isinstance(post.get("title"), dict) else str(post.get("title") or ""))
        raw_date = str(post.get("date") or "")
        d = parse_machine_date(raw_date)
        slug = str(post.get("slug") or "")
        if post.get("type") not in (None, "post"):
            run.reject(link, "not a post")
            continue
        if not run.same_site(link):
            run.reject(link, "link on another domain")
            continue
        why = ("default post" if slug in DEFAULT_SLUG else "") or title_rejected(title, run.site_names) or url_rejected(link)
        if why:
            run.reject(f"{title} <{link}>", why)
            continue
        if not date_ok(d):
            run.reject(f"{title} ({raw_date})", "date in the future or before 2010")
            continue
        # quote the post's own fields exactly as the API wrote them (JSON escapes and all)
        start = raw.find(f'"id":{post.get("id")},') if post.get("id") is not None else -1
        seg = raw[start: start + 4000] if start >= 0 else raw
        pieces = []
        for rx in (r'"date"\s*:\s*"[^"]*"', r'"title"\s*:\s*\{\s*"rendered"\s*:\s*"(?:[^"\\]|\\.)*"', r'"link"\s*:\s*"(?:[^"\\]|\\.)*"'):
            m = re.search(rx, seg)
            if m:
                pieces.append(m.group(0))
        span = " · ".join(pieces) if len(pieces) == 3 else f"{title} · {raw_date}"
        out.append(Item(clip(title, 200), link, d.isoformat(), "company WordPress API", _ev(f, span, "wordpress_rest_api"), 0.97))
    return template_listing(out, run, f.url)


async def from_wordpress(run: Run) -> tuple[list[Item], int]:
    url = f"{run.origin}/wp-json/wp/v2/posts?per_page={MAX_ITEMS}&_fields=id,date,date_gmt,link,title,slug,type"
    f = await run.get(url, headers={"Accept": "application/json"}, max_body=1_000_000)
    if f is not None and f.status == 404:  # plain permalinks: the same route through the query string
        f = await run.get(f"{run.origin}/?rest_route=/wp/v2/posts&per_page={MAX_ITEMS}&_fields=id,date,date_gmt,link,title,slug,type",
                          headers={"Accept": "application/json"}, max_body=1_000_000)
    if f is None or not f.ok or "json" not in (f.content_type or "").lower():
        return [], (f.status if f is not None else 0)
    return parse_wp_posts(f.text(), f, run), f.status


# --- 2. RSS / Atom ----------------------------------------------------------------------------------------------------

ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(f: Fetched, run: Run) -> list[Item]:
    try:
        root = ET.fromstring(f.body)
    except ET.ParseError:
        return []
    out: list[Item] = []
    rss_items = root.findall(".//item")
    entries = rss_items or root.findall(f".//{ATOM}entry")
    for it in entries[:MAX_ITEMS * 2]:
        def text(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        if rss_items:
            title, link, raw_date = text("title"), text("link"), text("pubDate")
            kind = "rss_item"
        else:
            title, raw_date = text(f"{ATOM}title"), text(f"{ATOM}published")
            link = ""
            for ln in it.findall(f"{ATOM}link"):
                if ln.attrib.get("rel", "alternate") == "alternate" and ln.attrib.get("href"):
                    link = ln.attrib["href"]
                    break
            kind = "atom_entry"
        title = strip_tags(title)
        link = untrack(urljoin(f.final_url, link)) if link else ""
        if not raw_date:
            run.reject(title or link, "no publish date (only an updated date)")
            continue
        d = parse_machine_date(raw_date)
        if not link or not run.same_site(link):
            run.reject(f"{title} <{link}>", "link on another domain")
            continue
        why = title_rejected(title, run.site_names) or url_rejected(link)
        if why:
            run.reject(f"{title} <{link}>", why)
            continue
        if not date_ok(d):
            run.reject(f"{title} ({raw_date})", "date in the future or before 2010")
            continue
        out.append(Item(clip(title, 200), link, d.isoformat(), "company feed", _ev(f, f"{title} · {raw_date}", kind), 0.95))
    out.sort(key=lambda i: i.published, reverse=True)
    return template_listing(out[:MAX_ITEMS], run, f.url)


def feed_urls(res, run: Run) -> list[str]:
    out: list[str] = []
    for page in [*res.pages, *run.listings.values()]:
        for u in page.feeds:
            low = u.lower()
            if not run.same_site(u) or "comment" in low or "kommentar" in low or "/wp-json/" in low:
                continue
            if u not in out:
                out.append(u)
    # the site-wide feed before category and tag feeds
    out.sort(key=lambda u: bool(re.search(r"/(category|kategori|tag|author)/", u, re.I)))
    return out


async def from_feeds(run: Run, urls: list[str]) -> list[Item]:
    for u in urls[:2]:
        f = await run.get(u, max_body=1_500_000)
        if f is None or not f.ok:
            continue
        items = parse_feed(f, run)
        if items:
            return items
    return []


def visible_date(html: str, url: str, iso: str) -> tuple[str, str]:
    """(the publish date as the article page shows it to a reader: "3. mars 2026" or a <time>, its ISO day), or
    ("", ""). The stamp's own day is looked for first; the day before or after counts too, for posts stamped near
    midnight UTC that the page shows on the neighbouring day."""
    want = date.fromisoformat(iso)
    page = sp.parse(html, url, url)
    lines = page.text.splitlines()
    for day in (want, want - timedelta(days=1), want + timedelta(days=1)):
        for line in lines:
            for rx, _ in TEXT_DATES:
                for m in rx.finditer(line):
                    hit = parse_text_date(m.group(0))
                    if hit and hit[0] == day and not NOT_PUBLISH.search(line[: m.start()]):
                        return m.group(0), day.isoformat()
        for m in re.finditer(r"<time\b([^>]*)>", html, re.I):
            dt = re.search(r"datetime\s*=\s*[\"']([^\"']+)[\"']", m.group(1))
            if dt and not re.search(r"modif|updat|oppdat|endret", m.group(1), re.I) and parse_machine_date(dt.group(1)) == day:
                return dt.group(1), day.isoformat()
    return "", ""


async def dates_on_pages(run: Run, items: list[Item], sample: int = 2) -> bool:
    """Posts from the API or a feed are news only if their pages show readers a date: sites that keep projects,
    properties for sale or products as posts show none. The newest posts are opened (at most two); the first
    that shows its own publish date settles it, and its page joins that item's evidence."""
    opened = 0
    for it in sorted(items, key=lambda i: i.published, reverse=True)[:sample]:
        f = await run.get(it.url, max_body=2_000_000)
        if f is None:
            break
        opened += 1
        if not f.ok or not run.same_site(f.final_url) or "html" not in (f.content_type or "html").lower():
            continue
        shown, day = visible_date(f.text(), f.final_url, it.published)
        if shown:
            it.page_evidence = _ev(f, f"{it.title} · {shown}", "article_visible_date")
            it.published = day  # the day readers see
            return True
    if opened:
        run.reject(f"{items[0].url} and {len(items) - 1} more", "posts show readers no date (projects, products or pages)")
    return not opened  # nothing could be opened within the budget: keep the API's or feed's own dates


# --- 3. listing pages and article pages ----------------------------------------------------------------------------

POST_SEGS = {"post", "posts", "blogposts", "blog-posts", "blog-post", "blogpost", "artikkel", "article", "innlegg", "sak",
             "saker", "nyhet", "story", "stories"}


def article_link(u: str, under: list[str] | None) -> bool:
    """A link that can be an article: below a news section ("/nyheter/ny-avtale", "/prosjekt/x/nyheter/y"), below
    the listing's own section, or (from a listing) in a post folder ("/blog-posts/slug", "/post/slug")."""
    segs = segments(u)
    if not segs or url_rejected(u) or SECTION_SEG.match(segs[-1]):
        return False
    idx = section_index(u)
    if idx >= 0 and len(segs) > idx + 1:
        return True
    if under is not None:
        if len(segs) > len(under) and segs[: len(under)] == under:
            return True
        return len(segs) >= 2 and segs[0] in POST_SEGS
    return False


def article_links(page: sp.Page, run: Run, listing: bool = True) -> list[tuple[str, str]]:
    """(url, anchor) for article links on a news listing (or, with listing=False, on any other page), in page
    order, one per article."""
    under = None
    if listing:
        idx = section_index(page.final_url)
        if idx < 0:
            return []
        under = segments(page.final_url)[: idx + 1]
    seen: dict[str, tuple[str, str]] = {}
    for u, text in page.links:
        if u.startswith(("mailto:", "tel:")) or not run.same_site(u) or norm_url(u) == norm_url(page.final_url):
            continue
        if not article_link(u, under):
            continue
        s = urlsplit(u)
        clean = urlunsplit((s.scheme, s.netloc, s.path, s.query, ""))
        k = norm_url(clean)
        if k not in seen or len(text or "") > len(seen[k][1]):
            seen[k] = (clean, (text or "").strip())
    return list(seen.values())


def listing_dates(page: sp.Page, links: list[tuple[str, str]], run: Run) -> dict[str, tuple[str, str, str]]:
    """norm_url -> (date, title, span) where the listing prints a date right next to the link's headline."""
    lines = [x.strip() for x in page.text.split("\n")]
    heads = {re.sub(r"\s+", " ", t or "").strip() for _, t in links}

    def scan(i: int, step: int, reach: int):
        j = i + step
        while 0 <= j < len(lines) and abs(j - i) <= reach:
            if lines[j] in heads:
                return None  # reached the next or previous headline
            hit = parse_text_date(lines[j])
            if hit:
                return j, hit
            j += step
        return None

    after: dict[str, tuple] = {}
    before: dict[str, tuple] = {}
    titles: dict[str, str] = {}
    for u, text in links:
        t = re.sub(r"\s+", " ", text or "").strip()
        if title_rejected(t, run.site_names):
            continue
        i = next((k for k, ln in enumerate(lines) if ln == t), -1)
        if i < 0:
            continue
        titles[norm_url(u)] = t
        a, b = scan(i, 1, 3), scan(i, -1, 2)
        if a:
            after[norm_url(u)] = a
        if b:
            before[norm_url(u)] = b
    # a listing prints its dates on one side of the headline; the side most headlines have is the right one
    side = after if len(after) >= len(before) else before
    out: dict[str, tuple[str, str, str]] = {}
    for k, (j, (d, raw)) in side.items():
        if NOT_PUBLISH.search(lines[j][: lines[j].find(raw)]) or not date_ok(d):
            continue
        out[k] = (d.isoformat(), titles[k], f"{titles[k]} · {lines[j]}")
    return out


def article_from_html(html: str, f: Fetched, run: Run) -> Item | None:
    """The headline and publish date of one article page, or None (reason recorded)."""
    page = sp.parse(html, f.url, f.final_url)
    tree = HTMLParser(html)
    metas: dict[str, str] = {}
    for m in tree.css("meta"):
        a = m.attributes
        key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower().strip()
        if key and key not in metas and a.get("content"):
            metas[key] = (a.get("content") or "").strip()
    nodes = page.jsonld
    types = {t for n in nodes for t in ([n.get("@type")] if not isinstance(n.get("@type"), list) else n.get("@type")) if isinstance(t, str)}
    if metas.get("og:type", "").lower() == "product" or ("Product" in types and not types & ARTICLE_TYPES):
        run.reject(f.final_url, "product page")
        return None
    h1 = tree.css_first("h1")
    h1_text = re.sub(r"\s+", " ", h1.text() if h1 else "").strip()
    # --- publish date, strongest signal first
    found: tuple[date, str, str] | None = None  # (date, raw text, how)
    headline = None
    for n in nodes:
        t = n.get("@type")
        ts = set(t) if isinstance(t, list) else {t}
        art = bool(ts & ARTICLE_TYPES) or ("WebPage" in ts and metas.get("og:type", "").lower() == "article")
        raw = n.get("datePublished")
        if art and isinstance(raw, str):
            d = parse_machine_date(raw)
            if d:
                found = (d, raw, "jsonld_datePublished")
                headline = n.get("headline") or n.get("name")
                break
    if not found:
        for key in META_PUBLISHED:
            raw = metas.get(key)
            d = parse_machine_date(raw)
            if d:
                found = (d, raw, "meta_published_time")
                break
    if not found:
        for m in tree.css("[itemprop=datePublished]"):
            raw = m.attributes.get("datetime") or m.attributes.get("content") or ""
            d = parse_machine_date(raw)
            if d:
                found = (d, raw, "microdata_datePublished")
                break
    near_only = False
    if not found:
        # a <time datetime> beside the headline (inside the <article>, or close after the <h1>)
        pos_h1 = html.find("<h1")
        for m in re.finditer(r"<time\b([^>]*)>", html, re.I):
            attrs = m.group(1)
            dt = re.search(r"datetime\s*=\s*[\"']([^\"']+)[\"']", attrs)
            if not dt or re.search(r"modif|updat|oppdat|endret", attrs, re.I):
                continue
            before = re.sub(r"<[^>]+>", " ", html[max(0, m.start() - 160): m.start()])
            if NOT_PUBLISH.search(before.strip()):
                continue
            in_article = html.rfind("<article", 0, m.start()) > html.rfind("</article", 0, m.start())
            close = pos_h1 >= 0 and -1500 <= m.start() - pos_h1 <= 3000
            d = parse_machine_date(dt.group(1))
            if d and (in_article or close):
                found = (d, dt.group(1), "time_element")
                near_only = True
                break
    if not found and h1_text:
        # "Publisert 12. mars 2024" in the article header, right around the headline
        i = page.text.find(h1_text)
        if i >= 0:
            window = page.text[max(0, i - 200): i + len(h1_text) + 400]
            hit = parse_text_date(window)
            if hit:
                d, raw = hit
                before = window[: window.find(raw)][-30:]
                if not NOT_PUBLISH.search(before):
                    found = (d, raw, "header_date")
                    near_only = True
    if not found:
        run.reject(f.final_url, "no publish date on the article")
        return None
    d, raw_date, how = found
    if not near_only and h1_text:
        # a machine date that disagrees with the date printed beside the headline is a migration or import stamp
        # (plugport.no: JSON-LD 2026-02-27, the page shows "May 3, 2024"): the date readers see wins
        i = page.text.find(h1_text)
        if i >= 0:
            window = page.text[max(0, i - 200): i + len(h1_text) + 400]
            hit = parse_text_date(window)
            if hit and abs((hit[0] - d).days) > 2:
                before = window[: window.find(hit[1])][-30:]
                if not NOT_PUBLISH.search(before):
                    d, raw_date, how = hit[0], hit[1], "header_date"
    body = (tree.css_first("[itemprop=articleBody]") or tree.css_first(".entry-content") or tree.css_first(".post-content")
            or tree.css_first(".article-content") or tree.css_first(".elementor-widget-theme-post-content")
            or tree.css_first("article") or tree.css_first("main"))
    if body is not None:
        words = len(re.findall(r"[^\W\d_]{2,}", body.text(separator=" ")))
        if words < 35:
            # a teaser or an empty "Uncategorized" post that only says "kontakt oss" is not an article
            run.reject(f"{f.final_url} ({words} words)", "too short to be an article")
            return None
    if not date_ok(d):
        run.reject(f"{f.final_url} ({raw_date})", "date in the future or before 2010")
        return None
    if near_only and d == today():
        run.reject(f"{f.final_url} ({raw_date})", "today's date beside the headline (a page clock, not a publish date)")
        return None
    # --- headline: the article's own, never the site name
    head = None
    for cand in ((headline if how == "jsonld_datePublished" else None), h1_text, metas.get("og:title"), page.title):
        cand = clean_title(str(cand or ""), run.site_names)
        if cand and not title_rejected(cand, run.site_names):
            head = cand
            break
    if not head:
        run.reject(f"{f.final_url} ({h1_text or metas.get('og:title') or page.title})", "no real headline")
        return None
    return Item(clip(head, 200), f.final_url, d.isoformat(), "company website", _ev(f, f"{head} · {raw_date}", "article_" + how), 0.95)


async def fetch_article(run: Run, url: str) -> Item | None:
    f = await run.get(url, max_body=2_000_000)
    if f is None or not f.ok or "html" not in (f.content_type or "html").lower():
        return None
    if not run.same_site(f.final_url) or url_rejected(f.final_url) or not urlsplit(f.final_url).path.strip("/"):
        run.reject(url, "redirects away from the article")
        return None
    return article_from_html(f.text(), f, run)


async def find_listings(res, run: Run) -> list[sp.Page]:
    """Section pages already crawled, or the one the site links (fetched once)."""
    pages: list[sp.Page] = []
    for page in res.pages[1:]:
        if page.generator in ("script-bundle", "page-data"):
            continue
        idx = section_index(page.final_url)
        if idx >= 0 and len(segments(page.final_url)) == idx + 1 and run.same_site(page.final_url):
            pages.append(page)
            run.listings[norm_url(page.final_url)] = page
    if pages:
        return pages
    for page in res.pages[:4]:
        for u, _ in page.links:
            if not run.same_site(u) or u.startswith(("mailto:", "tel:")):
                continue
            idx = section_index(u)
            if idx >= 0 and len(segments(u)) == idx + 1:
                got = await fetch_listing(run, u)
                return [got] if got else []
    return []


async def fetch_listing(run: Run, url: str) -> sp.Page | None:
    k = norm_url(url)
    if k in run.listings:
        return run.listings[k]
    f = await run.get(url)
    if f is None or not f.ok or "html" not in (f.content_type or "html").lower() or not run.same_site(f.final_url):
        return None
    page = sp.parse(f.text(), url, f.final_url)
    page.sha256, page.retrieved_at, page.status = f.sha256, f.retrieved_at, f.status
    run.listings[k] = page
    return page


async def from_listings(run: Run, listings: list[sp.Page], res) -> list[Item]:
    links: list[tuple[str, str, sp.Page]] = []
    have: set[str] = set()

    def add(u: str, t: str, page: sp.Page, first: bool = False) -> None:
        k = norm_url(u)
        if k in have or k in run.listings:
            return
        have.add(k)
        if first:
            links.insert(0, (u, t, page))
        else:
            links.append((u, t, page))
    for page in listings:
        for u, t in article_links(page, run):
            add(u, t, page)
    # article links on the home page and the other crawled pages ("/aktuelt/ny-avtale" linked from the front page)
    for page in res.pages:
        if page.generator in ("script-bundle", "page-data") or any(page is x for x in listings):
            continue
        for u, t in article_links(page, run, listing=False):
            add(u, t, page)
    # crawled pages that are themselves articles under a section
    for page in res.pages[1:]:
        if page.generator in ("script-bundle", "page-data") or not run.same_site(page.final_url):
            continue
        if article_link(page.final_url, None):
            add(page.final_url, page.title, page, first=True)
    if not links:
        return []
    by_listing = {norm_url(p.final_url): listing_dates(p, [(u, t) for u, t, q in links if q is p], run) for p in listings}
    picks = [u for u, _, _ in links][:MAX_ARTICLES]
    got = await asyncio.gather(*(fetch_article(run, u) for u in picks))
    items = [i for i in got if i]
    # a listing's own dates count only when the articles we opened agree with them
    for page in listings:
        dates = by_listing[norm_url(page.final_url)]
        confirmed = [i for i in items if norm_url(i.url) in dates and dates[norm_url(i.url)][0] == i.published]
        disagreed = [i for i in items if norm_url(i.url) in dates and dates[norm_url(i.url)][0] != i.published]
        if not confirmed or disagreed:
            if dates:
                run.reject(page.final_url, "listing dates not confirmed by the articles")
            continue
        listed = []
        for u, t, q in links:
            k = norm_url(u)
            if q is page and k in dates and k not in {norm_url(i.url) for i in items}:
                d, title, span = dates[k]
                listed.append(Item(clip(title, 200), u, d, "company website", _page_ev(page, span, "news_listing_date"), 0.9))
        items.extend(template_listing(listed, run, page.final_url))
    return template_listing(items, run, "listing")


# --- the news section claim --------------------------------------------------------------------------------------

async def news_section(run: Run, items: list[Item]) -> tuple[sp.Page, str, str] | None:
    """(section page, article url, anchor) for the section page that links an article we publish."""
    keys = {norm_url(i.url): i for i in items}
    for page in run.listings.values():
        if not BUILDERR_SECTION.search(urlsplit(page.final_url).path + "/"):
            continue
        for u, t in page.links:
            if norm_url(u) in keys and t and len(t) >= 6:
                return page, u, t
    # the articles' own section, fetched once when the budget allows
    for i in items:
        idx = section_index(i.url)
        if idx < 0:
            continue
        s = urlsplit(i.url)
        sec = "/" + "/".join([x for x in s.path.split("/") if x][: idx + 1])
        url = f"{s.scheme}://{s.netloc}{sec}/"
        if not BUILDERR_SECTION.search(sec + "/") or norm_url(url) in run.listings:
            continue
        page = await fetch_listing(run, url)
        if page is None:
            continue
        for u, t in page.links:
            if norm_url(u) in keys and t and len(t) >= 6:
                return page, u, t
        break
    return None


# --- entry point ------------------------------------------------------------------------------------------------

def site_names(res) -> set[str]:
    out = set()
    for v in (res.home.title, res.home.site_name):
        if v:
            out.add(fold(v).strip(" .!:"))
            for part in re.split(r"\s+[|–—-]\s+", v):
                out.add(fold(part).strip(" .!:"))
    label = fold(registrable(res.home.host()).split(".")[0])
    out |= {label, label.replace("-", " ")}
    return {x for x in out if x}


async def add_company_news(client: Client, p: Profile, res, trace: dict | None = None) -> int:
    """Company news (and at most one news section page) from one verified site. Returns items added."""
    if getattr(res, "foreign_host", False) or not res.home or res.status != "exact":
        return 0
    try:
        return await asyncio.wait_for(_add(client, p, res, trace), timeout=BUDGET_S)
    except asyncio.TimeoutError:
        p.error(SOURCE, f"company news stopped after {BUDGET_S:.0f}s")
        return 0


async def _add(client: Client, p: Profile, res, trace: dict | None) -> int:
    s = urlsplit(res.home.final_url)
    run = Run(client, registrable(res.home.host()), f"{s.scheme}://{s.netloc}", site_names(res))
    have = [c for c in p.family_claims("activity") if c.field == "company_news"]
    room = MAX_ITEMS - len(have)
    if room <= 0:
        return 0
    items: list[Item] = []
    how = []
    wp_status = None
    if is_wordpress(res):
        items, wp_status = await from_wordpress(run)
        how.append(f"wordpress:{wp_status}")
    listings = await find_listings(res, run)
    if listings:
        how.append(f"listings:{len(listings)}")
    if items and not await dates_on_pages(run, items):
        how.append("wordpress:undated")
        items, wp_status = [], 0
        undated = True
    else:
        undated = False
    if not items and not undated:
        urls = feed_urls(res, run)
        if not urls and wp_status is not None and wp_status != 200:
            urls = [run.origin + "/feed/"]
        if urls:
            items = await from_feeds(run, urls)
            how.append(f"feeds:{len(urls)}")
            if items and not await dates_on_pages(run, items):
                how.append("feeds:undated")
                items = []
    if not items:
        items = await from_listings(run, listings, res)
        if items:
            how.append("articles")
    if len(items) >= 3:
        # a bulk import stamps many posts with one date (finndoff.no: 29 posts within a minute on 2026-03-03)
        counts = Counter(i.published for i in items)
        bulk = {d for d, n in counts.items() if n >= 3}
        if bulk:
            for i in items:
                if i.published in bulk:
                    run.reject(f"{i.url} ({i.published})", "one date shared by many posts (an import stamp)")
            items = [i for i in items if i.published not in bulk]
    seen = {norm_url(c.value.get("url", "")) for c in have if isinstance(c.value, dict)}
    picked: list[Item] = []
    for it in sorted(items, key=lambda i: i.published, reverse=True):
        k = norm_url(it.url)
        if k in seen:
            continue
        seen.add(k)
        picked.append(it)
        if len(picked) >= room:
            break
    for it in picked:
        p.add(Claim("activity", "company_news",
                    {"title": it.title, "url": it.url, "published": it.published, "source": it.source},
                    [it.evidence] + ([it.page_evidence] if it.page_evidence else []), label="Company news",
                    effective_date=it.published, confidence=it.confidence, key=f"activity:company_news:{it.url.lower()}"))
    if picked and not any(c.field == "news_page" for c in p.family_claims("activity")):
        sec = await news_section(run, picked)
        if sec:
            page, art_url, anchor = sec
            title = page.title or page.site_name or urlsplit(page.final_url).path.strip("/").split("/")[-1].title()
            p.add(Claim("activity", "news_page", {"url": page.final_url, "title": clip(title, 160)},
                        [_page_ev(page, anchor, "news_section_link")], label="News section on the company site",
                        confidence=0.95, attributes={"links_article": art_url},
                        key=f"activity:news_page:{page.final_url.lower()}"))
    if trace is not None:
        trace.setdefault("news", []).append({"site": run.site_reg, "methods": how, "items": len(picked),
                                             "requests": MAX_REQUESTS - run.left, "rejects": run.rejects[:12]})
    return len(picked)
