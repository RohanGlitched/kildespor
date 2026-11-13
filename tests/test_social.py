from kildespor.extract import handle_matches, handle_name, split_words

BYGG = {"navn": "ROGER AAMODT BYGG AS", "forretningsadresse": {"kommune": "GJØVIK", "poststed": "GJØVIK"}}
MUSIKK = {"navn": "MUSIKK I INNLANDET AS", "forretningsadresse": {"kommune": "GJØVIK", "poststed": "GJØVIK"}}


def test_sister_company_handle_is_rejected():
    # Builderr's Nov 13 audit: these belong to ROGER AAMODT EIENDOM AS, not ROGER AAMODT BYGG AS
    assert not handle_matches("rogeraamodteiendom", BYGG, "www.rogeraamodt.no")
    assert not handle_matches("rogeraamodtinvest", BYGG, "www.rogeraamodt.no")
    assert not handle_matches("rogeraamodtholding", BYGG, "www.rogeraamodt.no")


def test_own_handles_are_kept():
    assert handle_matches("rogeraamodtbygg", BYGG, "www.rogeraamodt.no")
    assert handle_matches("RogerAamodtBygg", BYGG, "www.rogeraamodt.no")
    assert handle_matches("rogeraamodt", BYGG, "www.rogeraamodt.no")  # the site's own name
    assert handle_matches("roger.aamodt.bygg.as", BYGG, "www.rogeraamodt.no")
    assert handle_matches("company/roger-aamodt-bygg-as", BYGG, "www.rogeraamodt.no")
    assert handle_matches("rogeraamodtbygggjovik", BYGG, "www.rogeraamodt.no")  # own place
    assert handle_matches("musikkinnlandet", MUSIKK, "musikkinnlandet.no")
    assert handle_matches("musikkiinnlandet", MUSIKK, "www.example.no")
    assert handle_matches("pages/Musikk-i-Innlandet/123456789012", MUSIKK, "www.example.no")


def test_partial_or_unrelated_handles_are_rejected():
    assert not handle_matches("bygg", BYGG, "www.rogeraamodt.no")  # one generic name word
    assert not handle_matches("aamodt", BYGG, "www.rogeraamodt.no")  # part of the name only
    assert not handle_matches("byggmakker", BYGG, "www.rogeraamodt.no")
    assert not handle_matches("innlandetmusikkfest", MUSIKK, "musikkinnlandet.no")
    assert not handle_matches("rogeraamodt-", BYGG, "www.rogeraamodt.no")  # truncated slug
    assert not handle_matches("rogeraamodtltd", BYGG, "www.rogeraamodt.no")  # foreign company form


def test_handle_name_and_split():
    assert handle_name("p/Fidi-Video-100063123") == "Fidi-Video"
    assert handle_name("pages/Roger-Aamodt/123") == "Roger-Aamodt"
    assert handle_name("@rogeraamodt") == "rogeraamodt"
    assert split_words("rogeraamodteiendom", {"roger", "aamodt", "eiendom"}) == ["roger", "aamodt", "eiendom"]
    assert split_words("rogeraamodtx", {"roger", "aamodt"}) is None
