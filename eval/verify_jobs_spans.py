"""Check that every jobs-family evidence span is literally in the archived response it cites.

python eval/verify_jobs_spans.py out/run/envelopes.jsonl
Uses the same normalisation as `python -m kildespor verify`, but for job postings, careers pages and recruitment links
(whose extraction methods the general verifier does not text-check). Spans joined with ' · ' must have every piece present.
"""
import html
import json
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _norm(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"[^0-9a-zæøå@.]+", "", text.lower())


def main(path: str) -> None:
    env_path = Path(path)
    z = zipfile.ZipFile(env_path.parent / "snapshots.zip")
    names = {n.split(".")[0]: n for n in z.namelist()}
    checked = ok = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        evs = {x["id"]: x for x in e["evidence"]}
        for c in e["claims"]:
            if c["family"] != "jobs":
                continue
            for i in c["evidence_ids"]:
                ev = evs[i]
                if ev["extraction_method"] in ("recruitment_link_on_verified_site", "outbound_link"):
                    continue  # a description of where the link was found, not a quote
                raw = z.read(names[ev["content_sha256"]]).decode("utf-8", "replace") if ev["content_sha256"] in names else ""
                hay = _norm(raw) + "|" + re.sub(r"[^0-9a-zæøå@.]+", "", html.unescape(raw).lower())
                pieces = [x for x in ev["claim_span"].split(" · ") if x.strip()]
                good = bool(raw) and all(_norm(x) in hay for x in pieces)
                checked += 1
                ok += good
                if not good:
                    print("MISS", e["organisation_number"], c["field"], ev["extraction_method"], ev["source_url"][:80], "|", ev["claim_span"][:120])
    print(f"jobs evidence spans checked {checked}, every piece found {ok}")


if __name__ == "__main__":
    main(sys.argv[1])
