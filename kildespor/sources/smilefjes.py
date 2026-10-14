"""Mattilsynet food-safety inspections ("smilefjes"), open data under NLOD.

One CSV download per run, indexed by organisation number. Inspections are registered on the
workplace (subunit) number, so we match the company's own number and its registered subunits.
"""
from __future__ import annotations

import csv
import io

from ..claims import Claim, Evidence
from . import Source

URL = "https://matnyttig.mattilsynet.no/smilefjes/tilsyn.csv"
GRADE = {"0": "smiling face (no remarks)", "1": "smiling face (minor remarks)", "2": "straight face", "3": "sad face"}


class Smilefjes(Source):
    name = "smilefjes"
    families = ["activity", "locations"]

    def __init__(self) -> None:
        self.by_org: dict[str, list[dict]] = {}
        self.meta: dict = {}
        self.matched = 0

    async def prepare(self, ctx, orgs: list[str]) -> None:
        f = await ctx.client.get(self.name, URL, max_body=60_000_000, retries=2, timeout=90)
        if not f.ok:
            raise RuntimeError(f"smilefjes CSV unavailable ({f.status or f.error})")
        self.meta = {"at": f.retrieved_at, "sha": f.sha256, "status": f.status}
        text = f.body.decode("utf-8-sig", errors="replace")
        for row in csv.DictReader(io.StringIO(text), delimiter=";"):
            org = (row.get("orgnummer") or "").strip()
            if len(org) == 9:
                self.by_org.setdefault(org, []).append(row)

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        if self.prepare_error:
            raise RuntimeError(self.prepare_error)
        p.checked_source("activity", "Mattilsynet food inspections")
        own = [(p.orgnr, "exact")] + [(u["organisation_number"], "registered_subunit") for u in subunits if u.get("organisation_number")]
        hit = False
        for org, rel in own:
            rows = self.by_org.get(org, [])
            if not rows:
                continue
            hit = True
            rows = sorted(rows, key=lambda r: (r.get("dato") or "")[4:8] + (r.get("dato") or "")[2:4] + (r.get("dato") or "")[:2], reverse=True)
            place = rows[0]
            addr = ", ".join(x for x in (place.get("adrlinje1"), f"{place.get('postnr', '')} {place.get('poststed', '')}".strip()) if x)
            span0 = f"orgnummer {org} · {place.get('navn')} · {addr}"
            ev0 = [Evidence(URL, "official_registry", self.meta["at"], self.meta["sha"], span0, "smilefjes_csv_orgnr",
                            http_status=self.meta["status"], source_name="Mattilsynet")]
            p.add(Claim("locations", "food_outlet", {"name": place.get("navn"), "address": addr, "organisation_number": org},
                        ev0, label="Food outlet inspected by Mattilsynet", relationship=rel,
                        key=f"locations:food_outlet:{org}"))
            for r in rows[:8]:
                d = r.get("dato") or ""
                iso = f"{d[4:8]}-{d[2:4]}-{d[:2]}" if len(d) == 8 else None
                grade = GRADE.get((r.get("total_karakter") or "").strip(), r.get("total_karakter"))
                span = f"{r.get('navn')} · tilsyn {r.get('tilsynid')} · dato {d} · total_karakter {r.get('total_karakter')}"
                p.add(Claim("activity", "food_inspection",
                            {"title": f"Food-safety inspection at {r.get('navn')}: {grade}", "grade": r.get("total_karakter"),
                             "place": r.get("navn"), "url": "https://smilefjes.mattilsynet.no/", "source": "Mattilsynet"},
                            [Evidence(URL, "official_registry", self.meta["at"], self.meta["sha"], span, "smilefjes_csv_orgnr",
                                      http_status=self.meta["status"], source_name="Mattilsynet")],
                            label="Food-safety inspection", effective_date=iso, relationship=rel,
                            key=f"activity:food_inspection:{r.get('tilsynid')}"))
        if hit:
            self.matched += 1

    def report(self) -> dict:
        return {"organisations_in_file": len(self.by_org), "companies_matched": self.matched}
