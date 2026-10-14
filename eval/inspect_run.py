"""Quick look at a run: per-company families, websites found, and the discovery trace."""
import collections
import json
import sys

path = sys.argv[1]
verbose = "-v" in sys.argv
envs = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
fam = collections.Counter()
for e in envs:
    fams = sorted({c["family"] for c in e["claims"]})
    for f in fams:
        fam[f] += 1
    site = next((c["value"] for c in e["claims"] if c["field"] == "official_website"), None)
    soc = [c["value"]["platform"] for c in e["claims"] if c["family"] == "social"]
    print(f'{e["organisation_number"]} {(e.get("legal_name") or "")[:38]:38} {len(e["claims"]):3} claims  site={site["domain"] + " via " + site["discovered_via"] + " " + ",".join(site["identity_proof"]) if site else "-"}  social={soc}')
    if verbose and "discovery_trace" in e:
        for s in e["discovery_trace"].get("sites", []):
            print(f'      {s["status"]:12} {s["origin"]:16} {s["domain"]:30} {s["reason"][:70]}')
    for err in e["errors"]:
        print("      ERR", err)
print(len(envs), "companies;", dict(fam))
