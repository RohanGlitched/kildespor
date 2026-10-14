"""Write the static profile viewer for a run (opens from disk; no server needed)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .claims import FAMILIES

WEB = Path(__file__).parent / "web"


def _index_row(env: dict) -> dict:
    claims = env.get("claims", [])
    states = {s["family"]: s["state"] for s in env.get("field_states", [])}
    get = lambda fam, field: next((c for c in claims if c["family"] == fam and c["field"] == field), None)  # noqa: E731
    revs = sorted((c for c in claims if c["field"] == "revenue"), key=lambda c: c["value"]["year"])
    site = get("website", "official_website")
    return {
        "org": env["organisation_number"],
        "name": env.get("legal_name") or env["organisation_number"],
        "muni": str((get("identity", "municipality") or {}).get("value") or "").title(),
        "industry": ((get("identity", "industry") or {}).get("value") or "").split(" ", 1)[-1],
        "domain": site["value"]["domain"] if site else "",
        "facts": len(claims),
        "social": sum(1 for c in claims if c["family"] == "social"),
        "jobs": sum(1 for c in claims if c["field"] == "job_posting" and (c["value"] or {}).get("status") != "closed"),
        "changes": len(env.get("changes") or []),
        "revenue": revs[-1]["value"]["amount"] if revs else None,
        "ribbon": [states.get(f, "not_available") for f in FAMILIES],
    }


def write_viewer(results: dict, orgs: list[str], report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "data" / "c").mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "style.css"):
        shutil.copyfile(WEB / name, out / name)
    index = []
    for o in orgs:
        env = {k: v for k, v in results[o].items() if k != "discovery_trace"}
        index.append(_index_row(env))
        (out / "data" / "c" / f"{o}.js").write_text("KS.put(" + json.dumps(env, ensure_ascii=False, separators=(",", ":")) + ");\n",
                                                    encoding="utf-8")
    run = {k: report.get(k) for k in ("run_id", "agent", "started_at", "completed_at", "runtime_seconds", "companies", "claims",
                                      "evidence_records", "companies_with_claims_by_family", "validation", "operations", "changes")}
    payload = {"families": list(FAMILIES.items()), "index": index, "run": run}
    (out / "data" / "index.js").write_text("window.KS=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                           encoding="utf-8")
