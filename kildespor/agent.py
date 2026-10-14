"""Research one organisation number end to end."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from . import extract, registry
from .claims import FAMILIES, Profile
from .discovery import Candidate, Resolver, candidates, domain_of, registrable
from .http import Client
from .site import SiteResult, complete, crawl, verify

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
    _, subunits, years = await asyncio.gather(
        registry.add_roles(ctx.client, p, orgnr),
        registry.add_subunits(ctx.client, p, orgnr),
        registry.add_financials(ctx.client, p, orgnr),
    )
    p.notes["subunits"] = subunits
    p.notes["financial_years"] = years

    # --- website discovery and verification -------------------------------------------
    trace["t_registry_ms"] = int((time.monotonic() - t0) * 1000)
    cands = candidates(ent, subunits)
    have = {c.domain for c in cands}
    for src in ctx.sources:
        for url in getattr(src, "website_candidates", lambda o: [])(orgnr):
            d = domain_of(url)
            if d and d not in have:
                cands.insert(0, Candidate(d, "wikidata_website", url))
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
            res = verify(res, ent, subunits, orgnr)
            trace["sites"].append({"domain": res.candidate.domain, "origin": res.candidate.origin, "status": res.status,
                                   "reason": res.reason, "final": res.home.final_url if res.home else None,
                                   "proofs": [pr.kind for pr in res.proofs]})
            same_site = res.home and any(res.home.sha256 == x.home.sha256 or res.home.title == x.home.title for x in exact)
            if res.status == "exact" and res.domain not in seen_domains and not same_site and len(exact) < MAX_EXACT_SITES:
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
    # --- run-wide connectors ------------------------------------------------------------
    for src in ctx.sources:
        try:
            await src.enrich(ctx, p, ent, subunits, exact)
        except Exception as exc:  # each connector fails alone
            p.error(getattr(src, "name", "connector"), repr(exc))
            for fam in getattr(src, "families", []):
                if not p.family_claims(fam):
                    p.mark(fam, "failed", f"{getattr(src, 'name', 'connector')} failed: {type(exc).__name__}")
    # employer homepages stated in matched job ads are one more declared candidate
    if not exact and p.notes.get("nav_homepages"):
        extra = []
        for url in dict.fromkeys(p.notes["nav_homepages"]):
            d = domain_of(url)
            if d and d not in {c.domain for c in cands} and await ctx.resolver.exists(d):
                extra.append(Candidate(d, "job_ad_homepage", url))
        for res in await asyncio.gather(*(crawl(ctx.client, c) for c in extra[:2])):
            res = verify(res, ent, subunits, orgnr)
            trace["sites"].append({"domain": res.candidate.domain, "origin": res.candidate.origin, "status": res.status,
                                   "reason": res.reason, "final": res.home.final_url if res.home else None,
                                   "proofs": [pr.kind for pr in res.proofs]})
            if res.status == "exact" and not exact:
                await complete(ctx.client, res)
                exact.append(res)
                p.states.pop("website", None)
                extract.add_website(p, res)
                extract.add_site_claims(p, res, ent)
    trace["runtime_ms"] = int((time.monotonic() - t0) * 1000)
    return p, trace
