"""Batch command: one terminal envelope for every organisation number in the input.

    python -m kildespor run --organisations batch.jsonl --output out/envelopes.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import json
import sys
import time
from pathlib import Path

from . import __version__
from .agent import Context, finish, research
from .claims import FAMILIES, Profile
from .discovery import Resolver
from .envelope import build
from .http import Client
from .refresh import diff, load_previous
from .sources import default_sources
from .util import utc_now


def read_orgnrs(path: str) -> list[str]:
    src = Path(path)
    opener = gzip.open if src.suffix == ".gz" else open
    with opener(src, "rt", encoding="utf-8") as fh:
        text = fh.read()
    values: list = []
    stripped = text.lstrip()
    if stripped.startswith("[") or (stripped.startswith("{") and src.suffix == ".json"):
        body = json.loads(text)
        values = body if isinstance(body, list) else body.get("organisation_numbers") or body.get("companies") or []
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("{"):
                values.append(json.loads(line))
            else:
                values.extend(x for x in line.replace(";", ",").split(",") if x.strip())
    out, seen = [], set()
    for v in values:
        raw = v.get("organisation_number") or v.get("orgnr") or v.get("organisasjonsnummer") if isinstance(v, dict) else v
        org = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if org.lower() in ("organisationnumber",) or not org:
            continue
        if len(org) != 9:
            raise SystemExit(f"Invalid organisation number in input: {v!r}")
        if org not in seen:
            seen.add(org)
            out.append(org)
    return out


def read_bulk(path: str | None, wanted: set[str]) -> dict[str, dict]:
    """Optional frozen registry snapshot (Brreg CSV or JSON). Used only when the live lookup fails."""
    if not path:
        return {}
    src = Path(path)
    opener = gzip.open if src.suffix == ".gz" else open
    found: dict[str, dict] = {}
    with opener(src, "rt", encoding="utf-8", newline="") as fh:
        head = fh.read(1)
        fh.seek(0)
        if head in "[{":
            data = json.load(fh) if head == "[" else [json.loads(x) for x in fh if x.strip()]
            for row in data:
                org = str(row.get("organisasjonsnummer") or row.get("organisation_number") or "")
                if org in wanted:
                    found[org] = _bulk_entity(row)
        else:
            for row in csv.DictReader(fh):
                org = row.get("organisasjonsnummer") or row.get("Organisasjonsnummer") or ""
                if org in wanted:
                    found[org] = _bulk_entity(row)
    return found


def _bulk_entity(row: dict) -> dict:
    if "navn" in row and isinstance(row.get("forretningsadresse"), dict):
        return row
    g = lambda *ks: next((row[k] for k in ks if row.get(k)), "")  # noqa: E731
    return {
        "organisasjonsnummer": g("organisasjonsnummer", "organisation_number"),
        "navn": g("navn", "name"),
        "organisasjonsform": {"kode": g("organisasjonsform.kode", "legal_form"), "beskrivelse": g("organisasjonsform.beskrivelse")},
        "hjemmeside": g("hjemmeside", "website"),
        "naeringskode1": {"kode": g("naeringskode1.kode", "industry_code"), "beskrivelse": g("naeringskode1.beskrivelse", "industry_label")},
        "forretningsadresse": {"adresse": [x for x in [g("forretningsadresse.adresse")] if x], "postnummer": g("forretningsadresse.postnummer"),
                               "poststed": g("forretningsadresse.poststed"), "kommune": g("forretningsadresse.kommune", "municipality")},
        "antallAnsatte": int(g("antallAnsatte", "employees") or 0) or None,
        "stiftelsesdato": g("stiftelsesdato"),
    }


def change_sentence(env: dict, ch: dict) -> dict:
    """What changed since the previous run, in one sourced sentence."""
    events = env["changes"]
    if not ch.get("previous_run_id"):
        return {"topic": "changes", "text": "First run for this company: there is no earlier profile to compare with.", "claim_keys": []}
    if not events:
        kept = f" {ch['carried_forward']} fact(s) were kept from the previous run." if ch.get("carried_forward") else ""
        return {"topic": "changes", "text": f"No changes since the previous run ({(ch.get('previous_completed_at') or '')[:10]}).{kept}",
                "claim_keys": []}
    order = {"high": 0, "medium": 1, "low": 2}
    top = sorted(events, key=lambda e: order.get(e["materiality"], 3))[:3]
    def word(e: dict) -> str:
        v = e.get("current") if e.get("current") is not None else e.get("previous")
        if isinstance(v, dict):
            v = v.get("title") or v.get("name") or v.get("url") or v.get("domain") or ""
        return f"{e['type'].replace('_', ' ')}" + (f" ({str(v)[:60]})" if v else "")
    more = f" and {len(events) - 3} more" if len(events) > 3 else ""
    return {"topic": "changes", "text": f"Since the previous run: {'; '.join(word(e) for e in top)}{more}.",
            "claim_keys": [e["key"] for e in top]}


def failed_profile(org: str, why: str) -> Profile:
    p = Profile(org)
    p.error("runner", why)
    for fam in FAMILIES:
        p.mark(fam, "failed", why)
    p.notes["entity_missing"] = True
    return p


async def run(args: argparse.Namespace) -> int:
    started = utc_now()
    t0 = time.monotonic()
    orgs = read_orgnrs(args.organisations)
    if args.expected_count is not None and len(orgs) != args.expected_count:
        print(f"warning: expected {args.expected_count} organisation numbers, received {len(orgs)}", file=sys.stderr)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    previous_path = args.previous or (str(out) if out.exists() and not args.no_refresh else None)
    previous = load_previous(previous_path) if previous_path and Path(previous_path).exists() else {}
    bulk = read_bulk(args.bulk, set(orgs))
    snapshots = Path(args.snapshots) if args.snapshots else out.parent / "snapshots"
    client = Client(concurrency=args.concurrency, snapshot_dir=None if args.no_snapshots else snapshots)
    resolver = Resolver()
    ctx = Context(client, resolver, default_sources(args), bulk)
    ctx.cache_dir = out.parent / ".kildespor-cache"  # declared external cache: NAV ad -> employer organisation number
    for src in ctx.sources:
        src.start(ctx, orgs)  # all run-wide downloads and indexes build in the background
    deadline = t0 + args.budget_minutes * 60 if args.budget_minutes else None
    sem = asyncio.Semaphore(args.companies_in_flight)
    results: dict[str, dict] = {}
    run_id = args.run_id or "kildespor-" + started.replace(":", "").replace("-", "")
    done = 0

    async def one(org: str) -> None:
        nonlocal done
        async with sem:
            req0 = client.stats.requests
            c0 = time.monotonic()
            p = Profile(org)
            trace: dict = {}
            budget = args.per_company_seconds
            if deadline:
                budget = max(10.0, min(budget, deadline - time.monotonic() - 30))
            try:
                await asyncio.wait_for(research(ctx, org, p, trace), timeout=budget)
            except asyncio.TimeoutError:
                p.error("runner", f"research stopped at the {budget:.0f}s per-company budget; partial results kept")
                for fam in FAMILIES:
                    if not p.family_claims(fam) and fam not in p.states:
                        p.mark(fam, "failed", "time budget reached before this source finished")
            except Exception as exc:  # never drop a company
                p.error("runner", repr(exc))
                for fam in FAMILIES:
                    if not p.family_claims(fam):
                        p.mark(fam, "failed", f"unexpected error: {type(exc).__name__}")
            research_ms = int((time.monotonic() - c0) * 1000)
        # late sources (the NAV job index) run after the research slot is released
        if "late_args" in p.notes:
            try:
                await asyncio.wait_for(finish(ctx, p, trace), timeout=max(60.0, (deadline - time.monotonic() - 20) if deadline else 900))
            except asyncio.TimeoutError:
                p.error("runner", "late sources did not finish within the budget")
                if not p.family_claims("jobs"):
                    p.mark("jobs", "failed", "the job index was not ready within the time budget")
            except Exception as exc:
                p.error("runner", repr(exc))
        ops = {"requests": client.stats.requests - req0, "runtime_ms": research_ms,
               "third_party_cost_usd": 0.0}
        env = build(p, run_id=run_id, started_at=started, completed_at=utc_now(), operations=ops, changes=None,
                    trace=trace if args.trace else None)
        ch = diff(env, previous.get(org))
        env["changes"] = ch.pop("events")
        env["refresh"] = ch
        env["sections"]["refresh"].update({"previous_run_id": ch.get("previous_run_id"), "changes": len(env["changes"])})
        env["summary"]["sentences"].append(change_sentence(env, ch))
        results[org] = env
        done += 1
        if done % 25 == 0 or done == len(orgs):
            print(f"{done}/{len(orgs)} companies · {client.stats.requests} requests · {time.monotonic() - t0:.0f}s", file=sys.stderr)

    await asyncio.gather(*(one(o) for o in orgs))
    await client.close()
    for o in orgs:  # belt and braces: exactly one envelope per input
        if o not in results:
            results[o] = build(failed_profile(o, "no result produced"), run_id=run_id, started_at=started,
                               completed_at=utc_now(), operations={"requests": 0, "runtime_ms": 0, "third_party_cost_usd": 0.0},
                               changes=None)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for o in orgs:
            fh.write(json.dumps(results[o], ensure_ascii=False, separators=(",", ":")) + "\n")
    if previous_path and Path(previous_path).exists() and Path(previous_path).resolve() == out.resolve():
        hist = out.parent / "history"
        hist.mkdir(exist_ok=True)
        Path(previous_path).replace(hist / f"envelopes-{next(iter(previous.values()))['run']['run_id'] if previous else 'previous'}.jsonl")
    tmp.replace(out)
    report = make_report(results, orgs, run_id, started, t0, client, ctx)
    Path(args.report or out.parent / "run-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.html:
        from .viewer import write_viewer
        write_viewer(results, orgs, report, Path(args.html))
    print(json.dumps({k: report[k] for k in ("run_id", "companies", "envelopes", "validation", "runtime_seconds")}, indent=2))
    return 0 if report["validation"]["passed"] else 1


def make_report(results: dict, orgs: list[str], run_id: str, started: str, t0: float, client: Client, ctx: Context) -> dict:
    envs = [results[o] for o in orgs]
    fam_cov = {f: sum(1 for e in envs if any(c["family"] == f for c in e["claims"])) for f in FAMILIES}
    states = {}
    for e in envs:
        for s in e["field_states"]:
            states.setdefault(s["family"], {}).setdefault(s["state"], 0)
            states[s["family"]][s["state"]] += 1
    lat = sorted(e["operations"]["runtime_ms"] for e in envs)
    checks = {
        "exact_expected_count": len(envs) == len(orgs),
        "unique_organisation_numbers": len({e["organisation_number"] for e in envs}) == len(envs),
        "every_envelope_terminal": all(e["run"]["terminal_status"] in ("completed", "failed") for e in envs),
        "every_claim_has_evidence": all(c["evidence_ids"] for e in envs for c in e["claims"]),
        "every_evidence_has_source_time_hash": all(ev["source_url"] and ev["retrieved_at"] and ev["content_sha256"]
                                                  for e in envs for ev in e["evidence"]),
    }
    return {
        "run_id": run_id,
        "agent": f"kildespor {__version__}",
        "started_at": started,
        "completed_at": utc_now(),
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "companies": len(orgs),
        "envelopes": len(envs),
        "validation": {"passed": all(checks.values()), "checks": checks},
        "claims": sum(len(e["claims"]) for e in envs),
        "evidence_records": sum(len(e["evidence"]) for e in envs),
        "companies_with_claims_by_family": fam_cov,
        "field_states_by_family": states,
        "changes": sum(len(e["changes"]) for e in envs),
        "operations": {"requests": client.stats.requests, "bytes": client.stats.bytes, "by_source": client.stats.by_source,
                       "p50_company_ms": lat[len(lat) // 2] if lat else None,
                       "p95_company_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
                       "third_party_cost_usd": 0.0, "dns_timeouts": getattr(ctx.resolver, "timeouts", 0)},
        "sources": [{"name": s.name, "prepared": not getattr(s, "prepare_error", None), "error": getattr(s, "prepare_error", None),
                     "prepare_seconds": getattr(s, "prepare_seconds", None),
                     **getattr(s, "report", lambda: {})()} for s in ctx.sources],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kildespor", description="Research Norwegian companies from their organisation numbers.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="research a batch and write one terminal envelope per company")
    r.add_argument("--organisations", "--input", required=True, help="JSON, JSONL, CSV or text list of organisation numbers")
    r.add_argument("--output", default="out/envelopes.jsonl")
    r.add_argument("--report")
    r.add_argument("--run-id")
    r.add_argument("--previous", help="previous envelopes.jsonl for refresh diffs (default: the existing --output file)")
    r.add_argument("--no-refresh", action="store_true", help="do not diff against an existing output file")
    r.add_argument("--bulk", help="optional frozen Brreg snapshot (CSV/JSON) used if the live register lookup fails")
    r.add_argument("--expected-count", type=int)
    r.add_argument("--concurrency", type=int, default=96, help="HTTP requests in flight")
    r.add_argument("--companies-in-flight", type=int, default=96)
    r.add_argument("--per-company-seconds", type=float, default=240)
    r.add_argument("--budget-minutes", type=float, default=0, help="global time budget; 0 = none")
    r.add_argument("--snapshots", help="directory for raw response snapshots (default: next to --output)")
    r.add_argument("--no-snapshots", action="store_true")
    r.add_argument("--html", help="write the static profile viewer to this directory")
    r.add_argument("--trace", action="store_true", help="include the discovery trace in each envelope")
    r.add_argument("--no-jobs", action="store_true")
    r.add_argument("--no-wikidata", action="store_true")
    r.add_argument("--no-announcements", action="store_true")
    v = sub.add_parser("view", help="build the static viewer from an envelopes file")
    v.add_argument("--envelopes", required=True)
    v.add_argument("--report")
    v.add_argument("--out", required=True)
    vf = sub.add_parser("verify", help="check every evidence hash and quoted span against the archived raw responses")
    vf.add_argument("--envelopes", required=True)
    vf.add_argument("--archive")
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        from .verify import verify_run
        rep = verify_run(Path(args.envelopes), Path(args.archive) if args.archive else None)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["hash_in_archive"] == rep["evidence_records"] else 1
    if args.cmd == "view":
        from .viewer import write_viewer
        envs = [json.loads(x) for x in Path(args.envelopes).read_text(encoding="utf-8").splitlines() if x.strip()]
        rep_path = Path(args.report) if args.report else Path(args.envelopes).parent / "run-report.json"
        report = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
        orgs = [e["organisation_number"] for e in envs]
        write_viewer({e["organisation_number"]: e for e in envs}, orgs, report, Path(args.out))
        print(f"viewer written to {args.out} ({len(orgs)} companies)")
        return 0
    if args.cmd == "run":
        from .netfix import install
        install()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        return asyncio.run(run(args))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
