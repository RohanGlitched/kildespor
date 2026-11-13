"""NAV Job Vacancy Feed (pam-stilling-feed.nav.no).

NAV publishes a public token for this feed and lets anyone use it free of charge under its terms.
The token is fetched at run time from NAV's own endpoint; nothing is tied to a personal account.

1. The walk. Parallel walkers read every feed page changed in the last WINDOW_DAYS (each starts at its own
   If-Modified-Since date) and keep the latest state per ad. 180 days covers 99.9% of NAV's active ads;
   75 days missed about 4% (ads published months ago and never edited).
2. The index. The feed page does not carry the employer's organisation number, so every ACTIVE ad's details
   are read once and indexed by employer orgnr. NAV answers about 20-25 detail requests a second per client
   however many are sent in parallel, so the order matters: ads whose employer name reads like a public body
   (kommune, HF, NAV, skole, ...) are read last, since the companies we research rarely post them. The index
   runs alongside the company research; it stops when complete, or after INDEX_SOFT_SECONDS once every company
   is waiting for it, or at INDEX_HARD_SECONDS.
3. Each company first reads, ahead of the index, the ads whose employer name matches its legal name, a
   registered subunit name or the verified site's brand; then waits for the index. An ad is published only
   when its employer orgnr is the company's own or one of its registered subunits', and only while it is open
   (ACTIVE, not past its application deadline or expiry). The posting links to its public page on
   arbeidsplassen.nav.no, which is fetched so that the evidence quotes the page anyone can open.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

from .. import http as _http
from ..claims import Claim, Evidence
from ..util import clip, fold, name_tokens
from . import Source

BASE = "https://pam-stilling-feed.nav.no"
PUBLIC = "https://arbeidsplassen.nav.no/stillinger/stilling/{}"
PUBLIC_HOST = "arbeidsplassen.nav.no"
WINDOW_DAYS = 180
WALKERS = 24
INDEX_WORKERS = 14        # index requests in flight: NAV serves ~12-25 a second per client whatever the concurrency; the host allows 16, so a company's own lookups never wait behind the index
INDEX_SOFT_SECONDS = 420  # after this the index stops as soon as every company is waiting for it
INDEX_HARD_SECONDS = 840  # never index longer than this
MAX_POSTINGS = 40         # NAV postings published per company (big employers post hundreds)
MAX_PUBLIC_PAGES = 6      # public ad pages fetched per company (the newest postings); the rest keep the feed evidence
MAX_NAME_CANDIDATES = 60
GENERIC = {"as", "asa", "og", "avd", "avdeling", "norge", "norway", "holding", "the", "i", "pa"}
# employer names that read like a public body; their ads are indexed last
PUBLIC_NAME = re.compile(
    r"\b(kommune|kommunes|fylkeskommune|fylkeskommunes|hf|sykehus\w*|sjukehus\w*|sykehjem|helsehus|universitet\w*|h[øo]gskule\w*|"
    r"h[øo]gskole\w*|nav|politi\w*|bufetat|statens|forsvaret|direktorat\w*|\w+etaten|kriminalomsorg\w*|fengsel|vgs|"
    r"videreg[åa]ende|bydel|tingrett|lagmannsrett|domstol\w*|departement\w*|statsforvalt\w*|kommunalomr[åa]de|"
    r"tenesteomr[åa]de|tjenesteomr[åa]de|kirkelig fellesr[åa]d|bispedømme\w*)\b", re.I)
COMPANY_NAME = re.compile(r"\b(as|asa|sa|ans|da|nuf)\s*$", re.I)

# the public ad page on arbeidsplassen.nav.no is served one request at a time by default; a few in parallel is polite
_http.HOST_LIMITS.setdefault(PUBLIC_HOST, 4)


def _today() -> str:
    return date.today().isoformat()


def _sig(name: str) -> tuple[str, ...]:
    return tuple(t for t in name_tokens(name) if t not in GENERIC)


def if_modified_since(dt: datetime) -> str:
    """RFC 7231 date for the If-Modified-Since header ('Fri, 13 Nov 2026 00:00:00 GMT'), English names whatever the locale."""
    return format_datetime(dt.astimezone(timezone.utc), usegmt=True)


def index_order(ads: dict[str, dict]) -> list[str]:
    """ACTIVE ads in the order the index reads them: likely companies first, public bodies last."""
    def tier(u: str) -> int:
        name = ads[u].get("businessName") or ""
        if COMPANY_NAME.search(name):
            return 0
        return 1 if PUBLIC_NAME.search(name) else 0
    act = [u for u, e in ads.items() if e.get("status") == "ACTIVE"]
    return sorted(act, key=tier)


def parse_due(text) -> str | None:
    """An application deadline as an ISO date, or None when it is not a date ('Snarest', 'Løpende')."""
    if not text:
        return None
    s = str(text).strip()
    m = re.match(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.match(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", s)
        if not m:
            return None
        d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def ad_state(detail: dict, feed_status: str | None, today: str) -> str:
    """'open', or why the ad is not an open posting: 'inactive', 'deadline_passed', 'expired', 'open_application'
    ('Åpen søknad for Rema 1000 Brattvåg'), 'evergreen' (a deadline more than a year away)."""
    from .careers import EVERGREEN_DAYS, OPEN_APPLICATION, _days
    status = detail.get("status") or feed_status
    if status != "ACTIVE":
        return "inactive"
    ad = detail.get("ad_content") or {}
    due = parse_due(ad.get("applicationDue"))
    if due and due < today:
        return "deadline_passed"
    exp = (ad.get("expires") or "")[:10]
    if exp and exp < today:
        return "expired"
    if OPEN_APPLICATION.search(ad.get("title") or ""):
        return "open_application"
    if due and _days(due, today) > EVERGREEN_DAYS:
        return "evergreen"
    return "open"


def employer_orgnr(detail: dict | None) -> str:
    return re.sub(r"\D", "", ((((detail or {}).get("ad_content") or {}).get("employer") or {}).get("orgnr")) or "")


def public_page_facts(html: str) -> dict:
    """Title, employer and deadline line as the public ad page shows them. The employer is the first line of the block
    right under the ad's heading; the 'Arbeidsgiver' labels further down belong to the similar ads NAV lists."""
    from selectolax.parser import HTMLParser
    tree = HTMLParser(html or "")
    h1 = tree.css_first("h1")
    out = {"title": re.sub(r"\s+", " ", h1.text()).strip() if h1 else ""}
    nxt = h1.next if h1 is not None else None
    while nxt is not None and nxt.tag != "section":
        nxt = nxt.next
    if nxt is not None:
        lines = [re.sub(r"\s+", " ", p.text() or "").strip() for p in nxt.css("p")]
        lines = [x for x in lines if x and x not in ("Arbeidsgiver", "Sted")]
        if lines:
            out["employer"] = lines[0]
    for p in tree.css("p"):
        t = re.sub(r"\s+", " ", p.text() or "").strip()
        if re.match(r"(Søk senest|Søk snarest|Søknadsfrist)\b", t):
            out["deadline_line"] = t
            break
    return out


