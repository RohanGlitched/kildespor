"""More official, organisation-number-keyed records from Brønnøysundregistrene (NLOD 2.0).

- Regnskapsregisteret: the list of filed annual-account copies (PDF) by year
- Enhetsregisteret: the dated update log for the entity
- Støtteregisteret: state-aid awards received by the entity
- dated events the entity record already carries (capital change, articles, board change, renames)
"""
from __future__ import annotations

import json
import time

from ..claims import Claim, Evidence
from ..util import clip
from . import Source

PDF_YEARS = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{}/aar"
PDF = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{}/{}"
UPDATES = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter?organisasjonsnummer={}&dato=2015-01-01T00:00:00.000Z&size=200"
AID = "https://stottetiltak-registerinfo-api.app.brreg.no/api/v1/soek/stoettetildeling?pageSize=50&page=1&language=NOB"
AID_PUBLIC = "https://data.brreg.no/stotteregisteret/"
SRC = "Brønnøysundregistrene"

INSTRUMENT = {
    "skatteEllerAvgiftsFritak": "tax or duty exemption", "tilskudd": "grant", "laan": "loan", "garanti": "guarantee",
    "rentesubsidier": "interest subsidy", "egenkapital": "equity", "skattefradrag": "tax deduction",
    "redusertSkatt": "reduced tax", "annet": "other aid",
}


def _ev(f, span: str, method: str, url: str | None = None) -> list[Evidence]:
    return [Evidence(url or f.url, "official_registry", f.retrieved_at, f.sha256, span, method, final_url=f.final_url,
                     http_status=f.status, source_name=SRC)]


