"""Open job postings on the recruitment pages a verified company website links to.

Runs after the website is verified (late source). For each verified site we look for recruitment
platforms the site itself links or embeds: on any crawled page's links, and in the raw HTML of the
site's careers page (iframes and widget scripts are not in the parsed links), plus one hop to the
careers page's own "vacancies" list. Each platform is read the way its public page reads itself:

| platform   | how                                                                          |
|------------|------------------------------------------------------------------------------|
| Teamtailor | the account's public `/jobs.rss` (also on custom career domains)             |
| Recman     | the account's `/jobs` page, then the JSON list that page loads (`/api/jobs`)  |
| ReachMee   | the HTML vacancy list the customer's iframe/widget script points at          |
| Jobylon    | the company embed list (`cdn.jobylon.com/jobs/companies/{id}/embed/v2/`)      |
| Jobbnorge  | Jobbnorge's public API (`publicapi.jobbnorge.no/v3/Jobs`), by employer id    |
| Easycruit  | the account's public XML vacancy export                                      |
| Mojob      | JobPosting JSON-LD on each linked ad (parser kept, switched off: ENABLED)     |
| Lever      | `api.lever.co/v0/postings/{account}`, Norwegian locations only (off)          |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs`, Norway only (off)          |
| Recruitee  | the account's `/api/offers/` (off)                                            |
| own site   | JobPosting JSON-LD on careers pages, and plain ads under the careers page     |

Not read: Webcruiter (robots.txt disallows all general crawlers), HR-manager (robots.txt allows only
application forms), FINN (terms forbid automated use), Workday (group tenants list many employers
without naming the employer per posting), SmartRecruiters (its API is disallowed in robots.txt).

Identity: a posting is published only when (a) the platform page was reached from a link or embed on
the verified site and (b) the posting's employer name (or, when the platform does not name one per
posting, the account name) matches the legal name, and it never names a different organisation number.
"""
from __future__ import annotations

import asyncio
import html as htmllib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree as ET

from .. import siteparse as sp
from ..claims import Claim, Evidence
from ..util import LEGAL_FORMS, clip, digits, fold, name_tokens
from . import Source

MAX_TARGETS = 3          # platform accounts read per company
MAX_POSTINGS = 20        # postings published per company
MAX_AD_PAGES = 8         # single-ad pages fetched per company (Mojob, Jobylon ads, own-site ads)
COMPANY_SECONDS = 6.0    # hard cap on fetching per company; whatever is read by then is kept
REQ_TIMEOUT = 5.0
# Platforms switched on for the official run: each has published postings that were opened and hand-checked
# against the company. Lever, Greenhouse, Recruitee and Mojob parsers are kept and tested but stay off until
# a real Norwegian company's postings through them have been hand-checked too.
ENABLED = {"teamtailor", "recman", "reachmee", "jobylon", "jobbnorge", "easycruit", "site"}
JOBBNORGE_FEED = "https://publicapi.jobbnorge.no/v3/Jobs"

LABEL = {"teamtailor": "Teamtailor", "recman": "Recman", "reachmee": "ReachMee", "jobylon": "Jobylon",
         "jobbnorge": "Jobbnorge", "easycruit": "Easycruit", "mojob": "Mojob", "lever": "Lever",
         "greenhouse": "Greenhouse", "recruitee": "Recruitee", "site": "company site"}
NOT_READ = {
    "webcruiter": (re.compile(r"webcruiter\.(?:no|com)", re.I), "robots.txt disallows general crawlers"),
    "hr-manager": (re.compile(r"hr-?manager\.(?:net|no)", re.I), "robots.txt allows only application forms"),
    "finn": (re.compile(r"(?:^|\.)finn\.no/job", re.I), "FINN.no terms forbid automated access"),
    "workday": (re.compile(r"myworkdayjobs\.com", re.I), "group tenants do not name the employer per posting"),
    "smartrecruiters": (re.compile(r"smartrecruiters\.com", re.I), "the public API is disallowed in robots.txt"),
}

# careers pages and vacancy lists on the company's own site (path segments, so "utstilling" never matches)
CAREERS_PATH = re.compile(r"(?:^|[/\-_.])(karriere|career|careers|jobb|jobbe|jobs?|ledige?[-_]stilling(?:er)?|stillinger|"
                          r"vacanc\w*|join[-_]us|bli[-_]med|work[-_]with[-_]us|open[-_]positions)(?=$|[/\-_.?#])", re.I)
LIST_PATH = re.compile(r"(?:^|[/\-_])(ledige?[-_]?stillinger|ledig[-_]stilling|stillinger|vacanc\w*|open[-_]positions|"
                       r"jobs|positions|openings)(?=$|[/\-_.?#])", re.I)
LIST_ANCHOR = re.compile(r"(ledige|våre|vare|alle) (stillinger|jobber)|se stillinger|ledige stillinger|open positions|vacancies|"
                         r"(see|view) (all )?(jobs|positions|openings|roles)|job openings", re.I)
CAREER_HOST = re.compile(r"^(career|careers|karriere|jobb|jobs|jobs\d|jobbe)\.", re.I)
AD_MARKERS = re.compile(r"s[øo]knadsfrist|stillingsprosent|tiltredelse|how to apply|send (?:din|en|oss din) s[øo]knad|"
                        r"s[øo]k (?:p[åa] )?(?:stillingen|her|n[åa])|apply (?:now|here|for this)|we are looking for|vi s[øo]ker",
                        re.I)
OPEN_APPLICATION = re.compile(r"[åa]pen (?:s[øo]knad|stillingsutlysning|utlysning)|open application|generell s[øo]knad|spontans[øo]knad|"
                              r"talent ?pool|talentbank|interesseliste", re.I)
NORWAY = re.compile(r"\b(norway|norge|noreg|oslo|bergen|trondheim|stavanger|troms[øo]|kristiansand|drammen|fredrikstad|"
                    r"sandnes|[åa]lesund|bod[øo]|haugesund|lillestr[øo]m|asker|b[æa]rum|lysaker|fornebu|kongsberg|"
                    r"t[øo]nsberg|sandefjord|moss|hamar|gj[øo]vik|lillehammer|molde|arendal|larvik|skien|porsgrunn|horten|"
                    r"harstad|narvik|alta|hammerfest|mo i rana|steinkjer|levanger|stord|f[øo]rde|sogndal|kristiansund)\b", re.I)
