"""Research one organisation number end to end."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from . import extract, registry
from .claims import FAMILIES, Profile
from .discovery import Candidate, Resolver, candidates, domain_of, registrable
from .http import Client
from .site import SiteResult, complete, crawl, sibling_check, verify

MAX_NAME_CANDIDATES = 5
MAX_EXACT_SITES = 2


class Context:
    """Shared, run-wide resources."""

    def __init__(self, client: Client, resolver: Resolver, sources: list[Any] | None = None, bulk: dict | None = None) -> None:
        self.client = client
        self.resolver = resolver
        self.sources = sources or []  # run-wide connectors (NAV jobs, Wikidata, ...)
        self.bulk = bulk or {}


async def research(ctx: Context, orgnr: str, p: Profile | None = None, trace: dict | None = None) -> tuple[Profile, dict]:
    t0 = time.monotonic()
    p = p if p is not None else Profile(orgnr)
    trace = trace if trace is not None else {}
    trace.update({"candidates": [], "sites": []})
    ent, f = await registry.fetch_entity(ctx.client, orgnr)
    if ent is None and orgnr in ctx.bulk:
        ent = ctx.bulk[orgnr]
        p.error("brreg", f"live entity lookup failed ({f.status or f.error}); used the supplied registry snapshot")
    if ent is None:
        p.error("brreg", f"entity lookup failed ({f.status or f.error})")
        p.notes["entity_missing"] = True
        for fam in FAMILIES:
            p.mark(fam, "failed", "The official register did not return this organisation number, so nothing could be anchored")
        trace["runtime_ms"] = int((time.monotonic() - t0) * 1000)
        return p, trace
    p.notes["entity"] = ent
    await registry.add_registry(ctx.client, p, ent, f)
    trace["t_entity_ms"] = int((time.monotonic() - t0) * 1000)
    people, subunits, years = await asyncio.gather(
        registry.add_roles(ctx.client, p, orgnr),
        registry.add_subunits(ctx.client, p, orgnr),
        registry.add_financials(ctx.client, p, orgnr),
    )
    p.notes["subunits"] = subunits
    p.notes["financial_years"] = years

    # --- run-wide connectors start now and run alongside website discovery ----------------
    async def connectors() -> None:
        async def one(src) -> None:
            await src.wait_ready()
            await _enrich(ctx, src, p, ent, subunits, [])
        await asyncio.gather(*(one(src) for src in ctx.sources if not src.late))
    connector_task = asyncio.create_task(connectors())

    # --- website discovery and verification -------------------------------------------
    trace["t_registry_ms"] = int((time.monotonic() - t0) * 1000)
    cands = candidates(ent, subunits)
    have = {c.domain for c in cands}
    for src in ctx.sources:
        if hasattr(src, "website_candidates") and src._task is not None and not src._task.done():
            try:
                await asyncio.wait_for(asyncio.shield(src._task), timeout=5)
            except asyncio.TimeoutError:
                continue  # still downloading: discovery goes on without its candidates
        for url in getattr(src, "website_candidates", lambda o: [])(orgnr):
            d = domain_of(url)
            if d and d not in have:
                cands.insert(0, Candidate(d, getattr(src, "candidate_origin", "wikidata_website"), url))
                have.add(d)
    exists = await asyncio.gather(*(ctx.resolver.exists(c.domain) for c in cands))
    live = [c for c, ok in zip(cands, exists) if ok]
    trace["t_dns_ms"] = int((time.monotonic() - t0) * 1000)
    trace["candidates"] = [{"domain": c.domain, "origin": c.origin, "dns": ok} for c, ok in zip(cands, exists)]
    declared = [c for c in live if c.declared]
    guessed = [c for c in live if not c.declared][:MAX_NAME_CANDIDATES]
    p.checked_source("website", "register website and e-mail fields")
    p.checked_source("website", f"{len(cands)} domain candidates ({len(live)} resolve in DNS)")
    exact: list[SiteResult] = []
    seen_domains: set[str] = set()
    for group in (declared, guessed):
        results = await asyncio.gather(*(crawl(ctx.client, c) for c in group))
        for res in results:
            res = verify(res, ent, subunits, orgnr, people)
            res = await sibling_check(ctx.client, res, ent, orgnr, subunits)
            trace["sites"].append({"domain": res.candidate.domain, "origin": res.candidate.origin, "status": res.status,
                                   "reason": res.reason, "final": res.home.final_url if res.home else None,
                                   "proofs": [pr.kind for pr in res.proofs]})
            same_site = res.home and any(res.home.sha256 == x.home.sha256 or res.home.title == x.home.title for x in exact)
            # a second website is published only when it, too, shows the organisation number
            second_ok = not exact or any(pr.kind == "orgnr" for pr in res.proofs)
            if res.status == "exact" and res.domain not in seen_domains and not same_site and second_ok and len(exact) < MAX_EXACT_SITES:
                seen_domains.add(res.domain)
                exact.append(res)
        if exact and group is declared:
            break
    await asyncio.gather(*(complete(ctx.client, r) for r in exact))
    for res in sorted(exact, key=lambda r: -r.score):
        extract.add_website(p, res)
        found = extract.add_site_claims(p, res, ent)
        try:
            n = await extract.add_feed_items(ctx.client, p, res, found["feeds"], ent)
            if not n:
                extract.news_from_pages(p, res)
        except Exception as exc:  # a broken feed never breaks the profile
            p.error("website_feed", repr(exc))
    if not exact:
        statuses = {s["status"] for s in trace["sites"]}
        if "blocked" in statuses:
            p.mark("website", "blocked", "A candidate site disallows automated access in robots.txt")
        elif "ambiguous" in statuses or "other_entity" in statuses:
            p.mark("website", "ambiguous", "Candidate sites were found but none proved it belongs to this exact entity")
        else:
            p.mark("website", "not_available", "No website declared in the register and no derived domain resolved to a site for this entity")
    for fam in ("social", "contact"):
        p.checked_source(fam, "verified company website" if exact else "no verified website")

    trace["t_website_ms"] = int((time.monotonic() - t0) * 1000)
    trace["t_website_done_ms"] = int((time.monotonic() - t0) * 1000)
    try:
        await connector_task
    except asyncio.CancelledError:
        connector_task.cancel()
        raise
    p.notes["late_args"] = (ent, subunits, exact, cands, orgnr)
    trace["runtime_ms"] = int((time.monotonic() - t0) * 1000)
    return p, trace


async def _enrich(ctx: Context, src, p: Profile, ent: dict, subunits: list, exact: list) -> None:
    try:
        await src.enrich(ctx, p, ent, subunits, exact)
    except Exception as exc:  # each connector fails alone
        p.error(getattr(src, "name", "connector"), repr(exc))
        for fam in getattr(src, "families", []):
            if not p.family_claims(fam):
                p.mark(fam, "failed", f"{getattr(src, 'name', 'connector')} failed: {type(exc).__name__}")


async def finish(ctx: Context, p: Profile, trace: dict) -> None:
    """Late sources (they wait for a run-wide index) and anything they unlock, after the research slot."""
    ent, subunits, exact, cands, orgnr = p.notes.pop("late_args")
    people = [c.value for c in p.family_claims("people") if c.field == "registered_role"]
    async def one(src) -> None:
        await src.wait_ready()
        await _enrich(ctx, src, p, ent, subunits, exact)
    await asyncio.gather(*(one(src) for src in ctx.sources if src.late))
    # employer homepages stated in matched job ads are one more declared candidate
    if not exact and p.notes.get("nav_homepages"):
        extra = []
        for url in dict.fromkeys(p.notes["nav_homepages"]):
            d = domain_of(url)
            if d and d not in {c.domain for c in cands} and await ctx.resolver.exists(d):
                extra.append(Candidate(d, "job_ad_homepage", url))
        for res in await asyncio.gather(*(crawl(ctx.client, c) for c in extra[:2])):
            res = verify(res, ent, subunits, orgnr, people)
            trace["sites"].append({"domain": res.candidate.domain, "origin": res.candidate.origin, "status": res.status,
                                   "reason": res.reason, "final": res.home.final_url if res.home else None,
                                   "proofs": [pr.kind for pr in res.proofs]})
            if res.status == "exact" and not exact:
                await complete(ctx.client, res)
                exact.append(res)
                p.states.pop("website", None)
                extract.add_website(p, res)
                extract.add_site_claims(p, res, ent)
