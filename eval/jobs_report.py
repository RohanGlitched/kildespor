"""Jobs-family summary of a run, for before/after comparisons and hand-checks.

python eval/jobs_report.py out/run/envelopes.jsonl [--list]
Prints: companies with >=1 open job posting, postings by source, careers pages, recruitment channels, the run's
runtime and request count, and the NAV index report (coverage, time). --list prints every jobs claim to hand-check.
"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(path: str, show: bool) -> None:
    envs = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    by_kind: collections.Counter = collections.Counter()
    companies: dict[str, set] = collections.defaultdict(set)
    rows = []
    for e in envs:
        for c in e["claims"]:
            if c["family"] != "jobs":
                continue
            v = c["value"] if isinstance(c["value"], dict) else (c.get("details") or {})
            if c["field"] == "job_posting":
                if v.get("status") == "closed":
                    kind = "job_posting/closed"
                else:
                    kind = "job_posting/" + ("nav" if ":nav:" in c["key"] else v.get("platform") or "site")
            else:
                kind = c["field"]
            by_kind[kind] += 1
            companies[kind].add(e["organisation_number"])
            rows.append((e["organisation_number"], e.get("legal_name", ""), kind, v))
    open_cos = set().union(*[s for k, s in companies.items() if k.startswith("job_posting/") and k != "job_posting/closed"] or [set()])
    print(f"companies: {len(envs)}   with >=1 open posting: {len(open_cos)}")
    for k in sorted(by_kind):
        print(f"  {k:28} items {by_kind[k]:4}   companies {len(companies[k]):4}")
    rep_path = Path(path).parent / "run-report.json"
    if rep_path.exists():
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        ops = rep.get("operations") or {}
        print(f"runtime {rep.get('runtime_seconds')} s   requests {ops.get('requests')}   by source "
              f"{ {k: v for k, v in (ops.get('by_source') or {}).items() if k in ('nav_jobs', 'nav_jobs_index', 'careers', 'website')} }")
        for s in rep.get("sources") or []:
            if s.get("name") in ("nav_jobs", "careers"):
                print(s.get("name"), json.dumps({k: v for k, v in s.items() if k not in ("name",)}, ensure_ascii=False))
    if show:
        for org, name, kind, v in sorted(rows, key=lambda r: (r[2], r[1])):
            due = v.get("deadline") or v.get("application_due") or v.get("application_due_text") or ""
            print(f"{org} {name[:30]:30} | {kind:22} | {str(v.get('title') or v.get('platform') or '')[:55]:55} | due {str(due)[:10]:10} | {v.get('url')}")


if __name__ == "__main__":
    main(sys.argv[1], "--list" in sys.argv)