def feed_span(raw: str, uuid: str, title: str, org: str) -> str:
    """Literal fragments of the feed entry: the employer block's name and organisation number, the ad title, its status."""
    pieces = []
    m = re.search(r'"employer"\s*:\s*\{\s*"name"\s*:\s*"[^"]{1,120}"\s*,\s*"orgnr"\s*:\s*"' + re.escape(org) + '"', raw) \
        or re.search(r'"orgnr"\s*:\s*"' + re.escape(org) + '"', raw)
    if m:
        pieces.append(m.group(0))
    t = '"title":' + json.dumps(title, ensure_ascii=False)
    if title and t in raw:
        pieces.append(t)
    m = re.search(r'"status"\s*:\s*"[A-Z]+"(?=\s*\}\s*$)', raw)
    if m:
        pieces.append(m.group(0))
    return " · ".join(pieces) or uuid


# words many unrelated companies share; a common one of these does not make two names one family
SHARED_WORDS = {"hotel", "hotell", "bygg", "service", "services", "eiendom", "holding", "gruppen", "group", "norge", "norway",
                "drift", "invest", "consult", "consulting", "tannklinikk", "tannlegesenter", "restaurant", "transport", "elektro",
                "entreprenor", "entreprenør", "regnskap", "barnehage", "assistanse", "omsorg", "helse", "senter", "handel",
                "butikk", "maskin", "auto", "bil", "media", "solutions", "systems", "technology", "teknikk", "partner",
                "partners", "nordic", "norsk", "norske", "vest", "nord", "sør", "sor", "øst", "ost", "avdeling"}


