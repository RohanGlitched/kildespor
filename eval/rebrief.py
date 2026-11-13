"""Rebuild profiles from an envelopes.jsonl and print the buyer brief, to iterate on the summary without a crawl.

    python eval/rebrief.py <envelopes.jsonl> [N] [--json out.jsonl]
"""
from __future__ import annotations

import json
import sys

from kildespor import brief
from kildespor.claims import Claim, Evidence, FieldState, Profile


def rebuild(env: dict) -> Profile:
    p = Profile(env["organisation_number"])
    ev = {e["id"]: e for e in env.get("evidence", [])}
    for c in env.get("claims", []):
        evs = [Evidence(e["source_url"], e["source_class"], e["retrieved_at"], e["content_sha256"], e["claim_span"],
                        e.get("extraction_method", ""), source_name=e.get("source_name", ""), id=e["id"])
               for e in (ev.get(i) for i in c.get("evidence_ids", [])) if e]
        value = c.get("details") if isinstance(c.get("details"), dict) else c.get("value")
        p.add(Claim(c["family"], c["field"], value, evs, label=c.get("label", ""), effective_date=c.get("effective_date"),
                    reporting_period=c.get("reporting_period"), confidence=c.get("confidence", 0.99), key=c["key"]))
    for s in env.get("field_states", []):
        if s.get("state") != "available":
            p.states[s["family"]] = FieldState(s["family"], s["state"], s.get("note", ""))
    return p


def main() -> None:
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 40
    for i, line in enumerate(open(path, encoding="utf-8")):
        if i >= n:
            break
        env = json.loads(line)
        b = brief.brief(rebuild(env), env.get("changes"))
        print("##", env.get("legal_name"), env["organisation_number"])
        print("H:", b["headline"])
        print("T:", b["text"])
        print()


if __name__ == "__main__":
    main()
