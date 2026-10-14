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
                     home=page("Sandnes Elektriske. Ring oss på telefon 51 66 70 20", links=[("tel:+4751667020", "51 66 70 20")]))
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
    ent2 = {"navn": "FJELLFORM AS", "forretningsadresse": {"poststed": "GEILO", "kommune": "HOL", "postnummer": "3580"}}
    res2 = SiteResult(Candidate("fjellform.no", "name_derived"), "ambiguous", "", home=page("Velkommen til oss på Geilo", url="https://www.fjellform.no/", title="Fjellform AS"))
    res2.home.site_name = "Fjellform AS"
    res2.pages = [res2.home]
    out = verify(res2, ent2, [], "933355950")
    assert out.status == "exact" and out.proofs[0].kind == "legal_name"


def test_exact_legal_name_needs_a_name_derived_domain():
    ent = {"navn": "FJELLFORM AS", "forretningsadresse": {}}
    res = SiteResult(Candidate("fjell.no", "name_derived"), "ambiguous", "", home=page("Kunde: Fjellform AS", url="https://fjell.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "933355950").status == "ambiguous"


def test_postcode_town_stays_on_one_line():
    m = sp.POSTCODE_RE.search("Mosseveien 39B, 1610 Fredrikstad\nNorway")
    assert m and m.group(2) == "Fredrikstad"


def test_care_of_line_is_skipped_for_street_proof():
    ent = {"navn": "PLATO CATERING AS", "forretningsadresse": {"adresse": ["c/o Factory Tøyen", "Kjølberggata 21"], "postnummer": "0653"}}
    res = SiteResult(Candidate("platocatering.no", "name_derived"), "ambiguous", "",
                     home=page("Plato Catering\nKjølberggata 21, 0653 Oslo", url="https://platocatering.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "999999999").proofs[0].kind == "name_address"


def test_role_holder_and_all_name_tokens():
    ent = {"navn": "CHRISTIAN MEAAS SVENDSEN AS", "forretningsadresse": {}}
    people = [{"name": "Christian Meaas Svendsen", "kind": "person", "role": "Daglig leder"}]
    res = SiteResult(Candidate("christianmeaassvendsen.no", "name_derived"), "ambiguous", "",
                     home=page("Christian Meaas Svendsen – fotograf", url="https://christianmeaassvendsen.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "999999999", people).status == "exact"
    other = SiteResult(Candidate("svendsen.no", "name_derived"), "ambiguous", "",
                       home=page("Christian Meaas Svendsen", url="https://svendsen.no/"))
    other.pages = [other.home]
    assert verify(other, ent, [], "999999999", []).status == "ambiguous"


def test_housing_coop_needs_its_own_number():
    ent = {"navn": "BREKKENE BORETTSLAG", "organisasjonsform": {"kode": "BRL"},
           "forretningsadresse": {"poststed": "BERGEN", "kommune": "BERGEN"}}
    name_only = SiteResult(Candidate("brekkene-borettslag.no", "name_derived"), "ambiguous", "",
                           home=page("Brekkene Borettslag i Bergen", url="https://brekkene-borettslag.no/"))
    name_only.pages = [name_only.home]
    assert verify(name_only, ent, [], "938702675").status == "ambiguous"
    numbered = SiteResult(Candidate("brekkene-borettslag.no", "name_derived"), "ambiguous", "",
                          home=page("Brekkene Borettslag, org.nr 938 702 675", url="https://brekkene-borettslag.no/"))
    numbered.pages = [numbered.home]
    assert verify(numbered, ent, [], "938702675").status == "exact"


def test_phone_alone_needs_the_legal_name_on_the_site():
    ent = {"navn": "KLAVENESS FINANS AS", "telefon": "23 11 00 00", "forretningsadresse": {}}
    res = SiteResult(Candidate("klaveness.com", "registry_website"), "ambiguous", "",
                     home=page("Klaveness group. Phone 23 11 00 00", url="https://www.klaveness.com/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "993345911").status == "ambiguous"


def test_copyright_of_a_longer_sister_name_is_another_entity():
    ent = {"navn": "NORRØN AS", "forretningsadresse": {"adresse": ["Gate 1"], "postnummer": "0150"}}
    res = SiteResult(Candidate("norron.no", "name_derived"), "ambiguous", "",
                     home=page("Norrøn\nGate 1, 0150 Oslo\n© 2026 Norrøn Bolig AS", url="https://norron.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "994916009").status == "other_entity"


def test_labelled_number_failing_the_checksum_still_blocks_weak_proof():
    ent = {"navn": "UNIVERSI AS", "forretningsadresse": {"adresse": ["Vei 2"], "postnummer": "0150"}}
    res = SiteResult(Candidate("universi.no", "name_derived"), "ambiguous", "",
                     home=page("Universi AS\nVei 2, 0150 Oslo\nOrg.nr. 932 953 520", url="https://universi.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "984840551").status == "other_entity"


def test_legal_form_is_case_sensitive_and_needs_the_town():
    ent = {"navn": "NEMITEK AS", "forretningsadresse": {"poststed": "OSLO", "kommune": "OSLO", "postnummer": "0150"}}
    res = SiteResult(Candidate("nemitek.com", "name_derived"), "ambiguous", "",
                     home=page("Upload your game save to Nemitek as part of the beta. Oslo", url="https://nemitek.com/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "915903037").status == "ambiguous"


def test_copyright_line_naming_another_company_rejects_the_site():
    ent = {"navn": "SUNNSAND AS", "forretningsadresse": {"adresse": ["Industrivegen 3"], "postnummer": "5412", "poststed": "STORD"}}
    res = SiteResult(Candidate("sunnsand.no", "name_derived"), "ambiguous", "",
                     home=page("Sunnsand\nIndustrivegen 3, 5412 Stord\n© 2026 Sunnhordland Sandblåsing AS", url="https://sunnsand.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "998680360").status == "other_entity"


def test_registry_website_alone_is_not_proof():
    ent = {"navn": "SAMEIET GJERDETUNET 1-11", "forretningsadresse": {}}
    res = SiteResult(Candidate("bate.no", "registry_website", "www.bate.no"), "ambiguous", "",
                     home=page("Bate boligbyggelag – Min side", url="https://www.bate.no/"))
    res.pages = [res.home]
    assert verify(res, ent, [], "912302792").status == "ambiguous"


def test_phone_parsing_rejects_foreign_years_and_country_code_prefix():
    p = page("Tlf: +971 5430 8123\nTelefon 2022 2021\nTelefon: +47 22 13 28 80", links=[("tel:+35810709000", "")])
    got = {d for d, _ in sp.phones(p)}
    assert got == {"22132880"}


def test_facebook_p_links_keep_their_slug():
    p = page("", links=[("https://www.facebook.com/p/Fidi-Video-100063/", ""), ("https://www.facebook.com/policies/", "")])
    assert [x[2] for x in sp.socials(p)] == ["p/Fidi-Video-100063"]


def test_source_has_no_control_characters():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "kildespor"
    bad = [str(p) for p in root.rglob("*.py") if any(c in p.read_text(encoding="utf-8") for c in "\x08\x0c\x0b")]
    assert bad == []


def test_resolver_fallback_accepts_idna_bytes(monkeypatch):
    import socket
    from kildespor import netfix

    def broken(host, port, family=0, type=0, proto=0, flags=0):
        if isinstance(host, (bytes, bytearray)) or not host[0].isdigit():
            raise socket.gaierror(11002, "getaddrinfo failed")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    monkeypatch.setattr(netfix, "_original", broken)
    monkeypatch.setattr(netfix, "_public", lambda name: ["34.128.161.34"] if name == "example.no" else [])
    assert netfix.getaddrinfo(b"example.no", 443)[0][4][0] == "34.128.161.34"
    assert netfix.getaddrinfo("example.no", 443)[0][4][0] == "34.128.161.34"