class DisplayedEmployer:
    """The employer an ad shows ('Arbeidsgiver' on arbeidsplassen.nav.no, the feed's businessName) may differ from the
    organisation that registered it. A recruiter posting for a client ('Job Norway' registers the ad, the page shows
    'Støtvig Hotel AS') or an anonymous employer is not an open posting at the registering company. Brand, store and
    department names without a legal form ('KIWI Fredensborg', 'Humana omsorg og assistanse') are kept: the orgnr says whose."""

    def __init__(self, ent: dict, subunits: list, orgnr: str, brands: list[str]) -> None:
        from .careers import Who, _sig as csig
        self.who = Who(ent, subunits, orgnr, brands)
        self.csig = csig
        self.subs = {"".join(csig(u.get("name") or "")) for u in subunits} - {""}
        names = [ent.get("navn", "")] + [u.get("name") or "" for u in subunits] + list(brands)
        self.tokens = {t for x in names for t in csig(x) if len(t) >= 4} - SHARED_WORDS

    def other(self, name: str | None) -> bool:
        from .careers import _has_form
        if not name:
            return False
        if re.search(r"\banonym", name, re.I):
            return True
        if PUBLIC_NAME.search(name) and not PUBLIC_NAME.search(self.who.name) and not self.who.match(name):
            return True  # 'Statsforvaltaren i Vestland' shown on an ad filed under a TINE SA workplace: a mis-filed ad
        if not _has_form(name) or self.who.match(name):
            return False
        if "".join(self.csig(name)) in self.subs:
            return False
        # the same family of names ('Grand Hotel Arendal AS' for GRAND HOTEL ARENDAL DRIFT AS) is not another employer
        return not ({t for t in self.csig(name) if len(t) >= 4} - SHARED_WORDS) & self.tokens


