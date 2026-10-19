"""Compare official websites and social coverage between two runs on the same companies."""
import json
import sys


def sites(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        c = [x for x in e["claims"] if x["field"] == "official_website"]
        out[e["organisation_number"]] = (e["legal_name"], [((x.get("details") or x["value"])["domain"], ",".join((x.get("details") or x["value"]).get("identity_proof"))) for x in c],
                                         sum(1 for x in e["claims"] if x["family"] == "social"))
    return out


a, b = sites(sys.argv[1]), sites(sys.argv[2])
for o in b:
    if o in a and b[o][1] != a[o][1]:
        print(o, b[o][0], "|", a[o][1], "->", b[o][1], "| social", a[o][2], "->", b[o][2])
print("websites", sum(1 for o in a if a[o][1]), "->", sum(1 for o in b if b[o][1]))
print("companies with social", sum(1 for o in a if a[o][2]), "->", sum(1 for o in b if b[o][2]))
