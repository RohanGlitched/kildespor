"""Terminal envelope per organisation number, plus an evidence-bounded summary."""
from __future__ import annotations

from typing import Any

from .claims import FAMILIES, Claim, Profile

SECTIONS = [
    ("legal_identity_and_brand", "Legal identity and public brand", ["identity", "description"]),
    ("annual_accounts", "Latest annual accounts and available history", ["financials"]),
    ("leadership_and_workplaces", "Leadership and registered workplaces", ["people", "locations"]),
    ("website_and_profiles", "Verified official website and company-owned profiles", ["website", "social", "contact"]),
    ("hiring_and_activity", "Hiring and dated public activity", ["jobs", "activity"]),
]

ROLE_ORDER = ["DAGL", "LEDE", "NEST", "MEDL", "VARA", "KONT", "REVI", "REGN", "INNH", "DTPR", "DTSO", "KOMP", "BEST", "SAM"]


def _fmt_nok(v: float | int | None) -> str:
    if v is None:
        return "—"
    v = float(v)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e9:
        return f"{sign}NOK {v / 1e9:.1f} bn"
    if v >= 1e6:
        return f"{sign}NOK {v / 1e6:.1f} m"
    if v >= 1e3:
        return f"{sign}NOK {v / 1e3:.0f} k"
    return f"{sign}NOK {v:.0f}"


