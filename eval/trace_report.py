"""Summarise website discovery from a run made with --trace.

    python eval/trace_report.py <envelopes.jsonl> [--list ambiguous|blocked|exact] [--origin registry_website]
"""
import argparse
import collections
import json

ap = argparse.ArgumentParser()
ap.add_argument("envelopes")
ap.add_argument("--list", default="")
ap.add_argument("--origin", default="")
args = ap.parse_args()

rows = [json.loads(line) for line in open(args.envelopes, encoding="utf-8")]
state = collections.Counter()
grid = collections.Counter()
listed = []
for e in rows:
    fs = e["field_states"]
    st = fs["website"]["state"] if isinstance(fs, dict) else next((x["state"] for x in fs if x.get("family") == "website"), "?")
    state[st] += 1
    tr = e.get("discovery_trace") or {}
    for s in tr.get("sites", []):
        grid[(s["origin"], s["status"])] += 1
        if args.list and s["status"] == args.list and (not args.origin or s["origin"] == args.origin):
            listed.append((e["organisation_number"], e["legal_name"], s["origin"], s["domain"], s.get("final") or "", s.get("reason", "")))
print("website state per company:", dict(state))
print("\ncandidate sites crawled, by origin and outcome:")
for (o, s), n in sorted(grid.items()):
    print(f"  {o:20s} {s:14s} {n}")
for r in listed:
    print("\t".join(r))
