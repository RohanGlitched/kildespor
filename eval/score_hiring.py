import json
import sys

labels = {json.loads(l)["organisation_number"]: set(json.loads(l)["expected_nav_ads"]) for l in open(sys.argv[1], encoding="utf-8")}
envs = {json.loads(l)["organisation_number"]: json.loads(l) for l in open(sys.argv[2], encoding="utf-8")}
hit_c = hit_a = tot_a = 0
for org, ads in labels.items():
    e = envs[org]
    got = {c["value"].get("uuid") for c in e["claims"] if c["field"] == "job_posting" and isinstance(c["value"], dict)}
    found = ads & got
    tot_a += len(ads)
    hit_a += len(found)
    hit_c += bool(found)
    if not found:
        print("MISS", org, e.get("legal_name"), "jobs found:", len(got))
print(f"companies {hit_c}/{len(labels)}  ads {hit_a}/{tot_a}")
