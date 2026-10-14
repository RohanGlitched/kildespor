"""Official Norwegian records from Brønnøysundregistrene (NLOD 2.0).

Identity, contact fields, roles, registered subunits and filed annual accounts. These are the
identity anchor for everything else: every external fact must tie back to this entity.
"""
from __future__ import annotations

import json
from typing import Any

from .claims import Claim, Evidence, Profile
from .http import Client, Fetched

ENHET = "https://data.brreg.no/enhetsregisteret/api/enheter/{}"
ROLLER = "https://data.brreg.no/enhetsregisteret/api/enheter/{}/roller"
UNDER = "https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={}&size=200"
REGNSKAP = "https://data.brreg.no/regnskapsregisteret/regnskap/{}"
PUBLIC_ENHET = "https://virksomhet.brreg.no/nb/oppslag/enheter/{}"

SRC = "Brønnøysundregistrene"


def _json(f: Fetched) -> Any:
    try:
        return json.loads(f.body)
    except (ValueError, TypeError):
        return None


def _ev(f: Fetched, span: str, method: str, url: str | None = None) -> Evidence:
    return Evidence(url or f.url, "official_registry", f.retrieved_at, f.sha256, span, method,
                    final_url=f.final_url, http_status=f.status, source_name=SRC)


def _addr(a: dict | None) -> str:
    if not a:
        return ""
    lines = [x for x in a.get("adresse") or [] if x]
    tail = " ".join(x for x in (a.get("postnummer"), a.get("poststed")) if x)
    if a.get("landkode") and a.get("landkode") != "NO":
        tail = (tail + ", " + (a.get("land") or "")).strip(", ")
    return ", ".join(lines + ([tail] if tail else []))


async def fetch_entity(client: Client, orgnr: str) -> tuple[dict | None, Fetched]:
    f = await client.get("brreg", ENHET.format(orgnr), headers={"Accept": "application/json"}, check_robots=False, retries=2)
    return (_json(f) if f.ok else None), f


async def add_registry(client: Client, p: Profile, ent: dict, f: Fetched) -> None:
    """Identity claims from the entity record."""
    def c(field: str, value: Any, path: str, label: str, effective: str | None = None) -> None:
        if value in (None, "", []):
            return
        span = f"{path}: {value if not isinstance(value, (dict, list)) else json.dumps(value, ensure_ascii=False)}"
        p.add(Claim("identity", field, value, [_ev(f, span, "registry_field")], label=label, effective_date=effective))

    c("legal_name", ent.get("navn"), "navn", "Legal name")
    c("organisation_number", ent.get("organisasjonsnummer"), "organisasjonsnummer", "Organisation number")
    form = ent.get("organisasjonsform") or {}
    c("legal_form", f"{form.get('kode')} ({form.get('beskrivelse')})" if form.get("kode") else None,
      "organisasjonsform", "Legal form")
    for i, key in enumerate(("naeringskode1", "naeringskode2", "naeringskode3"), 1):
        n = ent.get(key)
        if n:
            c("industry" if i == 1 else f"industry_{i}", f"{n.get('kode')} {n.get('beskrivelse')}", key,
              "Industry (NACE)" if i == 1 else f"Secondary industry {i - 1}")
    c("registered_business_address", _addr(ent.get("forretningsadresse")), "forretningsadresse", "Business address")
    c("postal_address", _addr(ent.get("postadresse")), "postadresse", "Postal address")
    c("municipality", (ent.get("forretningsadresse") or {}).get("kommune"), "forretningsadresse.kommune", "Municipality")
    c("founded", ent.get("stiftelsesdato"), "stiftelsesdato", "Founded", ent.get("stiftelsesdato"))
    c("registered", ent.get("registreringsdatoEnhetsregisteret"), "registreringsdatoEnhetsregisteret",
      "Registered in the Central Coordinating Register", ent.get("registreringsdatoEnhetsregisteret"))
    if ent.get("harRegistrertAntallAnsatte") and ent.get("antallAnsatte") is not None:
        c("registered_employees", ent.get("antallAnsatte"), "antallAnsatte", "Registered employees",
          ent.get("registreringsdatoAntallAnsatteEnhetsregisteret"))
    kap = ent.get("kapital") or {}
    if kap.get("belop") is not None:
        c("share_capital", {"amount": kap.get("belop"), "currency": kap.get("valuta"), "shares": kap.get("antallAksjer")},
          "kapital", "Share capital", kap.get("innfortDato"))
    purpose = " ".join(ent.get("vedtektsfestetFormaal") or []) or " ".join(ent.get("aktivitet") or [])
    if purpose:
        p.add(Claim("description", "registered_purpose", purpose,
                    [_ev(f, "vedtektsfestetFormaal: " + purpose, "registry_field")], label="Registered purpose"))
    flags = []
    for key, label in (("registrertIMvaregisteret", "VAT registered"), ("registrertIForetaksregisteret", "In the Register of Business Enterprises"),
                       ("erIKonsern", "Part of a group"), ("konkurs", "Bankrupt"), ("underAvvikling", "Being wound up")):
        if ent.get(key):
            flags.append(label)
    if flags:
        c("registry_flags", flags, "flags", "Registry status")
    if ent.get("hjemmeside"):
        c("registered_website", ent["hjemmeside"], "hjemmeside", "Website stated in the register")
    for key, label in (("telefon", "Registered phone"), ("mobil", "Registered mobile"), ("epostadresse", "Registered e-mail")):
        if ent.get(key):
            p.add(Claim("contact", "registered_" + {"telefon": "phone", "mobil": "mobile", "epostadresse": "email"}[key],
                        ent[key], [_ev(f, f"{key}: {ent[key]}", "registry_field")], label=label))
    for h in ent.get("historiskeNavn") or []:
        if isinstance(h, dict) and h.get("navn"):
            c("former_name", h["navn"], "historiskeNavn", "Former name", h.get("tilDato"))
    p.notes["entity_retrieved_at"] = f.retrieved_at
    p.notes["entity_sha"] = f.sha256
    p.checked_source("identity", SRC)
    p.checked_source("contact", SRC)