FOREIGN_FORMS = {"ab", "aps", "oy", "oyj", "gmbh", "ltd", "limited", "inc", "llc", "plc", "bv", "sarl", "sas", "srl", "corp", "a/s"}
GENERIC = {"og", "the", "i", "pa", "and"}
DEPT = {"avd", "avdeling", "divisjon", "division", "region", "kontor", "office", "butikk", "store", "sentrum", "senter", "norge"}


# ----------------------------------------------------------------------------------------------
# identity

def _sig(name: str) -> tuple[str, ...]:
    toks = name_tokens(name)
    toks = ["norge" if t == "norway" else t for t in toks]
    return tuple(t for t in toks if t not in GENERIC)


def _has_form(name: str) -> bool:
    raw = name_tokens(name, drop_forms=False)
    return bool(raw) and (raw[-1] in LEGAL_FORMS or any(t in FOREIGN_FORMS for t in raw))


def _contiguous(small: tuple, big: tuple) -> bool:
    n = len(small)
    return any(big[i:i + n] == small for i in range(len(big) - n + 1))


class Who:
    """Whether a name on a recruitment platform is our legal entity."""

    def __init__(self, ent: dict, subunits: list | None = None, orgnr: str = "") -> None:
        self.name = ent.get("navn", "")
        self.legal = _sig(self.name)
        self.compact = "".join(self.legal)
        self.own = {orgnr or ent.get("organisasjonsnummer", "")} | {u.get("organisation_number") for u in subunits or []
                                                                     if u.get("organisation_number")}
        self.own.discard("")

    def match(self, name: str | None) -> bool:
        if not name or not self.legal:
            return False
        n = _sig(name)
        if not n:
            return False
        if n == self.legal or "".join(n) == self.compact:
            return True
        raw = name_tokens(name, drop_forms=False)
        if any(t in FOREIGN_FORMS for t in raw) or re.search(r"\b(ab|aps|gmbh|ltd|inc|oy)\b", name.lower()):
            return False  # a foreign company
        if raw and raw[-1] in LEGAL_FORMS:
            return False  # another registered entity's full name ("X Bergen AS" is not "X AS")
        L = self.legal
        if len(L) >= 2 and _contiguous(L, n) and all(t in DEPT or NORWAY.fullmatch(t) for t in n if t not in L):
            return True  # our name plus a place or a department word ("Nille AS Moss", "Firma Bergen avdeling")
        if len(n) >= 2 and _contiguous(n, L) and len(L) == len(n) + 1 and L[-1] == "norge":
            return True  # our name without its country suffix ("Aimo Park" for AIMO PARK NORWAY AS)
        return False

    def other_orgnr(self, text: str) -> bool:
        """True when the text names a valid organisation number that is not ours."""
        for num, _ in sp.orgnr_mentions(text or ""):
            if num not in self.own:
                return True
        return False


# ----------------------------------------------------------------------------------------------
# small helpers

def _iso(v) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and v > 10**11:  # epoch milliseconds
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date().isoformat()
    from ..extract import _iso as iso
    return iso(str(v))


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", fold(t or "")).strip()


def _today() -> str:
    return date.today().isoformat()


@dataclass
class Posting:
    platform: str
    id: str
    title: str
    url: str
    published: str | None = None
    deadline: str | None = None
    deadline_text: str | None = None
    location: str = ""
    country: str | None = None
    employer: str | None = None
    status: str = "open"
    orgnr: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class Target:
    platform: str
    url: str          # first URL to read
    key: str          # account identity for de-duplication
    via: dict         # company-owned page that links or embeds it
    extra: dict = field(default_factory=dict)


def _via_page(page: sp.Page, span: str) -> dict:
    return {"url": page.final_url, "retrieved_at": page.retrieved_at, "sha256": page.sha256, "status": page.status,
            "span": span, "host": page.host()}


def _via_fetched(f, span: str) -> dict:
    return {"url": f.final_url, "retrieved_at": f.retrieved_at, "sha256": f.sha256, "status": f.status, "span": span,
            "host": (urlsplit(f.final_url).hostname or "").lower()}


# ----------------------------------------------------------------------------------------------
# finding recruitment platforms in links and raw HTML

SKIP_SUB = {"www", "app", "apply", "api", "cdn", "scripts", "images", "assets", "static", "support", "help", "cp-analytics",
            "widget", "widgets", "media", "blog", "status"}
RX = {
    "teamtailor": re.compile(r"https?://([a-z0-9-]+)\.teamtailor\.com", re.I),
    "recman": re.compile(r"https?://([a-z0-9-]+)\.recman\.(page|io|no)\b", re.I),
    "recman_apply": re.compile(r"https?://apply\.recman\.page/job_post\.php\?id=(\d+)", re.I),
    "reachmee": re.compile(r"https?://(web\d+\.reachmee\.com)/ext/(I\d+)/(\d+)/(?:main|job|apply)\?([^\"'<>\s]+)", re.I),
    "reachmee_js": re.compile(r"https?://(web\d+\.reachmee\.com)/customerjs/(I\d+)-(\d+)-(\d+)\.js", re.I),
    "jobylon_company": re.compile(r"jbl_company_id\s*=\s*['\"]?(\d+)|(?:emp|cdn)\.jobylon\.com/(?:jobs/)?companies/(\d+)", re.I),
    "jobylon_group": re.compile(r"jbl_group_id\s*=\s*['\"]?(\d+)", re.I),
    "jobylon_ad": re.compile(r"https?://emp\.jobylon\.com/jobs/(\d+)-[a-z0-9-]+/?", re.I),
    "jobbnorge_ad": re.compile(r"jobbnorge\.no/(?:ledige-stillinger/)?stilling/(\d+)", re.I),
    "easycruit": re.compile(r"https?://([a-z0-9-]+)\.easycruit\.com", re.I),
    "mojob_ad": re.compile(r"https?://jobs\.mojob\.io/(\d+)/?", re.I),
    "lever": re.compile(r"https?://jobs\.(eu\.)?lever\.co/([A-Za-z0-9._-]+)", re.I),
    "greenhouse": re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)", re.I),
    "recruitee": re.compile(r"https?://([a-z0-9-]+)\.recruitee\.com", re.I),
}


