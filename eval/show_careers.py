"""Print the job postings the careers source published (non-NAV) per company: python eval/show_careers.py envelopes.jsonl"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for line in open(sys.argv[1], encoding="utf-8"):
    e = json.loads(line)
    jp = [c for c in e["claims"] if c["field"] == "job_posting"]
    nav = [c for c in jp if c["key"].startswith("jobs:job_posting:nav")]
    new = [c for c in jp if not c["key"].startswith("jobs:job_posting:nav")]
    errs = [x["message"][:100] for x in e.get("errors", []) if x["source"] == "careers"]
    if new or errs or "-a" in sys.argv:
        print("=====", e["organisation_number"], e["legal_name"], "nav", len(nav), "other", len(new), errs)
    for c in new:
        v = c["value"]
        print("   ", v.get("platform"), "|", v.get("employer"), "|", v["title"][:70], "|", v.get("published"), v.get("application_due"),
              "|", v["url"][:100])
