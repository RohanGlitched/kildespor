"""Fagfolkguiden company pages (tradespeople directory).

Each page lives at /bedrift/{slug}-{orgnr} (robots.txt allows /bedrift/) and embeds a LocalBusiness
JSON-LD block whose identifier is the organisation number, with the Google aggregate rating the page
displays. We publish the rating only when that identifier equals our organisation number; no review
text is collected.
"""
from __future__ import annotations

import json
import re
import unicodedata

from ..claims import Claim, Evidence
from . import Source

BASE = "https://www.fagfolkguiden.no/bedrift/{}-{}"


def slug(value: str) -> str:
    text = str(value or "").translate(str.maketrans({"ø": "o", "å": "a", "æ": "ae", "Ø": "O", "Å": "A", "Æ": "AE"}))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return "-".join(re.findall(r"[a-z0-9]+", text))


class Fagfolkguiden(Source):
    late = True  # does not feed website discovery: runs after the research slot
    name = "fagfolkguiden"
    families = ["reviews"]

    def __init__(self) -> None:
        self.pages = 0
        self.rated = 0

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        url = BASE.format(slug(ent.get("navn", "")), p.orgnr)
        f = await ctx.client.get(self.name, url, retries=1)
        p.checked_source("reviews", "Fagfolkguiden company page (Google rating it displays)")
        if f.blocked or not f.ok:
            return
        text = f.text()
        node = None
        for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', text, re.S):
            try:
                data = json.loads(m.group(1), strict=False)
            except ValueError:
                continue
            for d in data if isinstance(data, list) else [data]:
                if isinstance(d, dict) and str((d.get("identifier") or {}).get("value", "")) == p.orgnr:
                    node = d
        if node is None:
            return  # the page does not state our organisation number: not published
        self.pages += 1
        r = node.get("aggregateRating") or {}
        if r.get("ratingValue") is None or not r.get("ratingCount"):
            return
        self.rated += 1
        span = f"identifier Organisasjonsnummer {p.orgnr} · aggregateRating {r.get('ratingValue')}/{r.get('bestRating', 5)} from {r.get('ratingCount')} ratings"
        p.add(Claim("reviews", "customer_rating", {"rating": r.get("ratingValue"), "best": r.get("bestRating", 5), "count": r.get("ratingCount"),
                                                   "platform": "Google rating shown on Fagfolkguiden", "url": url},
                    [Evidence(url, "public_directory", f.retrieved_at, f.sha256, span, "jsonld_identifier_orgnr", final_url=f.final_url,
                              http_status=f.status, source_name="Fagfolkguiden")],
                    label="Customer rating", confidence=0.95,
                    attributes={"note": "aggregate of Google reviews as displayed by Fagfolkguiden; no review text collected"},
                    key="reviews:customer_rating:fagfolkguiden"))

    def report(self) -> dict:
        return {"exact_pages": self.pages, "rated": self.rated}