def scan(text: str, via: dict) -> tuple[list[Target], dict[str, list[str]]]:
    """Recruitment targets named in a page's raw HTML or links. Returns (targets, single-ad URLs by platform)."""
    text = htmllib.unescape(text or "")
    out: list[Target] = []
    ads: dict[str, list[str]] = {"mojob": [], "jobylon": [], "jobbnorge": []}

    def add(t: Target) -> None:
        if t.key not in [x.key for x in out]:
            out.append(t)
    for m in RX["teamtailor"].finditer(text):
        sub = m.group(1).lower()
        if sub not in SKIP_SUB:
            origin = f"https://{sub}.teamtailor.com"
            add(Target("teamtailor", origin + "/jobs.rss", "teamtailor:" + sub, via))
    for m in RX["recman"].finditer(text):
        sub = m.group(1).lower()
        if sub not in SKIP_SUB:
            add(Target("recman", f"https://{sub}.recman.{m.group(2).lower()}/jobs", "recman:" + sub, via))
    for m in RX["recman_apply"].finditer(text):
        add(Target("recman", m.group(0), "recman-ad:" + m.group(1), via, {"resolve": True}))
    for m in RX["reachmee"].finditer(text):
        q = parse_qs(m.group(4))
        site, val = (q.get("site") or [""])[0], (q.get("validator") or [""])[0]
        if site and val:
            lang = (q.get("lang") or ["NO"])[0]
            url = f"https://{m.group(1)}/ext/{m.group(2)}/{m.group(3)}/main?site={site}&validator={val}&lang={lang}"
            add(Target("reachmee", url, f"reachmee:{m.group(2)}/{m.group(3)}/{site}", via))
    for m in RX["reachmee_js"].finditer(text):
        add(Target("reachmee", m.group(0), f"reachmee:{m.group(2)}/{m.group(3)}/{m.group(4)}", via, {"customerjs": True}))
    for m in RX["jobylon_company"].finditer(text):
        cid = m.group(1) or m.group(2)
        add(Target("jobylon", f"https://cdn.jobylon.com/jobs/companies/{cid}/embed/v2/?target=jobylon-jobs-widget&page_size=50",
                   "jobylon:c" + cid, via))
    for m in RX["jobylon_group"].finditer(text):
        add(Target("jobylon", f"https://cdn.jobylon.com/jobs/company-groups/{m.group(1)}/embed/v2/?target=jobylon-jobs-widget&page_size=50",
                   "jobylon:g" + m.group(1), via))
    for m in RX["jobylon_ad"].finditer(text):
        ads["jobylon"].append(m.group(0))
    for m in RX["jobbnorge_ad"].finditer(text):
        ads["jobbnorge"].append(m.group(1))
    for m in RX["easycruit"].finditer(text):
        sub = m.group(1).lower()
        if sub not in SKIP_SUB:
            add(Target("easycruit", f"https://{sub}.easycruit.com/export/xml/vacancy/list.xml", "easycruit:" + sub, via))
    for m in RX["mojob_ad"].finditer(text):
        ads["mojob"].append(f"https://jobs.mojob.io/{m.group(1)}/")
    for m in RX["lever"].finditer(text):
        acct = m.group(2)
        api = "https://api.eu.lever.co" if m.group(1) else "https://api.lever.co"
        add(Target("lever", f"{api}/v0/postings/{acct}?mode=json", "lever:" + acct.lower(), via))
    for m in RX["greenhouse"].finditer(text):
        tok = m.group(1)
        if tok.lower() not in ("embed", "v1", "jobs"):
            add(Target("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs", "greenhouse:" + tok.lower(), via,
                       {"board": f"https://boards-api.greenhouse.io/v1/boards/{tok}"}))
    for m in RX["recruitee"].finditer(text):
        sub = m.group(1).lower()
        if sub not in SKIP_SUB:
            add(Target("recruitee", f"https://{sub}.recruitee.com/api/offers/", "recruitee:" + sub, via))
    for k in ads:
        ads[k] = list(dict.fromkeys(ads[k]))
    return out, ads


def not_read(text: str) -> list[str]:
    return [k for k, (rx, _) in NOT_READ.items() if rx.search(text or "")]


# ----------------------------------------------------------------------------------------------
# platform parsers (pure; tested on saved fixtures)

def _xml_text(el, tag: str, ns: str = "") -> str:
    x = el.find(ns + tag)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_teamtailor_rss(body: bytes) -> tuple[str, list[Posting]]:
    root = ET.fromstring(body)
    ch = root.find("channel")
    if ch is None:
        return "", []
    account = _xml_text(ch, "title")
    ns = "{https://teamtailor.com/locations}"
    out = []
    for it in ch.findall("item"):
        link = _xml_text(it, "link")
        m = re.search(r"/jobs/(\d+)", link)
        locs = it.findall(f"{ns}locations/{ns}location")
        cities = [(_xml_text(x, "city", ns) or _xml_text(x, "name", ns)) for x in locs]
        countries = {(_xml_text(x, "country", ns) or "").lower() for x in locs} - {""}
        out.append(Posting("teamtailor", m.group(1) if m else link, _xml_text(it, "title"), link,
                           published=_iso(_xml_text(it, "pubDate")), location=", ".join(c for c in dict.fromkeys(cities) if c),
                           country="NO" if not countries or countries & {"norway", "norge", "no"} else "/".join(sorted(countries)),
                           extra={"department": _xml_text(it, "department", ns) or None}))
    return account, out


