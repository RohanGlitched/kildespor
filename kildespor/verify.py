"""Check a run's evidence against the raw bytes it was taken from.

    python -m kildespor verify --envelopes out/envelopes.jsonl

For every evidence record: the content hash must be in snapshots.zip, and for page-text evidence the
quoted span must actually occur in the archived page (whitespace and markup ignored).
"""
from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path

TEXT_METHODS = {"page_text_or_mailto", "page_text_or_tel", "address_pattern", "html_title", "meta_description", "news_listing_date",
                "careers_page", "identity_proof_orgnr", "identity_proof_phone", "identity_proof_email", "identity_proof_name_address",
                "identity_proof_legal_name", "identity_proof_legal_name_town", "identity_proof_role_holder_and_name"}


def _norm(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"[^0-9a-zæøå@.]+", "", text.lower())


def verify_run(envelopes: Path, archive: Path | None = None) -> dict:
    archive = archive or envelopes.parent / "snapshots.zip"
    z = zipfile.ZipFile(archive) if archive.exists() else None
    names = {n.split(".")[0]: n for n in z.namelist()} if z else {}
    cache: dict[str, str] = {}
    total = hashed = text_checked = text_found = 0
    missing: list[dict] = []
    for line in envelopes.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        env = json.loads(line)
        for ev in env.get("evidence", []):
            total += 1
            sha = ev.get("content_sha256")
            if sha not in names:
                if len(missing) < 20:
                    missing.append({"organisation_number": env["organisation_number"], "evidence": ev["id"], "reason": "hash not archived"})
                continue
            hashed += 1
            method = ev.get("extraction_method", "")
            if method not in TEXT_METHODS:
                continue
            if sha not in cache:
                raw = z.read(names[sha]).decode("utf-8", errors="replace")
                cache[sha] = _norm(raw) + "|" + re.sub(r"[^0-9a-zæøå@.]+", "", html.unescape(raw).lower())
            span = ev.get("claim_span", "")
            if ":" in span and method.startswith("identity_proof"):
                span = span.split(":", 1)[1]
            span = span.replace("…", " ")
            pieces = [p for p in re.split(r"\s{2,}| · |\.\.\.", span) if len(_norm(p)) >= 8]
            if not pieces:
                continue
            text_checked += 1
            if any(_norm(p)[:60] in cache[sha] for p in pieces):
                text_found += 1
            elif len(missing) < 20:
                missing.append({"organisation_number": env["organisation_number"], "evidence": ev["id"], "reason": "span not in page",
                                "span": span[:100]})
    return {"evidence_records": total, "hash_in_archive": hashed, "text_spans_checked": text_checked,
            "text_spans_found_in_page": text_found, "examples_of_misses": missing}