def _clip_words(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-–")
    return cut + "…"


def _first(claims: list[Claim], field: str) -> Claim | None:
    return next((c for c in claims if c.field == field), None)


def summarise(p: Profile) -> dict[str, Any]:
    """Short, sourced sentences. Each sentence lists the claim keys it rests on; nothing else is said."""
    if p.notes.get("entity_missing"):
        return {"headline": "Not found in the official register", "sentences": [], "unknowns": list(FAMILIES)}
    by = {f: p.family_claims(f) for f in FAMILIES}
    s: list[dict[str, Any]] = []
    ident = by["identity"]
    name = _first(ident, "legal_name")
    ind = _first(ident, "industry")
    muni = _first(ident, "municipality")
    founded = _first(ident, "founded")
    brand = _first(ident, "public_brand")
    keys = [c.key for c in (name, ind, muni, founded) if c]
    parts = [name.value if name else p.orgnr]
    if ind:
        parts.append(f"is registered in {ind.value.split(' ', 1)[-1].lower()}")
    if muni:
        parts.append(f"in {str(muni.value).title()}")
    if founded:
        parts.append(f"(founded {str(founded.value)[:4]})")
    s.append({"topic": "identity", "text": " ".join(parts) + ".", "claim_keys": keys})
    if brand and name and brand.value.lower() not in name.value.lower():
        s.append({"topic": "identity", "text": f"It presents itself online as {brand.value}.", "claim_keys": [brand.key]})
    desc = _first(by["description"], "site_description") or _first(by["description"], "about_page")
    purpose = _first(by["description"], "registered_purpose")
    if desc:
        s.append({"topic": "what_it_does", "text": f"Its website says: “{_clip_words(desc.value, 220)}”", "claim_keys": [desc.key]})
    elif purpose:
        s.append({"topic": "what_it_does", "text": f"Registered purpose: {_clip_words(purpose.value, 220)}", "claim_keys": [purpose.key]})
    fin = [c for c in by["financials"] if isinstance(c.value, dict) and "amount" in c.value]
    years = sorted({c.value["year"] for c in fin})
    if years:
        y = years[-1]
        rev = next((c for c in fin if c.field == "revenue" and c.value["year"] == y), None)
        res = next((c for c in fin if c.field == "annual_result" and c.value["year"] == y), None)
        eq = next((c for c in fin if c.field == "equity" and c.value["year"] == y), None)
        bits, ks = [], []
        if rev:
            bits.append(f"revenue {_fmt_nok(rev.value['amount'])}")
            ks.append(rev.key)
            prev = next((c for c in fin if c.field == "revenue" and c.value["year"] == str(int(y) - 1)), None)
            if prev and prev.value["amount"]:
                ch = (rev.value["amount"] - prev.value["amount"]) / abs(prev.value["amount"]) * 100
                bits[-1] += f" ({ch:+.0f}% on {int(y) - 1})"
                ks.append(prev.key)
        if res:
            bits.append(f"annual result {_fmt_nok(res.value['amount'])}")
            ks.append(res.key)
        if eq:
            bits.append(f"equity {_fmt_nok(eq.value['amount'])}")
            ks.append(eq.key)
        if bits:
            s.append({"topic": "financials", "text": f"Latest filed accounts ({y}): " + ", ".join(bits) + ".", "claim_keys": ks})
        if eq and eq.value["amount"] is not None and eq.value["amount"] < 0:
            s.append({"topic": "financials", "text": f"Equity was negative at the end of {y}.", "claim_keys": [eq.key]})
    roles = sorted([c for c in by["people"] if c.field == "registered_role"],
                   key=lambda c: ROLE_ORDER.index(c.value.get("role_code")) if c.value.get("role_code") in ROLE_ORDER else 99)
    lead = [c for c in roles if c.value.get("role_code") in ("DAGL", "LEDE", "INNH")][:2]
    if lead:
        s.append({"topic": "people", "text": "; ".join(f"{c.value['role']}: {c.value['name']}" for c in lead) + ".",
                  "claim_keys": [c.key for c in lead]})
    subs = [c for c in by["locations"] if c.field == "registered_subunit"]
    if len(subs) > 1:
        munis = sorted({(c.value.get("municipality") or "").title() for c in subs if c.value.get("municipality")})
        s.append({"topic": "locations", "text": f"{len(subs)} registered workplaces" + (f" in {', '.join(munis[:5])}" if munis else "") + ".",
                  "claim_keys": [c.key for c in subs[:8]]})
    site = _first(by["website"], "official_website")
    socials = [c for c in by["social"]]
    if site:
        txt = f"Verified website: {site.value['domain']} (proof: {', '.join(site.value['identity_proof'])})"
        if socials:
            txt += "; company-linked profiles on " + ", ".join(sorted({c.value["platform"] for c in socials}))
        s.append({"topic": "online", "text": txt + ".", "claim_keys": [site.key] + [c.key for c in socials[:6]]})
    jobs = [c for c in by["jobs"] if c.field == "job_posting"]
    if jobs:
        latest = max((c.effective_date or "" for c in jobs), default="")
        s.append({"topic": "hiring", "text": f"{len(jobs)} job posting(s) found" + (f", latest {latest}" if latest else "") + ".",
                  "claim_keys": [c.key for c in jobs[:8]]})
    elif any(c.field in ("careers_page", "recruitment_channel") for c in by["jobs"]):
        c = next(c for c in by["jobs"] if c.field in ("careers_page", "recruitment_channel"))
        s.append({"topic": "hiring", "text": "It publishes a careers page, but no individual open postings were found.", "claim_keys": [c.key]})
    acts = sorted([c for c in by["activity"] if c.effective_date], key=lambda c: c.effective_date, reverse=True)
    if acts:
        top = acts[0]
        title = top.value.get("title") or top.label if isinstance(top.value, dict) else top.label
        s.append({"topic": "activity", "text": f"Most recent dated activity ({top.effective_date}): {title}.", "claim_keys": [top.key]})
    unknown = [f for f in FAMILIES if not by[f]]
    headline = (name.value if name else p.orgnr)
    if ind:
        headline += f" · {ind.value.split(' ', 1)[-1]}"
    return {"headline": headline, "sentences": s, "unknowns": unknown}


def family_states(p: Profile) -> list[dict[str, Any]]:
    out = []
    for fam, label in FAMILIES.items():
        n = len(p.family_claims(fam))
        if n:
            out.append({"family": fam, "label": label, "state": "available", "claims": n, "checked_sources": p.checked[fam]})
            continue
        st = p.states.get(fam)
        if st:
            d = st.as_dict()
            d["checked_sources"] = p.checked[fam] or d["checked_sources"]
            out.append(d | {"claims": 0})
        else:
            out.append({"family": fam, "label": label, "state": "not_available", "claims": 0,
                        "note": "Checked; nothing found for this entity", "checked_sources": p.checked[fam]})
    return out


def build(p: Profile, *, run_id: str, started_at: str, completed_at: str, operations: dict, changes: dict | None,
          trace: dict | None = None) -> dict[str, Any]:
    states = family_states(p)
    claims = [c.as_dict() for c in p.claims]
    evidence: dict[str, dict] = {}
    for c in p.claims:
        for e in c.evidence:
            evidence.setdefault(e.id, e.as_dict())
    by_fam = {s["family"]: s for s in states}
    sections = {}
    for key, label, fams in SECTIONS:
        avail = [f for f in fams if by_fam[f]["state"] == "available"]
        if avail:
            state = "available"
        else:
            st = [by_fam[f]["state"] for f in fams]
            state = next((x for x in ("blocked", "ambiguous", "failed", "not_applicable") if x in st), "not_available")
        sections[key] = {"label": label, "state": state, "families": fams,
                         "claim_keys": [c["key"] for c in claims if c["family"] in fams]}
    sections["evidence_and_availability"] = {"label": "Claim-level evidence and availability state", "state": "available",
                                              "claims": len(claims), "evidence_records": len(evidence)}
    sections["refresh"] = {"label": "Refresh metadata and material changes since the previous run", "state": "available",
                           "previous_run_id": (changes or {}).get("previous_run_id"),
                           "changes": len((changes or {}).get("events", []))}
    ent = p.notes.get("entity") or {}
    terminal = "failed" if p.notes.get("entity_missing") else "completed"
    status = "failed" if terminal == "failed" else "available"
    env = {
        "organisation_number": p.orgnr,
        "status": status,
        "legal_name": ent.get("navn"),
        "run": {"run_id": run_id, "started_at": started_at, "completed_at": completed_at, "terminal_status": terminal},
        "summary": summarise(p),
        "sections": sections,
        "field_states": states,
        "claims": claims,
        "evidence": list(evidence.values()),
        "changes": (changes or {}).get("events", []),
        "refresh": {k: v for k, v in (changes or {}).items() if k != "events"},
        "errors": p.errors,
        "operations": operations,
    }
    if trace is not None:
        env["discovery_trace"] = trace
    return env