async def add_roles(client: Client, p: Profile, orgnr: str) -> list[dict]:
    f = await client.get("brreg", ROLLER.format(orgnr), headers={"Accept": "application/json"}, check_robots=False, retries=2)
    p.checked_source("people", SRC + " roles")
    if not f.ok:
        p.mark("people", "failed", f"Role register request failed ({f.status or f.error})")
        return []
    data = _json(f) or {}
    people = []
    for group in data.get("rollegrupper") or []:
        changed = group.get("sistEndret")
        p.notes.setdefault("role_groups", []).append({"group": (group.get("type") or {}).get("beskrivelse") or "Roles",
                                                      "changed": changed, "retrieved_at": f.retrieved_at, "sha": f.sha256})
        for r in group.get("roller") or []:
            if r.get("avregistrert") or r.get("fratraadt"):
                continue
            role = (r.get("type") or {}).get("beskrivelse") or (r.get("type") or {}).get("kode")
            code = (r.get("type") or {}).get("kode")
            if r.get("person"):
                n = r["person"].get("navn") or {}
                if r["person"].get("erDoed"):
                    continue
                name = " ".join(x for x in (n.get("fornavn"), n.get("mellomnavn"), n.get("etternavn")) if x)
                kind = "person"
            elif r.get("enhet"):
                e = r["enhet"]
                name = " ".join(e.get("navn") or []) if isinstance(e.get("navn"), list) else (e.get("navn") or "")
                kind = "organisation"
            else:
                continue
            if not name:
                continue
            value = {"name": name, "role": role, "role_code": code, "kind": kind}
            if kind == "organisation" and r["enhet"].get("organisasjonsnummer"):
                value["organisation_number"] = r["enhet"]["organisasjonsnummer"]
            people.append(value)
            p.add(Claim("people", "registered_role", value,
                        [_ev(f, f"{role}: {name}", "registry_roles")], label=role or "Role",
                        effective_date=changed, key=f"people:registered_role:{code}:{name.lower()}"))
    if not people:
        p.mark("people", "not_available", "No active roles in the role register")
    return people


