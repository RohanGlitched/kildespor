"""Finanstilsynet's register of supervised entities (keyless public API).

The search is free text, so a hit is used only when the register's own organisation number equals
ours. Licences are published with their type, role and registration date.
"""
from __future__ import annotations

import json

from ..claims import Claim, Evidence
from . import Source

SEARCH = "https://api.finanstilsynet.no/registry/v2/legal-entities/search?query={}"
DETAIL = "https://api.finanstilsynet.no/registry/v2/legal-entities?ids={}"
PUBLIC = "https://www.finanstilsynet.no/virksomhetsregisteret/"


class Finanstilsynet(Source):
    late = True  # does not feed website discovery: runs after the research slot
    name = "finanstilsynet"
    families = ["identity", "activity"]

    def __init__(self) -> None:
        self.matched = 0

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        f = await ctx.client.get(self.name, SEARCH.format(p.orgnr), headers={"Accept": "application/json"}, check_robots=False,
                                 retries=1)
        p.checked_source("identity", "Finanstilsynet register")
        if not f.ok:
            return
        hits = [h for h in (json.loads(f.body).get("legalEntities") or []) if h.get("organisationNumber") == p.orgnr]
        if not hits:
            return
        h = hits[0]
        d = await ctx.client.get(self.name, DETAIL.format(h["legalEntityId"]), headers={"Accept": "application/json"},
                                 check_robots=False, retries=1, max_body=8_000_000)
        ev_s = Evidence(SEARCH.format(p.orgnr), "official_registry", f.retrieved_at, f.sha256,
                        f"organisationNumber {p.orgnr} · {h.get('name')} · {h.get('finanstilsynetId')}", "finanstilsynet_exact_orgnr",
                        http_status=f.status, source_name="Finanstilsynet")
        self.matched += 1
        p.add(Claim("identity", "financial_supervision", {"id": h.get("finanstilsynetId"), "label": h.get("name"), "url": PUBLIC,
                                                          "lei": h.get("leiCode"), "type": h.get("legalEntityType")},
                    [ev_s], label="Registered with Finanstilsynet", key=f"identity:financial_supervision:{h.get('finanstilsynetId')}"))
        if h.get("leiCode"):
            p.add(Claim("identity", "lei_code", h["leiCode"], [ev_s], label="LEI code"))
        if not d.ok:
            return
        rows = (json.loads(d.body).get("legalEntities") or [{}])[0].get("licences") or []
        for lic in rows[:20]:
            t = lic.get("licenceType") or {}
            name = (t.get("name") or {}).get("norwegian") or t.get("code")
            role = lic.get("serviceProviderType") or "Licence holder"
            principal = (lic.get("licensedEntity") or {}).get("legalEntityName")
            when = (lic.get("registeredDate") or "")[:10] or None
            title = f"{name}" + (f" ({role} for {principal})" if principal and principal != h.get("name") else "")
            ev = Evidence(DETAIL.format(h["legalEntityId"]), "official_registry", d.retrieved_at, d.sha256,
                          f"licence {t.get('code')} {name} · {role} · registeredDate {when}", "finanstilsynet_licence",
                          http_status=d.status, source_name="Finanstilsynet")
            p.add(Claim("identity", "financial_licence", {"title": title, "code": t.get("code"), "role": role, "url": PUBLIC},
                        [ev], label="Financial licence", effective_date=when,
                        key=f"identity:financial_licence:{t.get('code')}:{principal}:{when}"))
            if when:
                p.add(Claim("activity", "licence_registered", {"title": f"Licence registered: {title}", "url": PUBLIC,
                                                               "source": "Finanstilsynet"},
                            [ev], label="Licence registered", effective_date=when,
                            key=f"activity:licence_registered:{t.get('code')}:{principal}:{when}"))

    def report(self) -> dict:
        return {"companies_matched": self.matched}