def recman_token(html: str) -> tuple[str, str]:
    tok = re.search(r'name="csrf-token"\s+content="([^"]+)"', html or "")
    web = re.search(r'id="ra-webpage"\s+value="([^"]*)"', html or "")
    return (tok.group(1) if tok else ""), (web.group(1) if web else "")


def parse_recman_jobs(data: dict, origin: str) -> list[Posting]:
    out = []
    for j in ((data.get("data") or {}).get("job_posts") or []):
        if j.get("EmployeesOnly"):
            continue  # internal posting
        due = _iso(j.get("Expire"))
        out.append(Posting("recman", str(j.get("AdID")), clip(j.get("Name") or j.get("JobTitle") or "", 160),
                           f"{origin}/job/{j.get('AdID')}", published=_iso(j.get("Created")), deadline=due,
                           deadline_text=j.get("Deadline") if isinstance(j.get("Deadline"), str) else None,
                           location=j.get("Place") or "", employer=j.get("EmpName"),
                           extra={"job_title": j.get("JobTitle")}))
    return out


def reachmee_main_from_js(js: str, host: str) -> str | None:
    def g(k: str) -> str:
        m = re.search(rf"var\s+{k}\s*=\s*'([^']*)'", js)
        return m.group(1) if m else ""
    iid, cust, site, val, lang = g("iid"), g("customer"), g("site"), g("validator"), g("langDef") or "NO"
    base = g("iFrameUrl") or f"https://{host}/ext/"
    if not (iid and cust and site and val) or "reachmee.com" not in base:
        return None
    return f"{base.rstrip('/')}/{iid}/{cust}/main?site={site}&validator={val}&lang={lang}"


def parse_reachmee_list(html: str, url: str) -> tuple[str, list[Posting]]:
    from selectolax.parser import HTMLParser
    tree = HTMLParser(html)
    t = tree.css_first("title")
    account = re.split(r"\s+\|\s+", (t.text() if t else "").strip())[0].strip()
    out = []
    rows = tree.css("table#jobsTable tbody tr") or tree.css("table.jobsTableClass tbody tr")
    for tr in rows:
        a = tr.css_first("a[href]")
        if not a:
            continue
        href = urljoin(url, a.attributes.get("href") or "")
        jid = (parse_qs(urlsplit(href).query).get("job_id") or [""])[0]
        tds = tr.css("td")
        due = None
        for s in tr.css("span[style]"):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", (s.text() or "").strip()):
                due = s.text().strip()
        loc = tds[1].text().strip() if len(tds) >= 3 else ""
        out.append(Posting("reachmee", jid or href, clip(a.text(), 160), href, deadline=due, location=loc))
    return account, out