class BrregExtra(Source):
    late = True  # does not feed website discovery: runs after the research slot
    name = "brreg_extra"
    families = ["financials", "activity"]

    def __init__(self) -> None:
        self.aid_companies = 0
        self.pdf_companies = 0
        self.copies_paused_until = 0.0
        self.copies_rate_limited = 0

    async def enrich(self, ctx, p, ent, subunits, sites) -> None:
        org = p.orgnr
        c = ctx.client
        p.checked_source("activity", "Brreg update log, state-aid register, registry dates")
        pdf_f = None
        if time.monotonic() >= self.copies_paused_until:
            pdf_f = await c.get("regnskap", PDF_YEARS.format(org), headers={"Accept": "application/json"}, check_robots=False)
            if pdf_f.status == 429:
                # the copies endpoint allows ~30 calls per few minutes; pause it instead of hammering
                self.copies_paused_until = time.monotonic() + 180
                self.copies_rate_limited += 1
        if pdf_f is not None and not pdf_f.ok and pdf_f.status not in (404, 429):
            p.error("regnskap_copies", f"account-copy list failed ({pdf_f.status or pdf_f.error})")
        if pdf_f is not None and pdf_f.ok:
            try:
                years = sorted(json.loads(pdf_f.body))
            except ValueError:
                years = []
            if years:
                self.pdf_companies += 1
            for y in years:
                p.add(Claim("financials", "annual_report_copy", {"year": str(y), "url": PDF.format(org, y), "format": "pdf"},
                            _ev(pdf_f, f"annual-account copy available for {y}", "registry_accounts_copies", url=PDF_YEARS.format(org)),
                            label="Filed annual accounts (PDF copy)", reporting_period=str(y),
                            key=f"financials:annual_report_copy:{y}"))
        # dated update log
        up = await c.get("brreg", UPDATES.format(org), headers={"Accept": "application/json"}, check_robots=False, retries=1)
        if not up.ok:
            p.error("brreg_updates", f"update log failed ({up.status or up.error})")
        if up.ok:
            items = (json.loads(up.body).get("_embedded") or {}).get("oppdaterteEnheter") or []
            by_day: dict[str, list[str]] = {}
            for it in items:
                day = (it.get("dato") or "")[:10]
                if day:
                    by_day.setdefault(day, []).append(it.get("endringstype") or "Endring")
            for day in sorted(by_day, reverse=True)[:15]:
                kinds = sorted(set(by_day[day]))
                p.add(Claim("activity", "registry_update", {"title": f"Register entry updated ({', '.join(kinds)})", "count": len(by_day[day]),
                                                             "url": f"https://virksomhet.brreg.no/nb/oppslag/enheter/{org}", "source": SRC},
                            _ev(up, f"oppdatering {day}: {', '.join(kinds)} ×{len(by_day[day])}", "registry_update_log"),
                            label="Register entry updated", effective_date=day, key=f"activity:registry_update:{day}"))
        # events the entity record carries
        kap = ent.get("kapital") or {}
        for field, date, title in (
            ("share_capital_changed", kap.get("innfortDato"), f"Share capital registered: {kap.get('belop')} {kap.get('valuta') or ''}".strip()),
            ("articles_changed", ent.get("vedtektsdato"), "Articles of association dated"),
            ("founded", ent.get("stiftelsesdato"), "Company founded"),
        ):
            if not date or (field == "share_capital_changed" and kap.get("belop") is None):
                continue
            if True:
                p.add(Claim("activity", field, {"title": title, "source": SRC},
                            [Evidence(f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}", "official_registry",
                                      p.notes.get("entity_retrieved_at") or "", p.notes.get("entity_sha") or "",
                                      f"{field}: {date}", "registry_field_date", source_name=SRC)],
                            label=title.split(":")[0], effective_date=date, key=f"activity:{field}:{date}"))
        for h in ent.get("historiskeNavn") or []:
            if isinstance(h, dict) and h.get("tilDato"):
                p.add(Claim("activity", "renamed", {"title": f"Renamed from {h.get('navn')}", "source": SRC},
                            [Evidence(f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}", "official_registry",
                                      p.notes.get("entity_retrieved_at") or "", p.notes.get("entity_sha") or "",
                                      f"historiskeNavn: {h.get('navn')} until {h.get('tilDato')}", "registry_field_date", source_name=SRC)],
                            label="Changed name", effective_date=h["tilDato"][:10], key=f"activity:renamed:{h.get('navn')}"))
        for role in p.notes.get("role_groups", []):
            if role.get("changed"):
                p.add(Claim("activity", "roles_changed", {"title": f"{role['group']} registered", "source": SRC},
                            [Evidence(f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}/roller", "official_registry",
                                      role["retrieved_at"], role["sha"], f"{role['group']} sistEndret {role['changed']}",
                                      "registry_roles_date", source_name=SRC)],
                            label="Role register change", effective_date=role["changed"],
                            key=f"activity:roles_changed:{role['group']}:{role['changed']}"))
        # state aid
        body = json.dumps([{"field": "STOETTEMOTTAKER_ORGNR", "value": org, "matchType": "EXACT_MATCH"}]).encode()
        aid = await c.post("stotteregisteret", AID, body, headers={"Content-Type": "application/json", "Accept": "application/json"})
        if not aid.ok:
            p.error("stotteregisteret", f"state-aid search failed ({aid.status or aid.error})")
        if aid.ok:
            rows = json.loads(aid.body).get("stoettetildeling") or []
            n = 0
            for r in rows:
                recv = [x for x in r.get("rolle") or [] if x.get("type") == "rolletype.stoettemottaker"]
                if not any((x.get("rolleinnehaverVirksomhet") or {}).get("organisasjonsnummer") == org for x in recv):
                    continue  # the register's own recipient must be exactly this entity
                giver = next(((x.get("rolleinnehaverVirksomhet") or {}).get("navn") for x in r.get("rolle") or []
                              if x.get("type") == "rolletype.stoettegiver"), None)
                inst = (r.get("stoetteinstrument") or "").split(".")[-1]
                amt = (r.get("tildeltBeloep") or {})
                value = {"title": f"State aid: {INSTRUMENT.get(inst, inst)} from {giver or 'a public body'}",
                         "amount": amt.get("beloep"), "currency": amt.get("valuta"), "giver": giver,
                         "instrument": INSTRUMENT.get(inst, inst), "reference": r.get("stoettetiltaksnummer"),
                         "scheme": r.get("tilknyttetStoetteordning"), "url": AID_PUBLIC, "source": "Støtteregisteret"}
                p.add(Claim("activity", "state_aid_award", value,
                            [Evidence(AID + f"#orgnr={org}", "official_registry", aid.retrieved_at, aid.sha256,
                                      clip(f"stoettetiltak {r.get('stoettetiltaksnummer')}: {inst} {amt.get('beloep')} {amt.get('valuta')} "
                                           f"from {giver}, tildelingsdato {r.get('tildelingsdato')}", 300),
                                      "state_aid_register_exact_orgnr", http_status=aid.status, source_name="Støtteregisteret")],
                            label="State aid received", effective_date=r.get("tildelingsdato"),
                            key=f"activity:state_aid_award:{r.get('stoettetiltaksnummer')}"))
                n += 1
            if n:
                self.aid_companies += 1

    def report(self) -> dict:
        return {"companies_with_state_aid": self.aid_companies, "companies_with_account_copies": self.pdf_companies,
                "account_copy_rate_limit_pauses": self.copies_rate_limited}
