"""Regression tests for the wrong claims found by the Nov 14 independent audit (eval/audit-r2)."""
from kildespor import siteparse as sp
from kildespor.claims import Profile
from kildespor.discovery import Candidate
from kildespor.extract import _postal_addresses, abroad, handle_matches
from kildespor.news import title_rejected, url_rejected
from kildespor.site import SiteResult


def page(url: str, text: str, title: str = "") -> sp.Page:
    return sp.Page(url=url, final_url=url, title=title, text=text, links=[])


def site(url: str, text: str) -> SiteResult:
    pg = page(url, text)
    return SiteResult(Candidate(url.split("/")[2], "registry_website"), "exact", "", home=pg, pages=[pg])


KROULI = {"navn": "KROULI AS", "forretningsadresse": {"postnummer": "1363", "kommune": "BÆRUM"}}


def test_foreign_group_site_is_abroad():
    res = site("https://www.krouli.com/", "Krouli Group. Head office Nacka, Sweden. +46 8 52518743. sales@krouli.com #000047")
    assert abroad(res, KROULI)


def test_site_with_a_norwegian_phone_or_postcode_is_not_abroad():
    assert not abroad(site("https://www.krouli.com/", "Ring +47 22 33 44 55 or +46 8 52518743"), KROULI)
    assert not abroad(site("https://www.krouli.com/", "O.H. Bangs vei 17, 1363 Høvik. +46 8 52518743"), KROULI)
    assert not abroad(site("https://www.krouli.no/", "+46 8 52518743"), KROULI)


def test_chain_site_addresses_of_other_shops_are_skipped():
    ent = {"navn": "CULINA THOMSEN AS", "forretningsadresse": {"postnummer": "5132", "kommune": "BERGEN"}}
    p = Profile("981882423")
    pg = page("https://www.culina.no/kontakt", "Culina Bærum\nHolmaveien 20\n1339 Vøyenenga\nCulina Bergen\nLiamyrveien 15\n5132 Nyborg")
    _postal_addresses(p, pg, ent)
    got = [c.value for c in p.claims]
    assert got == ["Liamyrveien 15, 5132 Nyborg"]


def test_care_of_addresses_are_skipped():
    ent = {"navn": "SAMEIET X", "forretningsadresse": {"postnummer": "4317"}}
    p = Profile("1")
    _postal_addresses(p, page("https://x.no/", "c/o Bate boligbyggelag\nBadehusgata 33\n4317 Sandnes"), ent)
    assert not p.claims


def test_wikidata_handles_of_another_firm_fail_the_name_rule():
    ent = {"navn": "ANTON OG AASLAUG ARESKAUS STIFTELSE"}
    assert not handle_matches("arntzendebesche", ent, "")
    assert not handle_matches("adeb.law", ent, "")
    assert not handle_matches("BOSBil", {"navn": "BERTEL O. STEEN HOLDING AS"}, "")


def test_news_defaults_in_any_language_and_list_pages():
    assert title_rejected("Witaj, świecie!") == "default post"
    assert url_rejected("https://promaninvest.no/witaj-swiecie/") == "default post"
    assert url_rejected("https://gassecure.com/news/p2") == "page number"
    assert title_rejected("News - GasSecure", {"gassecure"}).startswith("section page title")
    assert title_rejected("Ny avtale med Statens vegvesen - GasSecure", {"gassecure"}) == ""


def test_address_lead_in_is_cut_but_street_words_stay():
    ent = {"navn": "GRINI HJEMMEBAKERI AS", "forretningsadresse": {"postnummer": "1349"}}
    p = Profile("1")
    _postal_addresses(p, page("https://x.no/", "Gården har adresse Grinivegen 12\n1349 Rykkinn"), ent)
    p2 = Profile("2")
    _postal_addresses(p2, page("https://y.no/", "Kong Oscars gate 3\n1349 Rykkinn"), ent)
    assert [c.value for c in p.claims] == ["Grinivegen 12, 1349 Rykkinn"]
    assert [c.value for c in p2.claims] == ["Kong Oscars gate 3, 1349 Rykkinn"]


def test_mailto_behind_a_different_visible_address_is_skipped():
    pg = sp.Page(url="https://novatek.no/kontakt", final_url="https://novatek.no/kontakt", title="", text="hani.alsaid@novatek.no",
                 links=[("mailto:anette.moen@novatek.no", "hani.alsaid@novatek.no"), ("mailto:post@novatek.no", "Send e-post")])
    assert sp.emails(pg) == ["post@novatek.no", "hani.alsaid@novatek.no"]
