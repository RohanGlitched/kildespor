"""TED (Tenders Electronic Daily): EU/EEA public-contract award notices won by the company.

Keyless search API. One query per 100 organisation numbers on the winner identifier; a notice is
published only when our exact organisation number is among its winner identifiers.
"""
from __future__ import annotations

import asyncio
import json

from ..claims import Claim, Evidence
from ..util import clip
from . import Source

API = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = ["publication-number", "notice-title", "publication-date", "winner-identifier", "winner-name", "notice-type", "buyer-name"]


def _text(v) -> str:
    if isinstance(v, dict):
        for lang in ("nor", "nob", "eng", "NOR", "ENG"):
            if v.get(lang):
                x = v[lang]
                return x[0] if isinstance(x, list) else x
        x = next(iter(v.values()), "")
        return x[0] if isinstance(x, list) else x
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


class Ted(Source):
    name = "ted"
    families = ["activity"]

    def __init__(self) -> None:
        self.by_org: dict[str, list[tuple[dict, dict]]] = {}
        self.queries = 0

    async def prepare(self, ctx, orgs: list[str]) -> None:
        for i in range(0, len(orgs), 100):
            chunk = orgs[i: i + 100]
            page = 1
            while page <= 5:
                body = json.dumps({"query": f"winner-identifier IN ({' '.join(chunk)})", "fields": FIELDS, "limit": 250,
                                   "page": page}).encode()
                f = await ctx.client.post(self.name, API, body, retries=4,
                                          headers={"Content-Type": "application/json", "Accept": "application/json"})
                await asyncio.sleep(1.5)  # TED rate-limits bursts
                self.queries += 1
                if not f.ok:
                    raise RuntimeError(f"TED search failed ({f.status or f.error})")
                data = json.loads(f.body)
                meta = {"at": f.retrieved_at, "sha": f.sha256, "status": f.status}
                for n in data.get("notices") or []:
                    for w in n.get("winner-identifier") or []:
                        w = "".join(ch for ch in str(w) if ch.isdigit())[-9:]
                        if w in chunk:
                            self.by_org.setdefault(w, []).append((n, meta))
                if len(data.get("notices") or []) < 250:
                    break
                page += 1

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        if self.prepare_error:
            raise RuntimeError(self.prepare_error)
        p.checked_source("activity", "TED public-contract awards")
        for n, meta in self.by_org.get(p.orgnr, [])[:25]:
            pub = n.get("publication-number")
            title = clip(_text(n.get("notice-title")), 200)
            when = (n.get("publication-date") or "")[:10] or None
            url = f"https://ted.europa.eu/en/notice/-/detail/{pub}"
            p.add(Claim("activity", "public_contract_award",
                        {"title": f"Public contract award: {title}", "buyer": clip(_text(n.get("buyer-name")), 120), "url": url,
                         "notice": pub, "source": "TED"},
                        [Evidence(url, "official_registry", meta["at"], meta["sha"],
                                  f"notice {pub} ({n.get('notice-type')}) winner-identifier {p.orgnr}: {title}", "ted_winner_identifier",
                                  http_status=meta["status"], source_name="TED (EU Publications Office)")],
                        label="Won a public contract", effective_date=when, key=f"activity:public_contract_award:{pub}"))

    def report(self) -> dict:
        return {"queries": self.queries, "companies_with_awards": len(self.by_org)}
