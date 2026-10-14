"""Wikidata (CC0): items carrying the Norwegian organisation number (P2333).

One batched SPARQL query per run. The organisation number is the join key, so a match is exact
by construction; we still require the item's P2333 value to equal ours character for character.
"""
from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

from ..claims import Claim, Evidence
from . import Source

ENDPOINT = "https://query.wikidata.org/sparql"
PROPS = {
    "P856": ("website", "official_website_wikidata"),
    "P2013": ("social", "facebook"),
    "P2003": ("social", "instagram"),
    "P4264": ("social", "linkedin"),
    "P2397": ("social", "youtube"),
    "P2002": ("social", "x"),
    "P7085": ("social", "tiktok"),
    "P414": ("identity", "stock_exchange"),
    "P249": ("identity", "ticker"),
    "P1128": ("identity", "employees_wikidata"),
    "P571": ("identity", "inception"),
    "P159": ("locations", "headquarters"),
    "P749": ("identity", "parent_organisation"),
    "P452": ("description", "industry_wikidata"),
}
URL = {
    "facebook": "https://www.facebook.com/{}", "instagram": "https://www.instagram.com/{}",
    "linkedin": "https://www.linkedin.com/company/{}", "youtube": "https://www.youtube.com/channel/{}",
    "x": "https://x.com/{}", "tiktok": "https://www.tiktok.com/@{}",
}


class Wikidata(Source):
    name = "wikidata"
    families = ["social", "website", "identity"]

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.meta: dict[str, dict] = {}
        self.matched = 0

    async def prepare(self, ctx, orgs: list[str]) -> None:
        for i in range(0, len(orgs), 1200):
            chunk = orgs[i: i + 1200]
            values = " ".join(f'"{o}"' for o in chunk)
            props = " ".join(f"wdt:{p}" for p in PROPS)
            q = f"""SELECT ?item ?itemLabel ?orgnr ?prop ?value ?valueLabel WHERE {{
  VALUES ?orgnr {{ {values} }}
  ?item wdt:P2333 ?orgnr .
  OPTIONAL {{ VALUES ?prop {{ {props} }} ?item ?prop ?value . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "nb,nn,en". }}
}}"""
            f = None
            for attempt in range(3):
                f = await ctx.client.post(self.name, ENDPOINT, ("query=" + quote(q)).encode(), retries=0,
                                          headers={"Accept": "application/sparql-results+json",
                                                   "Content-Type": "application/x-www-form-urlencoded"})
                if f.ok:
                    break
                await asyncio.sleep(20 * (attempt + 1))
            if not f.ok:
                raise RuntimeError(f"Wikidata query failed: {f.status or f.error}")
            data = json.loads(f.body)
            for b in data["results"]["bindings"]:
                org = b["orgnr"]["value"]
                self.rows.setdefault(org, []).append(b)
                self.meta[org] = {"url": f.url, "sha": f.sha256, "at": f.retrieved_at, "status": f.status}

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        if self.prepare_error:
            raise RuntimeError(self.prepare_error)
        rows = self.rows.get(p.orgnr)
        for fam in ("social",):
            p.checked_source(fam, "Wikidata (P2333)")
        if not rows:
            return
        self.matched += 1
        m = self.meta[p.orgnr]
        item = rows[0]["item"]["value"]
        qid = item.rsplit("/", 1)[-1]
        label = rows[0].get("itemLabel", {}).get("value", qid)

        def ev(span: str) -> list[Evidence]:
            return [Evidence(item, "open_knowledge_base", m["at"], m["sha"], span, "wikidata_sparql_p2333",
                             final_url=m["url"], http_status=m["status"], source_name="Wikidata")]

        p.add(Claim("identity", "wikidata_item", {"id": qid, "url": item, "label": label}, ev(f"{qid} P2333 {p.orgnr}"),
                    label="Wikidata item", confidence=0.99, key=f"identity:wikidata_item:{qid}"))
        seen = set()
        for b in rows:
            if "prop" not in b:
                continue
            prop = b["prop"]["value"].rsplit("/", 1)[-1]
            raw = b["value"]["value"]
            shown = b.get("valueLabel", {}).get("value", raw)
            if (prop, raw) in seen or prop not in PROPS:
                continue
            seen.add((prop, raw))
            fam, kind = PROPS[prop]
            span = f"{qid} {prop}: {shown}"
            if fam == "social":
                url = URL[kind].format(raw)
                p.add(Claim("social", "company_profile", {"platform": kind, "url": url, "handle": raw}, ev(span),
                            label=f"{kind.title() if kind != 'x' else 'X'} profile", confidence=0.95,
                            key=f"social:company_profile:{url.lower().rstrip('/')}"))
            elif fam == "website":
                p.add(Claim("website", "website_listed_in_wikidata", raw, ev(span), label="Website listed in Wikidata",
                            confidence=0.9))
            elif kind == "headquarters":
                p.add(Claim("locations", "headquarters", shown, ev(span), label="Headquarters (Wikidata)", confidence=0.9))
            elif kind == "employees_wikidata":
                p.add(Claim("identity", kind, shown, ev(span), label="Employees (Wikidata)", confidence=0.85))
            elif kind == "inception":
                p.add(Claim("identity", kind, raw[:10], ev(span), label="Inception (Wikidata)", effective_date=raw[:10], confidence=0.9))
            else:
                p.add(Claim(fam, kind, shown, ev(span), label={"stock_exchange": "Listed on", "ticker": "Ticker",
                                                                "parent_organisation": "Parent organisation",
                                                                "industry_wikidata": "Industry (Wikidata)"}[kind],
                            confidence=0.9, relationship="group_member" if kind == "parent_organisation" else "exact"))

    def website_candidates(self, orgnr: str) -> list[str]:
        return [b["value"]["value"] for b in self.rows.get(orgnr, []) if b.get("prop", {}).get("value", "").endswith("/P856")]

    def report(self) -> dict:
        return {"companies_with_items": len(self.rows), "matched": self.matched}