class NavJobs(Source):
    name = "nav_jobs"
    families = ["jobs"]
    late = True

    def __init__(self, window_days: int = WINDOW_DAYS) -> None:
        self.window_days = window_days
        self.token = ""
        self.ads: dict[str, dict] = {}  # uuid -> latest feed entry
        self.by_token: dict[str, list[str]] = {}
        self.by_orgnr: dict[str, list[str]] = {}
        self.pages = 0
        self.details = 0
        self.public_pages = 0
        self.matched_companies = 0
        self.published = 0
        self.skipped: dict[str, int] = {}
        self.skip_examples: dict[str, list[str]] = {}
        self.detail_cache: dict[str, asyncio.Future] = {}
        self.public_cache: dict[str, asyncio.Future] = {}
        self.sem = asyncio.Semaphore(16)
        self.indexed = 0
        self.cache_hits = 0
        self.total_companies = 0
        self.researched = 0  # companies whose research slot has ended (the runner calls research_done)
        self.index_done = asyncio.Event()
        self.index_complete = False
        self.index_seconds = 0.0
        self.walk_seconds = 0.0
        self.walker_errors: list[str] = []
        self._index_task = None
        self._indexed: set[str] = set()

    def _h(self, extra: dict | None = None) -> dict:
        return {"Authorization": "Bearer " + self.token, "Accept": "application/json", **(extra or {})}

    # ------------------------------------------------------------------------------------------
    async def prepare(self, ctx, orgs: list[str]) -> None:
        self.total_companies = len(orgs)
        t0 = time.monotonic()
        f = await ctx.client.get(self.name, BASE + "/api/publicToken", check_robots=False, retries=4, timeout=30)
        if not f.ok:
            self.index_done.set()
            raise RuntimeError(f"NAV public token unavailable ({f.status or f.error})")
        lines = [x.strip() for x in f.text().splitlines() if x.strip()]
        self.token = next((x for x in lines if x.count(".") == 2 and len(x) > 60), "")
        if not self.token:
            self.index_done.set()
            raise RuntimeError("NAV public token not found in response")
        now = datetime.now(timezone.utc)
        starts = [now - timedelta(days=self.window_days) + timedelta(days=self.window_days * i / WALKERS) for i in range(WALKERS)]
        bounds = starts[1:] + [None]
        results = await asyncio.gather(*(self._walk(ctx, s, b) for s, b in zip(starts, bounds)), return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        self.walker_errors = [repr(e) for e in errors]
        self.walk_seconds = round(time.monotonic() - t0, 1)
        if errors and len(errors) == len(results):
            self.index_done.set()
            raise RuntimeError(f"NAV feed unreadable: {errors[0]!r}")
        for uuid, e in self.ads.items():
            for t in set(_sig(e.get("businessName") or "")):
                self.by_token.setdefault(t, []).append(uuid)
        # the index builds in the background; companies read their own name matches meanwhile
        self._index_task = asyncio.create_task(self._index(ctx))

    async def _index(self, ctx) -> None:
        t0 = time.monotonic()
        cache_path = getattr(ctx, "cache_dir", None)
        cache_path = cache_path / "nav-employer-orgnr.json" if cache_path else None
        known: dict[str, str] = {}
        if cache_path and cache_path.exists():
            try:
                known = json.loads(cache_path.read_text(encoding="utf-8"))
            except ValueError:
                known = {}
        order = index_order(self.ads)
        todo: list[str] = []
        for u in order:
            if u in known:
                self.cache_hits += 1
                self._add_index(u, known[u])
            else:
                todo.append(u)
        queue = list(reversed(todo))  # pop() from the end keeps the order

        async def worker() -> None:
            while queue:
                u = queue.pop()
                if u in self._indexed:
                    continue  # a company's own lookup read it already
                d, _ = await self._detail(ctx, u)
                if d is not None:
                    org = employer_orgnr(d)
                    known[u] = org
                    self._add_index(u, org)
        workers = [asyncio.create_task(worker()) for _ in range(INDEX_WORKERS)]
        try:
            while not all(w.done() for w in workers):
                await asyncio.wait(workers, timeout=1.0)
                el = time.monotonic() - t0
                if el >= INDEX_HARD_SECONDS or (el >= INDEX_SOFT_SECONDS and self.researched >= self.total_companies):
                    break  # past the soft cap and no company is still being researched: the index is now the bottleneck
        finally:
            for w in workers:
                w.cancel()
            active = [u for u, e in self.ads.items() if e.get("status") == "ACTIVE"]
            self.index_complete = all(u in self._indexed for u in active)
            self.index_seconds = round(time.monotonic() - t0, 1)
            self.index_done.set()
            if cache_path:
                try:
                    keep = {u: known[u] for u in self.ads if u in known}
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps(keep, separators=(",", ":")), encoding="utf-8")
                except OSError:
                    pass

    def _add_index(self, u: str, org: str) -> None:
        if u in self._indexed:
            return
        self._indexed.add(u)
        if org and self.ads.get(u, {}).get("status") == "ACTIVE":
            self.by_orgnr.setdefault(org, []).append(u)
            self.indexed += 1

    async def _walk(self, ctx, start: datetime, stop: datetime | None) -> None:
        f = await ctx.client.get("nav_jobs_index", BASE + "/api/v1/feed", retries=3, timeout=45,
                                 headers=self._h({"If-Modified-Since": if_modified_since(start)}), check_robots=False)
        for _ in range(400):
            if not f.ok:
                raise RuntimeError(f"feed page failed ({f.status or f.error})")
            page = json.loads(f.body)
            self.pages += 1
            last = None
            for it in page.get("items") or []:
                e = it.get("_feed_entry") or {}
                when = it.get("date_modified") or e.get("sistEndret")
                last = when
                if e.get("uuid"):
                    prev = self.ads.get(e["uuid"])
                    if not prev or (when or "") >= (prev.get("_when") or ""):
                        self.ads[e["uuid"]] = {**e, "_when": when}
            if stop and last and datetime.fromisoformat(last) >= stop:
                return
            nxt = page.get("next_url")
            if not nxt or not page.get("items"):
                return
            f = await ctx.client.get("nav_jobs_index", BASE + nxt, headers=self._h(), check_robots=False, retries=3, timeout=45)

    async def _detail(self, ctx, uuid: str) -> tuple[dict | None, object]:
        """One ad's details, read once per run (the index and a company's own lookup share it)."""
        fut = self.detail_cache.get(uuid)
        if fut is None:
            fut = self.detail_cache[uuid] = asyncio.ensure_future(self._fetch_detail(ctx, uuid))
        try:
            return await asyncio.shield(fut)
        except Exception:  # noqa: BLE001 - a failed detail is a miss, never a crash
            return None, None

    async def _fetch_detail(self, ctx, uuid: str) -> tuple[dict | None, object]:
        async with self.sem:
            f = await ctx.client.get("nav_jobs_index", f"{BASE}/api/v1/feedentry/{uuid}", headers=self._h(), check_robots=False,
                                     retries=1, timeout=20)
        self.details += 1
        if not f.ok:
            self.detail_cache.pop(uuid, None)  # a later lookup may retry
            return None, f
        try:
            return json.loads(f.body), f
        except ValueError:
            return None, f

    def _candidates(self, aliases: list[tuple[str, ...]]) -> list[str]:
        found: list[str] = []
        for sig in aliases:
            if not sig:
                continue
            pool = None
            for t in sig[:2]:
                ids = set(self.by_token.get(t, []))
                pool = ids if pool is None else pool & ids
                if not pool:
                    break
            short = len(sig) == 1 and len(sig[0]) < 5
            for uuid in pool or []:
                bsig = _sig(self.ads[uuid].get("businessName") or "")
                if short:
                    ok = bsig == sig  # a short name ("SFE", "FLO") only as the whole employer name
                else:
                    # all alias tokens appear in the employer name, and the employer name is not much longer
                    ok = (set(sig) <= set(bsig) and len(bsig) <= len(sig) + 3) or (len(bsig) >= 2 and set(bsig) <= set(sig))
                if ok and uuid not in found:
                    found.append(uuid)
        return found

    # ------------------------------------------------------------------------------------------
    def research_done(self) -> None:
        """Called by the runner when a company's research slot ends (whether or not it reaches the late sources)."""
        self.researched += 1

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        try:
            await self._enrich(ctx, p, ent, subunits, sites)
        finally:  # the careers source waits for NAV's postings so that it never publishes the same ad twice
            p.notes.setdefault("_nav_done", asyncio.Event()).set()

    async def _enrich(self, ctx, p, ent, subunits, sites) -> None:
        if self.prepare_error:
            raise RuntimeError(self.prepare_error)
        p.checked_source("jobs", f"NAV job vacancy feed (ads changed in the last {self.window_days} days, indexed by employer orgnr)")
        own = {p.orgnr} | {u.get("organisation_number") for u in subunits if u.get("organisation_number")}
        aliases = [_sig(ent.get("navn", ""))] + [_sig(u.get("name") or "") for u in subunits]
        for s in sites:
            for page in s.pages[:1]:
                if page.site_name:
                    aliases.append(_sig(page.site_name))
                aliases.append(_sig(page.host().removeprefix("www.").split(".")[0].replace("-", " ")))  # the domain's brand
        aliases = [a for a in dict.fromkeys(aliases) if a and (len(a) >= 2 or len(a[0]) >= 3)]
        named = self._candidates(aliases)
        named.sort(key=lambda u: self.ads[u].get("status") != "ACTIVE")
        named = named[:MAX_NAME_CANDIDATES]
        # the company's own name matches are read now, ahead of the index
        early = []
        for u, (d, _) in zip(named, await asyncio.gather(*(self._detail(ctx, u) for u in named))):
            if d is not None:
                self._add_index(u, employer_orgnr(d))
                if employer_orgnr(d) in own and ad_state(d, self.ads[u].get("status"), _today()) == "open":
                    early.append(u)
        for u in early[:MAX_PUBLIC_PAGES]:  # their public pages load while the index finishes
            self._public_cached(ctx, u)
        # then the orgnr index, for ads posted under another name (a brand, a store, a department)
        if not self.index_done.is_set():
            try:
                await asyncio.wait_for(self.index_done.wait(), timeout=INDEX_HARD_SECONDS + 60)
            except asyncio.TimeoutError:
                pass
        if not self.index_complete:
            p.checked_source("jobs", f"NAV index incomplete: {self.indexed} of the active ads read in time")
        cands: list[str] = []
        for o in sorted(own):
            cands.extend(u for u in self.by_orgnr.get(o, []) if u not in cands)
        cands.extend(u for u in named if u not in cands)
        if not cands:
            return
        details = await asyncio.gather(*(self._detail(ctx, u) for u in cands))
        today = _today()
        if len(subunits) >= 200:  # the register lists 200 subunits per page: ask it about the other employers we matched by name
            others = {employer_orgnr(d) for d, _ in details if d} - own - {""}
            for o in list(others)[:10]:
                if await self._parent(ctx, o) == p.orgnr:
                    own.add(o)
        hits = []
        for uuid, (d, f) in zip(cands, details):
            if not d:
                continue
            org = employer_orgnr(d)
            if org not in own:
                continue
            state = ad_state(d, self.ads.get(uuid, {}).get("status"), today)
            if state != "open":
                self.skipped[state] = self.skipped.get(state, 0) + 1
                self._example(state, ent, (d.get("ad_content") or {}).get("title"), uuid)
                continue
            hits.append((uuid, d, f, org))
        brands = [s.home.host().removeprefix("www.").split(".")[0] for s in sites] + [s.home.site_name for s in sites if s.home.site_name]
        who = DisplayedEmployer(ent, subunits, p.orgnr, brands)
        hits = [h for h in hits if not self._other_shown(who, self.ads.get(h[0], {}).get("businessName"), ent, h[0])]
        hits.sort(key=lambda h: ((h[1].get("ad_content") or {}).get("published") or ""), reverse=True)
        hits = hits[:MAX_POSTINGS]
        pages = await asyncio.gather(*(self._public_cached(ctx, uuid) for uuid, *_ in hits[:MAX_PUBLIC_PAGES]))
        pages = list(pages) + [None] * (len(hits) - len(pages))
        kept = []
        for (uuid, d, f, org), pub in zip(hits, pages):
            if pub is not None and self._other_shown(who, pub[1].get("employer"), ent, uuid):
                continue
            kept.append((uuid, d, f, org))
            self._claim(ctx, p, uuid, d, f, org, pub)
            emp = (d.get("ad_content") or {}).get("employer") or {}
            if emp.get("homepage"):  # a hint for website discovery only; never a claim
                p.notes.setdefault("nav_homepages", []).append(emp["homepage"])
        if kept:
            self.matched_companies += 1
            self.published += len(kept)

    def _other_shown(self, who: "DisplayedEmployer", name: str | None, ent: dict | None = None, uuid: str = "") -> bool:
        if who.other(name):
            self.skipped["shown_for_another_employer"] = self.skipped.get("shown_for_another_employer", 0) + 1
            self._example("shown_for_another_employer", ent or {}, f"shown as '{name}'", uuid)
            return True
        return False

    def _example(self, reason: str, ent: dict, what, uuid: str) -> None:
        ex = self.skip_examples.setdefault(reason, [])
        if len(ex) < 4:  # a few examples of each reject rule, for the run report
            ex.append(f"{ent.get('navn', '')}: {clip(str(what or ''), 80)} ({uuid})")

    async def _parent(self, ctx, orgnr: str) -> str:
        f = await ctx.client.get("brreg", f"https://data.brreg.no/enhetsregisteret/api/underenheter/{orgnr}",
                                 headers={"Accept": "application/json"}, check_robots=False, retries=1)
        try:
            return str(json.loads(f.body).get("overordnetEnhet") or "") if f.ok else ""
        except ValueError:
            return ""

    def _public_cached(self, ctx, uuid: str) -> asyncio.Future:
        if uuid not in self.public_cache:
            self.public_cache[uuid] = asyncio.ensure_future(self._public(ctx, uuid))
        return self.public_cache[uuid]

    async def _public(self, ctx, uuid: str):
        f = await ctx.client.get(self.name, PUBLIC.format(uuid), timeout=15, retries=1)
        self.public_pages += 1
        if not f.ok or "html" not in (f.content_type or "").lower():
            return None
        facts = public_page_facts(f.text())
        return f, facts

    def _claim(self, ctx, p, uuid: str, d: dict, f, org: str, pub) -> None:
        ad = d.get("ad_content") or {}
        emp = ad.get("employer") or {}
        title = clip(ad.get("title") or self.ads.get(uuid, {}).get("title") or "", 160)
        locs = ", ".join(sorted({(x.get("city") or x.get("municipal") or "").title() for x in ad.get("workLocations") or [] if x} - {""}))
        posted = (ad.get("published") or "")[:10] or None
        due_raw = ad.get("applicationDue")
        due = parse_due(due_raw)
        value = {"title": title, "url": PUBLIC.format(uuid), "location": locs or None, "deadline": due, "posted": posted,
                 "status": "open", "source": "NAV arbeidsplassen",
                 # kept for older readers of the envelope
                 "uuid": uuid, "employer": emp.get("name"), "employer_orgnr": org, "published": posted,
                 "expires": (ad.get("expires") or "")[:10] or None, "application_due": due or due_raw}
        if due_raw and not due:
            value["application_due_text"] = clip(str(due_raw), 80)
        occ = [o.get("level2") for o in ad.get("occupationCategories") or [] if isinstance(o, dict) and o.get("level2")][:3]
        if occ:
            value["occupations"] = occ
        value = {k: v for k, v in value.items() if v not in (None, "")}
        rel = "exact" if org == p.orgnr else "registered_subunit"
        ev = []
        if pub is not None:
            pf, facts = pub
            same = fold(facts.get("title") or "") == fold(title) or fold(title) in fold(facts.get("title") or "")
            if same:
                span = " · ".join(x for x in (facts.get("title"), facts.get("employer"),
                                                facts.get("deadline_line")) if x)
                ev.append(Evidence(PUBLIC.format(uuid), "public_job_board", pf.retrieved_at, pf.sha256, span, "nav_public_ad_page",
                                   final_url=pf.final_url, http_status=pf.status, source_name="arbeidsplassen.nav.no"))
        ctx.client.save_snapshot(f)
        ev.append(Evidence(f"{BASE}/api/v1/feedentry/{uuid}", "public_job_board", f.retrieved_at, f.sha256,
                           feed_span(f.text(), uuid, ad.get("title") or "", org),
                           "nav_feed_employer_orgnr", final_url=f.final_url, http_status=f.status, source_name="NAV job vacancy feed"))
        p.add(Claim("jobs", "job_posting", value, ev, label="Job posting (NAV)", effective_date=posted, relationship=rel,
                    confidence=0.99, key=f"jobs:job_posting:nav:{uuid}"))
        if posted:
            p.add(Claim("activity", "job_ad_published", {"title": title, "url": value["url"], "source": "NAV arbeidsplassen"},
                        ev, label="Published a job ad", effective_date=posted, relationship=rel, confidence=0.99,
                        key=f"activity:job_ad_published:nav:{uuid}"))

    def report(self) -> dict:
        active = sum(1 for e in self.ads.values() if e.get("status") == "ACTIVE")
        return {"feed_pages": self.pages, "ads_in_window": len(self.ads), "active_ads": active, "walk_seconds": self.walk_seconds,
                "detail_requests": self.details, "public_ad_pages": self.public_pages, "companies_matched": self.matched_companies,
                "ads_published": self.published, "skipped_not_open": self.skipped, "skip_examples": self.skip_examples, "window_days": self.window_days,
                "active_ads_indexed_by_orgnr": self.indexed, "index_coverage": round(len(self._indexed & {u for u, e in self.ads.items()
                                                                                                           if e.get("status") == "ACTIVE"}) / active, 4) if active else None,
                "index_seconds": self.index_seconds, "index_cache_hits": self.cache_hits, "index_complete": self.index_complete,
                "walker_errors": self.walker_errors}
