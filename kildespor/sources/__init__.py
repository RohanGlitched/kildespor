"""Run-wide connectors. Each one prepares once per run, then enriches each profile.

A connector must: use only keyless or publicly published access, obey the source's terms,
publish only facts tied to the exact organisation number, and fail alone.
"""
from __future__ import annotations

import argparse
from asyncio import shield as asyncio_shield


class Source:
    name = "source"
    families: list[str] = []
    prepare_error: str | None = None
    late = False  # enriched after the company's research slot is released (waits for a slow run-wide index)
    _task = None

    def start(self, ctx, orgs: list[str]) -> None:
        import asyncio
        import sys
        import time

        async def run() -> None:
            t = time.monotonic()
            try:
                await self.prepare(ctx, orgs)
            except Exception as exc:  # a run-wide source that cannot start is reported per company
                self.prepare_error = repr(exc)
                print(f"warning: {self.name} could not start: {exc!r}", file=sys.stderr)
            self.prepare_seconds = round(time.monotonic() - t, 1)
        self._task = asyncio.create_task(run())

    async def wait_ready(self) -> None:
        if self._task is not None:
            await asyncio_shield(self._task)

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
    from .arbeidstilsynet import Arbeidstilsynet
    out.append(Arbeidstilsynet())
    from .fagfolkguiden import Fagfolkguiden
    out.append(Fagfolkguiden())
    if not getattr(args, "no_jobs", False):
        from .nav_jobs import NavJobs
        out.append(NavJobs())
    if not getattr(args, "no_wikidata", False):
        from .wikidata import Wikidata
        out.append(Wikidata())
    return out