def parse_jobylon_embed(html: str) -> list[Posting]:
    m = re.search(r"JBL\.embed_v2\['jobs'\]\s*=\s*\[(.*?)\];\s*\n", html, re.S)
    body = m.group(1) if m else ""
    out = []
    for block in re.split(r"\n\s*\{\s*\n\s*id:", body)[1:]:
        def g(k: str) -> str:
            mm = re.search(rf"\b{k}:\s*'((?:[^'\\]|\\.)*)'", block)
            if not mm:
                return ""
            v = re.sub(r"\\u([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), mm.group(1)).replace("\\'", "'")
            return htmllib.unescape(v)
        jid = re.match(r"\s*'(\d+)'", block)
        if not jid:
            continue
        url = "https://emp.jobylon.com" + g("url")
        out.append(Posting("jobylon", jid.group(1), clip(g("title"), 160), url, published=_iso(g("published_date")),
                           deadline=_iso(g("to_date")), location=g("locations_text"), employer=g("company"),
                           extra={"company_id": g("company_id")}))
    return out


def parse_easycruit_xml(body: bytes) -> list[Posting]:
    root = ET.fromstring(body)
    ns = "{urn:EasyCruit}"
    out = []
    for v in root.iter(ns + "Vacancy"):
        ver = v.find(f"{ns}Versions/{ns}Version")
        dep = v.find(f"{ns}Departments/{ns}Department")
        if ver is None:
            continue
        url = _xml_text(dep, "VacancyURL", ns) if dep is not None else ""
        due = _iso(_xml_text(ver, "ApplicationDeadline", ns)) or _iso(v.get("date_end"))
        out.append(Posting("easycruit", v.get("id") or url, clip(_xml_text(ver, "Title", ns), 160), url,
                           published=_iso(v.get("date_start")), deadline=due,
                           location=_xml_text(ver, "Location", ns), employer=_xml_text(ver, "AlternativeCompanyName", ns) or None,
                           extra={"department": _xml_text(dep, "Name", ns) if dep is not None else None}))
    return out


def parse_jobbnorge(data: dict) -> list[Posting]:
    out = []
    for j in data.get("jobs") or []:
        emp = j.get("department") if j.get("regardDepartmentAsEmployer") else j.get("employer")
        locs = ", ".join(dict.fromkeys(x.get("area") or x.get("municipality") or "" for x in j.get("locations") or [] if x))
        foreign = any(x.get("isDomestic") is False for x in j.get("locations") or [])
        out.append(Posting("jobbnorge", str(j.get("id")), clip(j.get("title") or "", 160),
                           j.get("link") or f"https://www.jobbnorge.no/ledige-stillinger/stilling/{j.get('id')}",
                           published=_iso(j.get("publicationDate")), deadline=_iso(j.get("deadline")),
                           deadline_text=j.get("deadline"), location=locs.strip(", "), employer=emp,
                           country="abroad" if foreign else "NO", extra={"employer_id": j.get("employerID")}))
    return out


def parse_lever(data: list) -> list[Posting]:
    out = []
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        out.append(Posting("lever", j.get("id", ""), clip(j.get("text") or "", 160), j.get("hostedUrl") or "",
                           published=_iso(j.get("createdAt")), location=cat.get("location") or "",
                           country=(j.get("country") or "").upper() or None))
    return out


def parse_greenhouse(data: dict) -> list[Posting]:
    out = []
    for j in data.get("jobs") or []:
        out.append(Posting("greenhouse", str(j.get("id")), clip(j.get("title") or "", 160), j.get("absolute_url") or "",
                           published=_iso(j.get("first_published")), deadline=_iso(j.get("application_deadline")),
                           location=(j.get("location") or {}).get("name") or "", employer=j.get("company_name")))
    return out


def parse_recruitee(data: dict) -> list[Posting]:
    out = []
    for j in data.get("offers") or []:
        out.append(Posting("recruitee", str(j.get("id")), clip(j.get("title") or "", 160), j.get("careers_url") or "",
                           published=_iso(j.get("published_at") or j.get("created_at")), deadline=_iso(j.get("close_at")),
                           location=", ".join(x for x in (j.get("city"), j.get("country")) if x),
                           country=(j.get("country_code") or "").upper() or None, employer=j.get("company_name"),
                           status="open" if j.get("status") in (None, "published") else "closed"))
    return out


def jsonld_postings(page: sp.Page, platform: str = "site") -> list[Posting]:
    out = []
    for node in page.jsonld:
        t = node.get("@type")
        if "JobPosting" not in (t if isinstance(t, list) else [t]) or not node.get("title"):
            continue
        org = node.get("hiringOrganization") or {}
        if isinstance(org, list):
            org = org[0] if org else {}
        if isinstance(org, str):
            org = {"name": org}
        ids = " ".join(str(org.get(k) or "") for k in ("identifier", "taxID", "vatID", "leiCode"))
        ident = node.get("identifier")
        if isinstance(ident, dict) and re.search(r"org\.?\s*nr|organisasjonsnummer|organi[sz]ation number", str(ident.get("name") or ""), re.I):
            ids += " " + str(ident.get("value") or "")
        loc = node.get("jobLocation")
        loc = loc[0] if isinstance(loc, list) and loc else loc
        addr = (loc or {}).get("address") if isinstance(loc, dict) else None
        city = country = ""
        if isinstance(addr, dict):
            city = addr.get("addressLocality") or addr.get("streetAddress") or ""
            country = addr.get("addressCountry") or ""
            if isinstance(country, dict):
                country = country.get("name") or ""
        own_url = bool(node.get("url"))
        url = node.get("url") or page.final_url
        jid = str((ident or {}).get("value") if isinstance(ident, dict) else "") or url
        orgnr = next((n for n, _ in sp.orgnr_mentions(ids)), None) if ids.strip() else None
        if not own_url and jid == url:
            jid = f"{url}#{_norm_title(str(node['title']))[:60]}"  # several ads described on one page
        out.append(Posting(platform, jid, clip(str(node["title"]), 160), str(url), published=_iso(node.get("datePosted")),
                           deadline=_iso(node.get("validThrough")), location=str(city), employer=org.get("name"),
                           country=str(country).upper() or None, orgnr=orgnr, extra={"shared_url": not own_url}))
    return out


CAREER_INFO = re.compile(r"^(jobbe som|jobb(?:e)? hos|karriere|om jobben|hvorfor|why work|working (?:at|with)|life at|livet i)|"
                         r"/(jobbe-som|hvorfor|why-work|life-at|working-at|working-with-us)[-/]", re.I)
GENERIC_ANCHOR = re.compile(r"^(view|see|read|les|se|s[øo]k|apply|mer|more|details|detaljer|klikk|click|g[åa] til)\b", re.I)


def _ad_title(page: sp.Page, anchor: str, who: Who) -> str:
    segs = [x.strip() for x in re.split(r"\s+[|\-–—]\s+", page.title or "") if x.strip()]
    while len(segs) > 1 and (who.match(segs[-1]) or len(segs[-1]) < 3):
        segs.pop()  # the site-name suffix
    cands = [" - ".join(segs), anchor or ""]
    slug = urlsplit(page.final_url).path.rstrip("/").split("/")[-1]
    if slug.count("-") >= 1 and not slug.isdigit():
        cands.append(slug.replace("-", " ").strip().capitalize())
    for c in cands:
        c = clip(c, 160)
        if len(c) >= 8 and not GENERIC_ANCHOR.search(c) and not who.match(c) and not LIST_ANCHOR.search(c):
            return c
    return ""


def own_site_ad(page: sp.Page, anchor: str, who: Who) -> Posting | None:
    """A plain job ad on the company's own site: a page under the careers page that reads like an ad,
    names our company, and names no other employer and no other organisation number."""
    if not AD_MARKERS.search(page.text or ""):
        return None
    title = _ad_title(page, anchor, who)
    if not title or OPEN_APPLICATION.search(title) or CAREER_INFO.search(title) or CAREER_INFO.search(urlsplit(page.final_url).path):
        return None
    if OPEN_APPLICATION.search(page.text or ""):
        return None  # a page about working here that invites open applications, not one ad
    for t in (title, anchor or ""):
        hos = re.search(r"\b(?:hos|at|with)\s+([A-ZÆØÅ][\wÆØÅæøå&.\-]*(?:\s+[A-ZÆØÅ][\wÆØÅæøå&.\-]*){0,3})", t)
        if hos and not NORWAY.search(fold(hos.group(1))) and not who.match(hos.group(1)):
            return None  # "Ledig stilling hos Lekia" on a shopping centre's site
    emp = re.search(r"(?:arbeidsgiver|employer|selskap|company)\s*:\s*([^\n]{2,60})", page.text or "", re.I)
    if emp and not who.match(emp.group(1)):
        return None
    if who.other_orgnr(page.text):
        return None
    words = set(re.findall(r"[a-z0-9]+", fold(page.text or "")))
    if not set(who.legal) <= words:
        return None  # the ad itself names the company
    due = None
    m = re.search(r"s[øo]knadsfrist\s*:?\s*([^\n]{0,40})", page.text or "", re.I)
    if m:
        due = _iso(m.group(1))
    return Posting("site", page.final_url, title, page.final_url, deadline=due, employer=who.name)


def _children(pg: sp.Page, site_label: str) -> list[tuple[str, str]]:
    """Same-site links one level below a careers or vacancy-list page (individual ads, if any)."""
    parent = urlsplit(pg.final_url).path.rstrip("/")
    if not (LIST_PATH.search(parent) or CAREERS_PATH.search(parent)):
        return []
    out: list[tuple[str, str]] = []
    for u, text in pg.links:
        s = urlsplit(u)
        child = s.path.rstrip("/")
        u = u.split("#")[0]
        if _label(s.hostname or "") == site_label and child.startswith(parent + "/") and child.count("/") == parent.count("/") + 1 \
                and not re.search(r"\.(pdf|jpe?g|png|docx?)$", child, re.I) and u not in [x[0] for x in out]:
            out.append((u, text or ""))
    return out


def _list_links(pg: sp.Page, site_label: str) -> list[str]:
    """Same-site links from a careers page to its vacancy list ("Ledige stillinger", "Se alle stillinger")."""
    out = []
    here = urlsplit(pg.final_url).path.rstrip("/")
    for u, text in pg.links:
        s = urlsplit(u)
        if _label(s.hostname or "") != site_label or u.split("#")[0].rstrip("/") == pg.final_url.rstrip("/"):
            continue
        if s.path.rstrip("/").startswith(here + "/") and not LIST_ANCHOR.search(text or ""):
            continue  # a page under this one is an ad, not the list
        if LIST_PATH.search(s.path) or LIST_ANCHOR.search(text or ""):
            out.append(u.split("#")[0])
    return list(dict.fromkeys(out))


# ----------------------------------------------------------------------------------------------
# the source

class Careers(Source):
    name = "careers"
    families = ["jobs"]
    late = True

    def __init__(self) -> None:
        self.cache: dict[str, asyncio.Future] = {}
        self.jobbnorge_lock = asyncio.Lock()
        self.jobbnorge: dict | None = None
        self.stats = {"companies_checked": 0, "companies_with_targets": 0, "targets_read": 0, "companies_published": 0,
                      "postings_published": 0, "skipped_other_employer": 0, "skipped_duplicate": 0, "skipped_expired": 0,
                      "skipped_abroad": 0, "by_platform": {}, "not_read": {}}

    async def _get(self, ctx, url: str, **kw):
        """Platform pages are fetched once per run (a group's career page is shared by its companies)."""
        key = url + json.dumps(kw.get("headers") or {}, sort_keys=True)
        if key not in self.cache:
            self.cache[key] = asyncio.ensure_future(ctx.client.get(self.name, url, timeout=REQ_TIMEOUT, **kw))
        return await asyncio.shield(self.cache[key])

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        if not sites:
            return
        p.checked_source("jobs", "recruitment pages linked from the verified website")
        self.stats["companies_checked"] += 1
        who = Who(ent, subunits, p.orgnr)
        found: list[tuple[Posting, dict, object]] = []  # posting, company-owned link, platform response
        # NAV postings are added first, so the same ad is not published twice
        nav_done = p.notes.setdefault("_nav_done", asyncio.Event()) if any(s.name == "nav_jobs" for s in ctx.sources) else None
        task = asyncio.ensure_future(self._collect(ctx, who, sites, found))
        done, _ = await asyncio.wait([task], timeout=COMPANY_SECONDS)
        if not done:
            task.cancel()
            p.error(self.name, f"recruitment pages: stopped after {COMPANY_SECONDS:.0f}s; partial results kept")
        elif task.exception() is not None:
            p.error(self.name, repr(task.exception()))
        if nav_done is not None:
            try:
                await asyncio.wait_for(nav_done.wait(), timeout=900)
            except asyncio.TimeoutError:
                pass
        self._publish(p, who, found)

    async def _collect(self, ctx, who: Who, sites: list, found: list) -> None:
        targets: list[Target] = []
        ads: dict[str, list[tuple[str, dict]]] = {"mojob": [], "jobylon": [], "jobbnorge": [], "site": []}
        fetched: set[str] = set()
        for site in sites[:2]:
            label = _label(site.home.host())
            # 1. recruitment links on every crawled page, and JobPosting JSON-LD
            for page in site.pages:
                hrefs = "\n".join(u for u, _ in page.links)
                self._add(targets, ads, hrefs, _via_page(page, f"link on {page.final_url}"))
                for post in jsonld_postings(page):
                    found.append((post, _via_page(page, f"JobPosting JSON-LD on {page.final_url}"), None))
            # 2. careers pages again as raw HTML (iframes and widget scripts are not links), and a career subdomain
            careers = [pg.final_url for pg in site.pages[1:] if CAREERS_PATH.search(urlsplit(pg.final_url).path)][:2]
            subs = [u for page in site.pages for u, _ in page.links
                    if CAREER_HOST.match((urlsplit(u).hostname or "").lower()) and _label(urlsplit(u).hostname or "") == label]
            todo = [u for u in dict.fromkeys(careers + subs[:1]) if u not in fetched]
            fetched.update(todo)
            pages = [x for x in await asyncio.gather(*(self._page(ctx, u) for u in todo)) if x]
            for f, pg in pages:
                self._scan_page(f, pg, targets, ads, found, label)
            # 3. one hop from the careers page to its vacancy list
            if not targets and not found and not any(ads[k] for k in ("mojob", "jobylon", "jobbnorge")):
                hop = [u for f, pg in pages for u in _list_links(pg, label) if u not in fetched][:1]
                fetched.update(hop)
                for res in await asyncio.gather(*(self._page(ctx, u) for u in hop)):
                    if res:
                        self._scan_page(res[0], res[1], targets, ads, found, label)
        if targets or any(ads.values()):
            self.stats["companies_with_targets"] += 1
        targets = [t for t in targets if t.platform in ENABLED]
        await asyncio.gather(*(self._read(ctx, t, found) for t in targets[:MAX_TARGETS]), return_exceptions=True)
        jobs = []
        budget = MAX_AD_PAGES
        for platform in [x for x in ("mojob", "jobylon") if x in ENABLED]:
            for u, via in ads[platform][:max(0, budget)]:
                jobs.append(self._ad_page(ctx, platform, u, via, found, who))
                budget -= 1
        if ads["jobbnorge"]:
            jobs.append(self._jobbnorge(ctx, ads["jobbnorge"], found, who))
        if not targets and not found and not jobs:
            seen: set[str] = set()
            for u, via in ads["site"]:
                if u in seen or u in fetched or budget <= 0:
                    continue
                seen.add(u)
                budget -= 1
                jobs.append(self._ad_page(ctx, "site", u, via, found, who))
        await asyncio.gather(*jobs, return_exceptions=True)

    def _add(self, targets: list, ads: dict, text: str, via: dict, extra: list | None = None) -> None:
        for k in not_read(text):
            self.stats["not_read"][k] = self.stats["not_read"].get(k, 0) + 1
        ts, a = scan(text, via)
        for t in (extra or []) + ts:
            if t.key not in [x.key for x in targets]:
                targets.append(t)
        for k, items in a.items():
            for u in items:
                if u not in [x[0] for x in ads[k]]:
                    ads[k].append((u, via))

    def _scan_page(self, f, pg: sp.Page, targets: list, ads: dict, found: list, label: str) -> None:
        raw = f.text()
        via = _via_fetched(f, f"recruitment link or embed on {f.final_url}")
        # a career site on the company's own domain run by Teamtailor (karriere.firma.no/jobs.rss)
        tt = [Target("teamtailor", feed, "teamtailor:" + (urlsplit(feed).hostname or ""), via) for feed in pg.feeds
              if feed.rstrip("/").endswith("/jobs.rss") and "teamtailor" in raw.lower()]
        self._add(targets, ads, raw, via, tt)
        for post in jsonld_postings(pg):
            found.append((post, _via_fetched(f, f"JobPosting JSON-LD on {f.final_url}"), f))
        for u, text in _children(pg, label):
            ads["site"].append((u, {"anchor": text, **_via_fetched(f, f"link '{clip(text, 60)}' on {f.final_url}")}))

    async def _page(self, ctx, url: str):
        f = await ctx.client.get(self.name, url, timeout=REQ_TIMEOUT)
        if not f.ok or "html" not in (f.content_type or "html").lower():
            return None
        pg = sp.parse(f.text(), url, f.final_url)
        pg.sha256, pg.retrieved_at, pg.status = f.sha256, f.retrieved_at, f.status
        return f, pg

    async def _read(self, ctx, t: Target, found: list) -> None:
        self.stats["targets_read"] += 1
        bp = self.stats["by_platform"].setdefault(t.platform, {"accounts": 0, "postings": 0})
        bp["accounts"] += 1
        posts: list[Posting] = []
        account = ""
        f = None
        if t.platform == "teamtailor":
            f = await self._get(ctx, t.url, headers={"Accept": "application/rss+xml"})
            if f.ok:
                account, posts = parse_teamtailor_rss(f.body)
        elif t.platform == "recman":
            url = t.url
            if t.extra.get("resolve"):
                r = await self._get(ctx, url)
                if not r.ok:
                    return
                s = urlsplit(r.final_url)
                url = f"{s.scheme}://{s.netloc}/jobs"
            page = await self._get(ctx, url)
            if not page.ok:
                return
            tok, web = recman_token(page.text())
            s = urlsplit(page.final_url)
            origin = f"{s.scheme}://{s.netloc}"
            if not tok:
                return
            f = await ctx.client.get(self.name, origin + "/api/jobs", timeout=REQ_TIMEOUT,
                                     headers={"X-CSRF-TOKEN": tok, "Accept": "application/json"})
            if f.ok:
                try:
                    posts = parse_recman_jobs(json.loads(f.body), origin)
                except ValueError:
                    posts = []
                account = web
        elif t.platform == "reachmee":
            url = t.url
            if t.extra.get("customerjs"):
                js = await self._get(ctx, url)
                url = reachmee_main_from_js(js.text(), urlsplit(url).hostname or "") if js.ok else None
                if not url:
                    return
            f = await self._get(ctx, url)
            if f.ok:
                account, posts = parse_reachmee_list(f.text(), f.final_url)
        elif t.platform == "jobylon":
            f = await self._get(ctx, t.url)
            if f.ok:
                posts = parse_jobylon_embed(f.text())
        elif t.platform == "easycruit":
            f = await self._get(ctx, t.url)
            if f.ok:
                try:
                    posts = parse_easycruit_xml(f.body)
                except ET.ParseError:
                    posts = []
        elif t.platform == "lever":
            f = await self._get(ctx, t.url, headers={"Accept": "application/json"})
            if f.ok:
                posts = parse_lever(json.loads(f.body))
                account = t.key.split(":", 1)[1]
                for x in posts:
                    x.extra["norway_only"] = True
        elif t.platform == "greenhouse":
            b = await self._get(ctx, t.extra["board"], headers={"Accept": "application/json"})
            f = await self._get(ctx, t.url, headers={"Accept": "application/json"})
            if f.ok:
                posts = parse_greenhouse(json.loads(f.body))
                account = (json.loads(b.body).get("name") if b.ok else "") or ""
                for x in posts:
                    x.extra["norway_only"] = True
        elif t.platform == "recruitee":
            f = await self._get(ctx, t.url, headers={"Accept": "application/json"})
            if f.ok:
                posts = parse_recruitee(json.loads(f.body))
        if f is None or not f.ok:
            return
        for x in posts:
            x.extra.setdefault("account", account)
            found.append((x, t.via, f))

    async def _ad_page(self, ctx, platform: str, url: str, via: dict, found: list, who: Who) -> None:
        res = await self._page(ctx, url)
        if not res:
            return
        f, pg = res
        if platform == "site":
            post = own_site_ad(pg, via.get("anchor") or "", who)
            if post:
                found.append((post, via, f))
            return
        m = re.search(r"/(\d+)", urlsplit(f.final_url).path)
        for post in jsonld_postings(pg, platform):
            post.url = f.final_url  # the ad page itself
            post.id = m.group(1) if m else f.final_url
            found.append((post, via, f))

    async def _jobbnorge(self, ctx, ids: list[tuple[str, dict]], found: list, who: Who) -> None:
        async with self.jobbnorge_lock:
            if self.jobbnorge is None:
                f = await ctx.client.get(self.name, JOBBNORGE_FEED, timeout=COMPANY_SECONDS, headers={"Accept": "application/json"})
                posts = []
                if f.ok:
                    try:
                        posts = parse_jobbnorge(json.loads(f.body))
                    except ValueError:
                        posts = []
                if not posts:
                    return  # unavailable now; the next company tries again
                self.jobbnorge = {"fetched": f, "by_id": {x.id: x for x in posts}}
        f, by_id = self.jobbnorge["fetched"], self.jobbnorge["by_id"]
        employers = set()
        for jid, via in ids:
            x = by_id.get(jid)
            if x and who.match(x.employer):
                employers.add(x.extra.get("employer_id"))
        via = ids[0][1]
        listed = {jid for jid, _ in ids}
        for x in by_id.values():
            if x.id in listed or (x.extra.get("employer_id") in employers and employers):
                found.append((x, via, f))

    # ------------------------------------------------------------------------------------------
    def _publish(self, p, who: Who, found: list) -> None:
        today = _today()
        have_urls = set()
        have_titles: list[tuple[str, str | None]] = []
        for c in p.family_claims("jobs"):
            if c.field == "job_posting" and isinstance(c.value, dict):
                have_urls.add(str(c.value.get("url") or "").lower().rstrip("/"))
                have_titles.append((_norm_title(c.value.get("title") or ""), c.value.get("published") or c.effective_date))
        published = 0
        for post, via, f in found:
            if published >= MAX_POSTINGS:
                break
            if post.platform not in ENABLED:
                continue
            if not post.title or not post.url:
                continue
            name = post.employer or post.extra.get("account") or ""
            if post.orgnr and post.orgnr not in who.own:
                self.stats["skipped_other_employer"] += 1
                continue
            if not (post.orgnr in who.own if post.orgnr else False) and not who.match(name):
                self.stats["skipped_other_employer"] += 1
                continue
            if post.platform != "site" and OPEN_APPLICATION.search(post.title):
                continue
            if post.deadline and post.deadline < today:
                self.stats["skipped_expired"] += 1
                continue
            if post.country and post.country not in ("NO", "NOR", "NORWAY", "NORGE"):
                self.stats["skipped_abroad"] += 1
                continue
            if post.extra.get("norway_only") and not NORWAY.search(post.location or ""):
                self.stats["skipped_abroad"] += 1
                continue
            u = post.url.lower().rstrip("/")
            nt = _norm_title(post.title)
            if (u in have_urls and not post.extra.get("shared_url")) or any(nt == t and (not d or not post.published or abs(_days(d, post.published)) <= 7)
                                     for t, d in have_titles):
                self.stats["skipped_duplicate"] += 1
                continue
            have_urls.add(u)
            have_titles.append((nt, post.published))
            self._claim(p, who, post, via, f)
            published += 1
            bp = self.stats["by_platform"].setdefault(post.platform, {"accounts": 0, "postings": 0})
            bp["postings"] += 1
        if published:
            self.stats["companies_published"] += 1
            self.stats["postings_published"] += published

    def _claim(self, p, who: Who, post: Posting, via: dict, f) -> None:
        label = LABEL.get(post.platform, post.platform)
        account = post.extra.get("account") or ""
        value = {"title": post.title, "url": post.url, "status": post.status, "employer": post.employer or account or None,
                 "location": post.location or None, "published": post.published, "application_due": post.deadline,
                 "source": label if post.platform != "site" else "company careers page", "platform": post.platform}
        if post.deadline_text and not post.deadline:
            value["application_due_text"] = clip(post.deadline_text, 80)
        if account and account != value["employer"]:
            value["account"] = account
        if post.platform != "site":
            value["platform_id"] = post.id
        value = {k: v for k, v in value.items() if v not in (None, "")}
        basis = (f"employer {post.employer}" if post.employer else f"account {account}") if not post.orgnr else f"orgnr {post.orgnr}"
        ev = []
        if f is not None and getattr(f, "final_url", "") != via.get("url"):
            ev.append(Evidence(f.url, "public_job_board" if post.platform != "site" else "company_owned", f.retrieved_at, f.sha256,
                               f"{label}: {post.title} · {basis} · posted {post.published or 'n/a'} · due {post.deadline or 'n/a'}",
                               f"{post.platform}_listing", final_url=f.final_url, http_status=f.status,
                               source_name=label if post.platform != "site" else (urlsplit(f.final_url).hostname or "")))
        ev.append(Evidence(via["url"], "company_owned", via.get("retrieved_at") or "", via.get("sha256") or "", via.get("span") or "",
                           "recruitment_link_on_verified_site" if ev else "jsonld_jobposting", final_url=via["url"],
                           http_status=via.get("status") or None, source_name=via.get("host") or ""))
        ident = f"{post.platform}:{post.id}" if post.platform != "site" else "site:" + post.id.lower().rstrip("/")
        conf = 0.95 if post.employer or post.orgnr else 0.92
        if post.platform == "site" and not post.orgnr:
            conf = 0.88
        rel = "registered_subunit" if post.orgnr and post.orgnr != p.orgnr else "exact"
        p.add(Claim("jobs", "job_posting", value, ev, label=f"Job posting ({label})", effective_date=post.published,
                    relationship=rel, confidence=conf, key=f"jobs:job_posting:{ident}"[:200]))
        if post.published:
            p.add(Claim("activity", "job_ad_published", {"title": post.title, "url": post.url, "source": value["source"]},
                        ev, label="Published a job ad", effective_date=post.published, relationship=rel, confidence=conf,
                        key=f"activity:job_ad_published:{ident}"[:200]))

    def report(self) -> dict:
        return self.stats


def _days(a: str, b: str) -> int:
    try:
        return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days
    except ValueError:
        return 999


def _label(host: str) -> str:
    """The brand label of a host: 'karriere.firma.no' -> 'firma'."""
    from ..discovery import registrable
    reg = registrable((host or "").lower())
    return reg.split(".")[0] if reg else ""
