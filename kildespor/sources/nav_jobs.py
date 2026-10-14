"""NAV Job Vacancy Feed (pam-stilling-feed.nav.no).

NAV publishes a public token for this feed and lets anyone use it free of charge under its terms.
The token is fetched at run time from NAV's own endpoint; nothing is tied to a personal account.

A run reads every feed page changed in the last WINDOW_DAYS (parallel walkers started at
different If-Modified-Since dates), keeps the latest state per ad, and indexes ads by employer
name. For each company we fetch the details of ads whose employer name matches the legal name,
a registered subunit name or the verified site's brand, and publish an ad only when the ad's
employer organisation number is the company's own or one of its registered subunits'.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from ..claims import Claim, Evidence
from ..util import clip, fold, name_tokens
from . import Source

BASE = "https://pam-stilling-feed.nav.no"
PUBLIC = "https://arbeidsplassen.nav.no/stillinger/stilling/{}"
WINDOW_DAYS = 75
WALKERS = 15
DETAIL_SECONDS = 420  # time cap for indexing active ads by employer organisation number
GENERIC = {"as", "asa", "og", "avd", "avdeling", "norge", "norway", "holding", "the", "i", "pa"}


def _sig(name: str) -> tuple[str, ...]:
    return tuple(t for t in name_tokens(name) if t not in GENERIC)


class NavJobs(Source):
    name = "nav_jobs"
    families = ["jobs"]

    def __init__(self, window_days: int = WINDOW_DAYS) -> None:
        self.window_days = window_days
        self.token = ""
        self.ads: dict[str, dict] = {}  # uuid -> latest feed entry
        self.by_token: dict[str, list[str]] = {}
        self.pages = 0
        self.details = 0
        self.matched_companies = 0
        self.published = 0
        self.detail_cache: dict[str, dict | None] = {}
        self.sem = asyncio.Semaphore(12)
        self.by_orgnr: dict[str, list[str]] = {}
        self.indexed = 0

    def _h(self, extra: dict | None = None) -> dict:
        return {"Authorization": "Bearer " + self.token, "Accept": "application/json", **(extra or {})}

    async def prepare(self, ctx, orgs: list[str]) -> None:
        f = await ctx.client.get(self.name, BASE + "/api/publicToken", check_robots=False)
        if not f.ok:
            raise RuntimeError(f"NAV public token unavailable ({f.status or f.error})")
        lines = [x.strip() for x in f.text().splitlines() if x.strip()]
        self.token = next((x for x in lines if x.count(".") == 2 and len(x) > 60), "")
        if not self.token:
            raise RuntimeError("NAV public token not found in response")
        now = datetime.now(timezone.utc)
        starts = [now - timedelta(days=self.window_days) + timedelta(days=self.window_days * i / WALKERS) for i in range(WALKERS)]
        bounds = starts[1:] + [None]
        results = await asyncio.gather(*(self._walk(ctx, s, b) for s, b in zip(starts, bounds)), return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        self.walker_errors = [repr(e) for e in errors]
        if errors and len(errors) == len(results):
            raise RuntimeError(f"NAV feed unreadable: {errors[0]!r}")
        for uuid, e in self.ads.items():
            for t in set(_sig(e.get("businessName") or "")):
                self.by_token.setdefault(t, []).append(uuid)
        # index every active ad by its employer's organisation number (NAV's intended consumer pattern)
        active = [u for u, e in self.ads.items() if e.get("status") == "ACTIVE"]
        async def one(u: str) -> None:
            d, _ = await self._detail(ctx, u)
            org = re.sub(r"\D", "", (((d or {}).get("ad_content") or {}).get("employer") or {}).get("orgnr") or "")
            if org:
                self.by_orgnr.setdefault(org, []).append(u)
                self.indexed += 1
        tasks = [asyncio.create_task(one(u)) for u in active]
        done, pending = await asyncio.wait(tasks, timeout=DETAIL_SECONDS)
        for t in pending:
            t.cancel()
        self.index_complete = not pending

    async def _walk(self, ctx, start: datetime, stop: datetime | None) -> None:
        f = await ctx.client.get("nav_jobs_index", BASE + "/api/v1/feed", retries=3, timeout=45,
                                 headers=self._h({"If-Modified-Since": format_datetime(start, usegmt=True)}), check_robots=False)
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
                        self.ads[e["uuid"]] = {**e, "_when": when, "_page": BASE + (page.get("feed_url") or "")}
            if stop and last and datetime.fromisoformat(last) >= stop:
                return
            nxt = page.get("next_url")
            if not nxt or not page.get("items"):
                return
            f = await ctx.client.get("nav_jobs_index", BASE + nxt, headers=self._h(), check_robots=False, retries=3, timeout=45)

    async def _detail(self, ctx, uuid: str) -> tuple[dict | None, object]:
        if uuid in self.detail_cache:
            return self.detail_cache[uuid]
        async with self.sem:
            f = await ctx.client.get("nav_jobs_index", f"{BASE}/api/v1/feedentry/{uuid}", headers=self._h(), check_robots=False,
                                     retries=1, timeout=20)
        self.details += 1
        out = (json.loads(f.body), f) if f.ok else (None, f)
        self.detail_cache[uuid] = out
        return out

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
            for uuid in pool or []:
                bsig = _sig(self.ads[uuid].get("businessName") or "")
                # all alias tokens appear in the employer name, and the employer name is not much longer
                forward = set(sig) <= set(bsig) and len(bsig) <= len(sig) + 3
                backward = len(bsig) >= 2 and set(bsig) <= set(sig)
                if (forward or backward) and uuid not in found:
                    found.append(uuid)
        return found

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        if self.prepare_error:
            raise RuntimeError(self.prepare_error)
        p.checked_source("jobs", f"NAV job vacancy feed (last {self.window_days} days)")
        own = {p.orgnr} | {u.get("organisation_number") for u in subunits if u.get("organisation_number")}
        aliases = [_sig(ent.get("navn", ""))] + [_sig(u.get("name") or "") for u in subunits]
        for s in sites:
            for page in s.pages[:1]:
                if page.site_name:
                    aliases.append(_sig(page.site_name))
        aliases = [a for a in dict.fromkeys(aliases) if a and (len(a) >= 2 or len(a[0]) >= 5)]
        cands = []
        for o in own:
            cands.extend(u for u in self.by_orgnr.get(o, []) if u not in cands)
        named = [u for u in self._candidates(aliases) if u not in cands]
        named.sort(key=lambda u: self.ads[u].get("status") != "ACTIVE")
        cands.extend(named[:60])
        if not cands:
            return
        details = await asyncio.gather(*(self._detail(ctx, u) for u in cands))
        hit = 0
        for uuid, (d, f) in zip(cands, details):
            if not d:
                continue
            ad = d.get("ad_content") or {}
            emp = ad.get("employer") or {}
            org = re.sub(r"\D", "", emp.get("orgnr") or "")
            if org not in own:
                continue
            hit += 1
            ctx.client.save_snapshot(f)
            status = d.get("status") or self.ads[uuid].get("status")
            locs = ", ".join(sorted({(x.get("city") or x.get("municipal") or "").title() for x in ad.get("workLocations") or [] if x}))
            published = (ad.get("published") or "")[:10] or None
            value = {"title": clip(ad.get("title") or self.ads[uuid].get("title") or "", 160), "uuid": uuid,
                     "url": PUBLIC.format(uuid), "status": "open" if status == "ACTIVE" else "closed",
                     "employer": emp.get("name"), "employer_orgnr": org, "location": locs,
                     "published": published, "expires": (ad.get("expires") or "")[:10] or None,
                     "application_due": ad.get("applicationDue"), "source": "NAV arbeidsplassen",
                     "occupations": [o.get("level2") for o in ad.get("occupationCategories") or [] if isinstance(o, dict)][:3]}
            rel = "exact" if org == p.orgnr else "registered_subunit"
            ev = [Evidence(f"{BASE}/api/v1/feedentry/{uuid}", "public_job_board", f.retrieved_at, f.sha256,
                           f"employer.orgnr {org} · {emp.get('name')} · {value['title']} · published {published} · status {status}",
                           "nav_feed_employer_orgnr", final_url=f.final_url, http_status=f.status, source_name="NAV arbeidsplassen")]
            p.add(Claim("jobs", "job_posting", value, ev, label="Job posting (NAV)" if status == "ACTIVE" else "Closed job posting (NAV)",
                        effective_date=published, relationship=rel, confidence=0.99, key=f"jobs:job_posting:nav:{uuid}"))
            if published:
                p.add(Claim("activity", "job_ad_published", {"title": value["title"], "url": value["url"], "source": "NAV arbeidsplassen"},
                            ev, label="Published a job ad", effective_date=published, relationship=rel, confidence=0.99,
                            key=f"activity:job_ad_published:nav:{uuid}"))
            if emp.get("homepage"):
                p.notes.setdefault("nav_homepages", []).append(emp["homepage"])
        if hit:
            self.matched_companies += 1
            self.published += hit

    def report(self) -> dict:
        return {"feed_pages": self.pages, "ads_in_window": len(self.ads),
                "active_ads": sum(1 for e in self.ads.values() if e.get("status") == "ACTIVE"),
                "detail_requests": self.details, "companies_matched": self.matched_companies, "ads_published": self.published,
                "window_days": self.window_days, "active_ads_indexed_by_orgnr": self.indexed,
                "index_complete": getattr(self, "index_complete", False), "walker_errors": getattr(self, "walker_errors", [])}
