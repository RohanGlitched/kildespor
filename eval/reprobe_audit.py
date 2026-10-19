"""Re-check audited websites with the current identity rules.

    python eval/reprobe_audit.py <verdicts.jsonl> <run envelopes.jsonl> [<more envelopes.jsonl> ...]

For each audited company, the candidate (same domain and origin as in the traced run) is crawled and verified
again, and the outcome is compared with the auditor's verdict.
"""
import asyncio
import json
import sys
import urllib.request

sys.path.insert(0, ".")
from kildespor.discovery import Candidate, registrable  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.site import crawl, sibling_check, unique_name_check, verify  # noqa: E402


def origins(paths):
    out = {}
    for path in paths:
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            for s in (e.get("discovery_trace") or {}).get("sites", []):
                if s["status"] == "exact":
                    out.setdefault(e["organisation_number"], (s["domain"], s["origin"]))
    return out


def brreg(path):
    return json.loads(urllib.request.urlopen("https://data.brreg.no/enhetsregisteret/api/" + path).read())


async def main() -> None:
    verdicts = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8")]
    found = origins(sys.argv[2:])
    c = Client(8)
    for v in verdicts:
        org = v["organisation_number"]
        if org not in found:
            print(f"{org} {v['legal_name']}: not in the traced runs")
            continue
        domain, origin = found[org]
        ent = brreg(f"enheter/{org}")
        try:
            units = (brreg(f"underenheter?overordnetEnhet={org}&size=100").get("_embedded") or {}).get("underenheter") or []
        except Exception:
            units = []
        subunits = [{"organisation_number": u.get("organisasjonsnummer"), "address": ", ".join((u.get("beliggenhetsadresse") or {}).get("adresse") or [])
                     + f", {(u.get('beliggenhetsadresse') or {}).get('postnummer', '')} {(u.get('beliggenhetsadresse') or {}).get('poststed', '')}",
                     "municipality": (u.get("beliggenhetsadresse") or {}).get("kommune"), "telefon": u.get("telefon"),
                     "mobil": u.get("mobil"), "epost": u.get("epostadresse")} for u in units]
        roles = brreg(f"enheter/{org}/roller")
        people = [{"kind": "person", "name": " ".join(x for x in [(r.get("person") or {}).get("navn", {}).get("fornavn"),
                                                                 (r.get("person") or {}).get("navn", {}).get("mellomnavn"),
                                                                 (r.get("person") or {}).get("navn", {}).get("etternavn")] if x)}
                  for g in roles.get("rollegrupper", []) for r in g.get("roller", []) if r.get("person")]
        res = await crawl(c, Candidate(domain, origin, domain))
        res = verify(res, ent, subunits, org, people)
        res = await unique_name_check(c, res, ent, org, subunits, people)
        res = await sibling_check(c, res, ent, org, subunits)
        ok = (res.status == "exact") == (v["verdict"] in ("correct", "related_acceptable"))
        print(f"{'OK ' if ok else 'BAD'} {v['verdict']:18s} -> {res.status:12s} {v['legal_name'][:30]:30s} {domain:28s} {origin:16s} "
              f"{[p.kind for p in res.proofs]} {res.reason[:70] if res.status != 'exact' else ''}")
    await c.close()


asyncio.run(main())
