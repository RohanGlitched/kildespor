"""Write the static profile viewer for a run (opens from disk; no server needed)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .claims import FAMILIES

WEB = Path(__file__).parent / "web"
WEB_FILES = ("index.html", "app.js", "style.css")
ROUTINE_ACTIVITY = {"registry_update"}


def _index_row(env: dict) -> dict:
    """One compact row per company: enough to search, filter, sort and preview without loading the profile."""
    claims = [dict(c, value=c["details"]) if isinstance(c.get("details"), dict) else c for c in env.get("claims", [])]
    states = {s["family"]: s["state"] for s in env.get("field_states", [])}
    get = lambda fam, field: next((c for c in claims if c["family"] == fam and c["field"] == field), None)  # noqa: E731

    def latest(field: str) -> dict | None:
        rows = [c for c in claims if c["family"] == "financials" and c["field"] == field and isinstance(c.get("value"), dict)
                and c["value"].get("amount") is not None and c["value"].get("year")]
        return max(rows, key=lambda c: str(c["value"]["year"])) if rows else None

    revs = sorted((c for c in claims if c["field"] == "revenue" and isinstance(c.get("value"), dict)), key=lambda c: str(c["value"].get("year")))
    rev = revs[-1] if revs else None
    prev = next((c for c in revs if str(c["value"].get("year")) == str(int(rev["value"]["year"]) - 1)), None) if rev and str(rev["value"].get("year", "")).isdigit() else None
    res = latest("annual_result")
    site = get("website", "official_website")
    emp = get("identity", "registered_employees")
    form = (get("identity", "legal_form") or {}).get("value") or ""
    founded = str((get("identity", "founded") or {}).get("value") or "")[:4]
    industry = (get("identity", "industry") or {}).get("value") or ""
    roles = [c for c in claims if c["field"] == "registered_role" and isinstance(c.get("value"), dict)]
    lead = next((c for code in ("DAGL", "INNH", "LEDE") for c in roles if c["value"].get("role_code") == code), None)
    dated = [str(c.get("effective_date"))[:10] for c in claims
             if c["family"] == "activity" and c.get("effective_date") and c["field"] not in ROUTINE_ACTIVITY]
    return {
        "org": env["organisation_number"],
        "name": env.get("legal_name") or env["organisation_number"],
        "status": env.get("status", "available"),
        "muni": str((get("identity", "municipality") or {}).get("value") or "").title(),
        "industry": industry.split(" ", 1)[-1],
        "nace": industry.split(" ", 1)[0] if " " in industry else "",
        "form": form.split(" ", 1)[0],
        "founded": founded,
        "domain": site["value"]["domain"] if site else "",
        "proof": list(site["value"].get("identity_proof") or []) if site else [],
        "facts": len(claims),
        "evidence": len(env.get("evidence") or []),
        "social": sum(1 for c in claims if c["family"] == "social"),
        "platforms": sorted({str((c.get("value") or {}).get("platform") or "") for c in claims if c["family"] == "social"} - {""}),
        "jobs": sum(1 for c in claims if c["field"] == "job_posting" and (c["value"] or {}).get("status") != "closed"),
        "careers": any(c["field"] in ("careers_page", "recruitment_channel") for c in claims),
        "changes": len(env.get("changes") or []),
        "revenue": rev["value"]["amount"] if rev else None,
        "ry": str(rev["value"].get("year")) if rev else "",
        "rprev": prev["value"]["amount"] if prev else None,
        "result": res["value"]["amount"] if res else None,
        "emp": emp["value"] if emp and isinstance(emp.get("value"), (int, float)) else None,
        "lead": lead["value"].get("name") if lead else "",
        "places": sum(1 for c in claims if c["field"] == "registered_subunit"),
        "last": max(dated) if dated else "",
        "ribbon": [states.get(f, "not_available") for f in FAMILIES],
    }


def write_viewer(results: dict, orgs: list[str], report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "data" / "c").mkdir(parents=True, exist_ok=True)
    for name in WEB_FILES:
        shutil.copyfile(WEB / name, out / name)
    index = []
    for o in orgs:
        env = {k: v for k, v in results[o].items() if k != "discovery_trace"}
        index.append(_index_row(env))
        (out / "data" / "c" / f"{o}.js").write_text("KS.put(" + json.dumps(env, ensure_ascii=False, separators=(",", ":")) + ");\n",
                                                    encoding="utf-8")
    run = {k: report.get(k) for k in ("run_id", "agent", "started_at", "completed_at", "runtime_seconds", "companies", "claims",
                                      "evidence_records", "companies_with_claims_by_family", "field_states_by_family", "validation",
                                      "operations", "changes")}
    payload = {"families": list(FAMILIES.items()), "index": index, "run": run}
    (out / "data" / "index.js").write_text("window.KS=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                           encoding="utf-8")
