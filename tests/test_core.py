import copy

from kildespor import siteparse as sp
from kildespor.claims import Claim, Evidence, Profile
from kildespor.discovery import Candidate, candidates, domain_of, name_domains, registrable
from kildespor.envelope import build
from kildespor.refresh import diff
from kildespor.site import SiteResult, verify
from kildespor.util import norm_phone


def page(text, url="https://firma.no/", title="Firma AS", links=None):
    p = sp.Page(url=url, final_url=url, title=title, text=text, links=links or [])
    p.sha256 = "0" * 64
    p.retrieved_at = "2026-10-14T00:00:00Z"
    return p


ENT = {"navn": "SANDNES ELEKTRISKE AS", "organisasjonsnummer": "810034882", "telefon": "51 66 70 20",
       "forretningsadresse": {"adresse": ["Strandgata 21"], "postnummer": "4307", "poststed": "SANDNES", "kommune": "SANDNES"}}


def test_orgnr_checksum():
    assert sp.valid_orgnr("810034882")
    assert sp.valid_orgnr("938702675")
    assert not sp.valid_orgnr("810034883")
    assert not sp.valid_orgnr("123456789")


def test_orgnr_mentions_spacing_variants():
    for s in ("Org.nr 810 034 882", "Org. nr.: 810034882 MVA", "NO 810.034.882 MVA", "Foretaksregisteret 810-034-882"):
        assert [n for n, _ in sp.orgnr_mentions(s)] == ["810034882"], s


def test_name_domains():
    d = name_domains("SANDNES ELEKTRISKE AS")
    assert d[0] == "sandneselektriske.no" and "sandnes-elektriske.no" in d
    assert "xn--nyekjkkenhuset-uqb.no" in name_domains("NYE KJØKKENHUSET AS")
    assert all(not x.startswith("as.") for x in name_domains("AS"))


def test_candidates_skip_freemail_and_shared_platforms():
    ent = {"navn": "X AS", "epostadresse": "ola@gmail.com", "hjemmeside": "www.x-firma.no"}
    c = candidates(ent, [{"epost": "styret@styrerommet.no"}])
    assert [x.domain for x in c if x.declared] == ["x-firma.no"]


def test_hosted_domains_keep_their_subdomain():
    assert registrable("bimbo.weebly.com") == "bimbo.weebly.com"
    assert registrable("www.firma.co.uk") == "firma.co.uk"
    assert domain_of("https://www.Firma.no/kontakt") == "firma.no"


def test_social_links():
    p = page("", links=[("https://www.facebook.com/sharer/sharer.php?u=x", ""), ("https://www.facebook.com/sandnesel/", ""),
                        ("https://no.linkedin.com/company/sandnes-elektriske", ""), ("https://www.instagram.com/p/abc/", "")])
    got = {(x[0], x[2]) for x in sp.socials(p)}
    assert got == {("facebook", "sandnesel"), ("linkedin", "company/sandnes-elektriske")}


def test_phone_normalisation():
    assert norm_phone("+47 51 66 70 20") == "51667020"
    assert norm_phone("0047 51667020") == "51667020"


def test_verify_exact_on_orgnr():
    res = SiteResult(Candidate("sandneselektriske.no", "name_derived"), "ambiguous", "", home=page("Org.nr 810 034 882"))
    res.pages = [res.home]
    assert verify(res, ENT, [], "810034882").status == "exact"


def test_verify_rejects_site_of_another_entity():
    res = SiteResult(Candidate("sandnes.no", "name_derived"), "ambiguous", "", home=page("Sandnes Elektriske. Org.nr. 938 702 675"))
    res.pages = [res.home]
    out = verify(res, ENT, [], "810034882")
    assert out.status == "other_entity"


def test_verify_name_without_address_is_not_enough():
    res = SiteResult(Candidate("sandneselektriske.no", "name_derived"), "ambiguous", "",
                     home=page("Sandnes Elektriske AS leverer elektro i Oslo"))
    res.pages = [res.home]
    assert verify(res, ENT, [], "810034882").status == "ambiguous"


def test_verify_phone_proof():
    res = SiteResult(Candidate("sandneselektriske.no", "name_derived"), "ambiguous", "",
                     home=page("Ring oss på telefon 51 66 70 20", links=[("tel:+4751667020", "51 66 70 20")]))
    res.pages = [res.home]
    out = verify(res, ENT, [], "810034882")
    assert out.status == "exact" and out.proofs[0].kind == "phone"


def _env(values):
    p = Profile("810034882")
    for field, v in values:
        ev = Evidence("https://data.brreg.no/x", "official_registry", "2026-10-14T00:00:00Z", "a" * 64, f"{field}: {v}", "registry_field")
        p.add(Claim("people", field, v, [ev], key=f"people:{field}:{v['name'] if isinstance(v, dict) else v}"))
    return build(p, run_id="r", started_at="2026-10-14T00:00:00Z", completed_at="2026-10-14T00:00:01Z",
                 operations={}, changes=None)


def test_refresh_is_idempotent():
    a = _env([("registered_role", {"name": "Ola Nordmann", "role": "Daglig leder"})])
    b = copy.deepcopy(a)
    b["run"]["run_id"] = "r2"
    ch = diff(b, a)
    assert ch["events"] == []


def test_refresh_reports_new_and_ended_roles_with_evidence():
    a = _env([("registered_role", {"name": "Ola Nordmann", "role": "Daglig leder"})])
    b = _env([("registered_role", {"name": "Kari Nordmann", "role": "Daglig leder"})])
    ch = diff(b, a)
    kinds = sorted(e["type"] for e in ch["events"])
    assert kinds == ["ended_role", "new_role"]
    assert all(e.get("previous_evidence") or e.get("current_evidence") for e in ch["events"])


def test_refresh_keeps_values_when_source_failed():
    a = _env([("registered_role", {"name": "Ola Nordmann", "role": "Daglig leder"})])
    b = _env([])
    for s in b["field_states"]:
        if s["family"] == "people":
            s["state"] = "failed"
    ch = diff(b, a)
    assert ch["events"] == [] and ch["carried_forward"] == 1
    assert b["claims"][0]["carried_forward"] is True


def test_exact_legal_name_proof_keeps_norwegian_letters():
    ent = {"navn": "RÅ SERVICE AS", "forretningsadresse": {}}
    res = SiteResult(Candidate("raservice.no", "name_derived"), "ambiguous", "", home=page("RA Service AS er et firma", url="https://www.raservice.no/", title="RA Service AS"))
    res.pages = [res.home]
    assert verify(res, ent, [], "933126919").status == "ambiguous"
    ent2 = {"navn": "FJELLFORM AS", "forretningsadresse": {}}
    res2 = SiteResult(Candidate("fjellform.no", "name_derived"), "ambiguous", "", home=page("Velkommen", url="https://www.fjellform.no/", title="Fjellform AS"))
    res2.home.site_name = "Fjellform AS"
    res2.pages = [res2.home]
    out = verify(res2, ent2, [], "933355950")
    assert out.status == "exact" and out.proofs[0].kind == "legal_name"


def test_exact_legal_name_needs_a_name_derived_domain():
    ent = {"navn": "FJELLFORM AS", "forretningsadresse": {}}
    res = SiteResult(Candidate("fjell.no", "name_derived"), "ambiguous", "", home=page("Kunde: Fjellform AS", url="https://fjell.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "933355950").status == "ambiguous"
