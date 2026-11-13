"""Write the static profile viewer for a run (opens from disk; no server, no network)."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .claims import FAMILIES

WEB = Path(__file__).parent / "web"
WEB_FILES = ("index.html", "app.js", "style.css")
ROUTINE_ACTIVITY = {"registry_update"}
HOSTED = "https://rohanglitched.github.io/kildespor/"
NEWS_FIELDS = {"company_news"}


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _headline(env: dict) -> str:
    s = env.get("summary") or {}
    if s.get("headline"):
        return _clip(s["headline"], 220)
    for x in s.get("sentences") or []:
        if x.get("topic") in ("profile", "what_it_does", "identity") and x.get("text"):
            return _clip(x["text"], 220)
    return ""


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
    news = sorted((c for c in claims if c["family"] == "activity" and c["field"] in NEWS_FIELDS and isinstance(c.get("value"), dict)),
                  key=lambda c: str(c.get("effective_date") or ""), reverse=True)
    jobs = [c for c in claims if c["field"] == "job_posting" and isinstance(c.get("value"), dict) and c["value"].get("status") != "closed"]
    addr = (get("identity", "registered_business_address") or {}).get("value") or ""
    if isinstance(addr, dict):
        addr = addr.get("address") or " ".join(str(v) for v in addr.values() if isinstance(v, str))
    row = {
        "org": env["organisation_number"],
        "name": env.get("legal_name") or env["organisation_number"],
        "status": env.get("status", "available"),
        "muni": str((get("identity", "municipality") or {}).get("value") or "").title(),
        "place": _clip(addr, 80) if isinstance(addr, str) else "",
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
        "jobs": len(jobs),
        "jt": _clip(jobs[0]["value"].get("title") or "", 90) if jobs else "",
        "careers": any(c["field"] in ("careers_page", "recruitment_channel") for c in claims),
        "news": len(news),
        "nd": str(news[0].get("effective_date") or "")[:10] if news else "",
        "nt": _clip(news[0]["value"].get("title") or "", 110) if news else "",
        "nu": str(news[0]["value"].get("url") or "") if news else "",
        "changes": len(env.get("changes") or []),
        "revenue": rev["value"]["amount"] if rev else None,
        "ry": str(rev["value"].get("year")) if rev else "",
        "rprev": prev["value"]["amount"] if prev else None,
        "result": res["value"]["amount"] if res else None,
        "emp": emp["value"] if emp and isinstance(emp.get("value"), (int, float)) else None,
        "lead": lead["value"].get("name") if lead else "",
        "places": sum(1 for c in claims if c["field"] == "registered_subunit"),
        "last": max(dated) if dated else "",
        "hl": _headline(env),
        "ribbon": [states.get(f, "not_available") for f in FAMILIES],
    }
    return row


def _noscript(index: list[dict], prefix: str) -> str:
    """A plain table for readers without JavaScript: every company, its website, revenue, hiring, news and headline."""
    def money(v):
        return "" if v is None else f"NOK {v:,.0f}".replace(",", " ")
    rows = []
    for x in index:
        site = f'<a href="https://{html.escape(x["domain"])}">{html.escape(x["domain"])}</a>' if x["domain"] else ""
        news = (f'<a href="{html.escape(x["nu"])}">{html.escape(x["nt"])}</a> ({x["nd"]})' if x.get("nu") else html.escape(x.get("nt") or "")) if x.get("news") else ""
        rows.append(f'<tr><td><a href="{prefix}data/c/{x["org"]}.js">{html.escape(x["name"])}</a><br><small>{x["org"]} · {html.escape(x["muni"])}'
                    f' · {html.escape(x["industry"])}</small></td><td>{site}</td><td>{money(x["revenue"])} {x["ry"]}</td>'
                    f'<td>{x["jobs"] or ""}</td><td>{news}</td><td>{html.escape(x["hl"])}</td></tr>')
    return ('<noscript><div class="page"><h1>Kildespor results</h1><p>This viewer needs JavaScript for search, compare and the evidence '
            'panels. Without it, here is every company in the run. Each name links to its full profile data (claims with source URL, '
            'retrieval time, SHA-256 and quoted span).</p><table class="nojs"><thead><tr><th>Company</th><th>Verified website</th>'
            '<th>Revenue</th><th>Open jobs</th><th>Latest news</th><th>Summary</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div></noscript>")


def _page(index: list[dict], prefix: str) -> str:
    src = (WEB / "index.html").read_text(encoding="utf-8")
    if prefix:
        src = (src.replace('href="style.css"', f'href="{prefix}style.css"')
                  .replace('src="data/index.js"', f'src="{prefix}data/index.js"')
                  .replace('src="app.js"', f'src="{prefix}app.js"')
                  .replace("<head>", f'<head>\n<script>window.KS_BASE="{prefix}"</script>', 1))
    return src.replace('<main class="main" id="main" tabindex="-1"></main>',
                       '<main class="main" id="main" tabindex="-1">' + _noscript(index, prefix) + "</main>", 1)


def entry_paths(viewer_dir: Path) -> dict:
    """Where the viewer and its root entry point live for a run whose viewer is <out>/viewer."""
    root = viewer_dir.parent if viewer_dir.name == "viewer" else None
    d = {"viewer": str(viewer_dir / "index.html"), "hosted_example": HOSTED}
    if root is not None:
        d["open"] = str(root / "index.html")
    return d


def write_viewer(results: dict, orgs: list[str], report: dict, out: Path) -> dict:
    """Write <out>/ (index.html, app.js, style.css, data/) and, when <out> is a run's viewer/ folder,
    an entry page <run>/index.html plus <run>/README.txt so the run folder opens with one double-click."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "data" / "c").mkdir(parents=True, exist_ok=True)
    for name in WEB_FILES[1:]:
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
    (out / "index.html").write_text(_page(index, ""), encoding="utf-8")
    paths = entry_paths(out)
    if "open" in paths:
        root = out.parent
        (root / "index.html").write_text(_page(index, out.name + "/"), encoding="utf-8")
        (root / "README.txt").write_text(
            "Kildespor run output\n"
            "====================\n\n"
            "OPEN index.html IN A BROWSER (double-click it). It is the results viewer: search and filter every company,\n"
            "compare two to four side by side, and open the source behind every fact (URL, retrieval time, SHA-256, quoted text).\n"
            "It works straight from disk: no server, no network, no install. Phones work too.\n\n"
            f"  index.html          the viewer ({len(orgs)} companies); same viewer also at viewer/index.html\n"
            "  envelopes.jsonl     one JSON envelope per input organisation number, in input order\n"
            "  run-report.json     counts, coverage by field family, validation checks, requests, runtime, cost\n"
            "  snapshots.zip       every fetched response behind a published fact, by SHA-256\n\n"
            "Check the evidence: python -m kildespor verify --envelopes envelopes.jsonl\n"
            f"Hosted example of the same viewer: {HOSTED}\n",
            encoding="utf-8")
    return paths