async def add_subunits(client: Client, p: Profile, orgnr: str) -> list[dict]:
    f = await client.get("brreg", UNDER.format(orgnr), headers={"Accept": "application/json"}, check_robots=False, retries=2)
    p.checked_source("locations", SRC + " subunits")
    units = []
    if not f.ok:
        p.mark("locations", "failed", f"Subunit register request failed ({f.status or f.error})")
        return units
    data = _json(f) or {}
    for u in (data.get("_embedded") or {}).get("underenheter") or []:
        if u.get("nedleggelsesdato"):
            continue
        addr = _addr(u.get("beliggenhetsadresse"))
        value = {"organisation_number": u.get("organisasjonsnummer"), "name": u.get("navn"), "address": addr,
                 "municipality": (u.get("beliggenhetsadresse") or {}).get("kommune"),
                 "industry": (u.get("naeringskode1") or {}).get("beskrivelse")}
        if u.get("harRegistrertAntallAnsatte") and u.get("antallAnsatte") is not None:
            value["registered_employees"] = u["antallAnsatte"]
        units.append({**value, "telefon": u.get("telefon"), "mobil": u.get("mobil"), "epost": u.get("epostadresse"),
                      "hjemmeside": u.get("hjemmeside")})
        p.add(Claim("locations", "registered_subunit", value,
                    [_ev(f, f"Underenhet {u.get('organisasjonsnummer')} {u.get('navn')}: {addr}", "registry_subunits",
                         url=f"https://data.brreg.no/enhetsregisteret/api/underenheter/{u.get('organisasjonsnummer')}")],
                    label="Registered workplace", effective_date=u.get("oppstartsdato"),
                    relationship="registered_subunit", key=f"locations:registered_subunit:{u.get('organisasjonsnummer')}"))
    return units


FIN_FIELDS = [
    ("revenue", "Operating revenue", ("resultatregnskapResultat", "driftsresultat", "driftsinntekter", "sumDriftsinntekter")),
    ("operating_result", "Operating result", ("resultatregnskapResultat", "driftsresultat", "driftsresultat")),
    ("profit_before_tax", "Result before tax", ("resultatregnskapResultat", "ordinaertResultatFoerSkattekostnad")),
    ("annual_result", "Annual result", ("resultatregnskapResultat", "aarsresultat")),
    ("payroll_cost", "Payroll costs", ("resultatregnskapResultat", "driftsresultat", "driftskostnad", "loennskostnad")),
    ("total_assets", "Total assets", ("eiendeler", "sumEiendeler")),
    ("equity", "Equity", ("egenkapitalGjeld", "egenkapital", "sumEgenkapital")),
    ("total_debt", "Total debt", ("egenkapitalGjeld", "gjeldOversikt", "sumGjeld")),
    ("cash", "Bank deposits and cash", ("eiendeler", "sumBankinnskuddOgKontanter")),
]


def _dig(d: dict, path: tuple[str, ...]) -> Any:
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


async def add_financials(client: Client, p: Profile, orgnr: str) -> list[dict]:
    f = await client.get("regnskap", REGNSKAP.format(orgnr), headers={"Accept": "application/json"}, check_robots=False, retries=2)
    p.checked_source("financials", SRC + " annual accounts")
    if f.status == 404:
        p.mark("financials", "not_available", "No filed annual accounts in the Register of Company Accounts")
        return []
    if not f.ok:
        p.mark("financials", "failed", f"Accounts request failed ({f.status or f.error})")
        return []
    rows = _json(f) or []
    if isinstance(rows, dict):
        rows = [rows]
    years = []
    for r in rows:
        period = (r.get("regnskapsperiode") or {})
        year = (period.get("tilDato") or "")[:4]
        if not year:
            continue
        rec = {"year": year, "period": f"{period.get('fraDato')}..{period.get('tilDato')}", "currency": r.get("valuta"),
               "type": r.get("regnskapstype"), "small_company_rules": (r.get("regnkapsprinsipper") or {}).get("smaaForetak"),
               "audited": not (r.get("revisjon") or {}).get("ikkeRevidertAarsregnskap", False),
               "audit_opt_out": (r.get("revisjon") or {}).get("fravalgRevisjon")}
        for field, label, path in FIN_FIELDS:
            v = _dig(r, path)
            if v is None:
                continue  # never turn a missing figure into zero
            rec[field] = v
            p.add(Claim("financials", field, {"year": year, "amount": v, "currency": r.get("valuta")},
                        [_ev(f, f"{year} {'.'.join(path)}: {v}", "registry_accounts")], label=label,
                        reporting_period=rec["period"], key=f"financials:{field}:{year}:{r.get('regnskapstype')}"))
        years.append(rec)
    years.sort(key=lambda x: x["year"])
    if not years:
        p.mark("financials", "not_available", "The accounts register returned no periods")
    return years


def public_page(orgnr: str) -> str:
    return PUBLIC_ENHET.format(orgnr)
