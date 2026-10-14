"""Run-wide connectors. Each one prepares once per run, then enriches each profile.

A connector must: use only keyless or publicly published access, obey the source's terms,
publish only facts tied to the exact organisation number, and fail alone.
"""
from __future__ import annotations

import argparse


class Source:
    name = "source"
    families: list[str] = []
    prepare_error: str | None = None

    async def prepare(self, ctx, orgs: list[str]) -> None:  # noqa: D401
        return None

    async def enrich(self, ctx, p, ent: dict, subunits: list[dict], sites: list) -> None:
        return None

    def report(self) -> dict:
        return {}


def default_sources(args: argparse.Namespace) -> list[Source]:
    out: list[Source] = []
    from .brreg_extra import BrregExtra
    out.append(BrregExtra())
    from .smilefjes import Smilefjes
    out.append(Smilefjes())
    from .ted import Ted
    out.append(Ted())
    from .finanstilsynet import Finanstilsynet
    out.append(Finanstilsynet())
    if not getattr(args, "no_jobs", False):
        from .nav_jobs import NavJobs
        out.append(NavJobs())
    if not getattr(args, "no_wikidata", False):
        from .wikidata import Wikidata
        out.append(Wikidata())
    return out
