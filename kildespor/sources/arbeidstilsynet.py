"""Arbeidstilsynet's public approval registers (cleaning companies, occupational-health services).

One XML download per register per run, keyed by organisation number. A company in the register is an
official, dated-today fact about its approval status; the register's web address is one more declared
website candidate (it still has to be proven like any other).
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from ..claims import Claim, Evidence
from . import Source

REGISTERS = {
    "renhold": ("https://registerdata.arbeidstilsynet.no/renhold_register.xml", "Approved cleaning company (Renholdsregisteret)"),
    "bht": ("https://registerdata.arbeidstilsynet.no/bht_register.xml", "Approved occupational health service (BHT)"),
}


class Arbeidstilsynet(Source):
    name = "arbeidstilsynet"
    candidate_origin = "arbeidstilsynet_register"
    families = ["identity"]

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.matched = 0

    async def prepare(self, ctx, orgs: list[str]) -> None:
        wanted = set(orgs)
        for key, (url, label) in REGISTERS.items():
            f = await ctx.client.get(self.name, url, max_body=80_000_000, retries=2, timeout=90, check_robots=False)
            if not f.ok:
                continue
            try:
                root = ET.fromstring(f.body)
            except ET.ParseError:
                continue
            for v in root.iter("Virksomhet"):
                h = v.find("Hovedenhet")
                if h is None:
                    continue
                org = (h.findtext("Organisasjonsnummer") or "").strip()
                if org not in wanted:
                    continue
                self.rows.setdefault(org, []).append({
                    "register": key, "label": label, "url": url, "status": (h.findtext("Godkjenningsstatus") or "").strip(),
                    "name": (h.findtext("Navn") or "").strip(), "web": (h.findtext("Kontaktinformasjon/Webadresse") or "").strip(),
                    "at": f.retrieved_at, "sha": f.sha256, "http": f.status})

    def website_candidates(self, orgnr: str) -> list[str]:
        return [r["web"] for r in self.rows.get(orgnr, []) if r["web"]]

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        rows = self.rows.get(p.orgnr, [])
        if rows:
            self.matched += 1
        for r in rows:
            p.add(Claim("identity", "public_approval", {"title": f"{r['label']}: {r['status']}", "register": r["register"],
                                                        "status": r["status"], "url": "https://www.arbeidstilsynet.no/registre/"},
                        [Evidence(r["url"], "official_registry", r["at"], r["sha"],
                                  f"Organisasjonsnummer {p.orgnr} · {r['name']} · Godkjenningsstatus {r['status']}",
                                  "arbeidstilsynet_register_orgnr", http_status=r["http"], source_name="Arbeidstilsynet")],
                        label="Public approval", key=f"identity:public_approval:{r['register']}"))

    def report(self) -> dict:
        return {"companies_in_registers": len(self.rows), "matched": self.matched}
