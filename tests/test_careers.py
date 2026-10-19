"""Careers source: platform parsers on saved responses, the identity rule and de-duplication. No network."""
import json
from pathlib import Path

from kildespor import siteparse as sp
from kildespor.claims import Claim, Evidence, Profile
from kildespor.sources import careers as cs

FX = Path(__file__).parent / "fixtures" / "careers"
VIA = {"url": "https://firma.no/karriere", "retrieved_at": "2026-10-19T00:00:00Z", "sha256": "0" * 64, "status": 200,
       "span": "link on https://firma.no/karriere", "host": "firma.no"}


class F:  # a stand-in for http.Fetched
    def __init__(self, url, body=b""):
        self.url = self.final_url = url
        self.body = body
        self.retrieved_at = "2026-10-19T00:00:00Z"
        self.sha256 = "1" * 64
        self.status = 200


def who(name, orgnr="923609016"):
    return cs.Who({"navn": name, "organisasjonsnummer": orgnr}, [], orgnr)


def test_identity_rule():
    w = who("PINCHO NATION NORGE AS")
    assert w.match("Pincho Nation Norway")
    assert w.match("PINCHO NATION NORGE AS")
    assert not w.match("Pincho Nation Tromsø AS")          # a sister company's full registered name
    assert not who("MIO BPA AS").match("MiO Gruppen")        # the group, not the company
    assert who("MIO BPA AS").match("Mio BPA")
    assert not who("ABERIA AS").match("Aberia Omsorg & Assistanse AS")
    assert not who("RANDSTAD AS").match("Gjensidige Forsikring Fredrikstad")
    assert not who("AIMO PARK NORWAY AS").match("Aimo Park Sverige AB")
    assert who("AIMO PARK NORWAY AS").match("Aimo Park")
    assert not who("COOP ØST FORVALTNING AS").match("Coop Øst")
    assert not who("COOP ØST SA").match("Coop Øst Forvaltning")
    assert who("KONGSBERG DEFENCE & AEROSPACE AS").match("Kongsberg Defence & Aerospace")
    assert not who("NILLE AS").match("Nille Holding")
    assert who("BPA NORD AS").match("BPA Nord")


def test_teamtailor_rss():
    account, posts = cs.parse_teamtailor_rss((FX / "teamtailor.rss").read_bytes())
    assert account == "Pincho Nation Norway"
    assert len(posts) == 3
    p = posts[0]
    assert p.title.startswith("Hovmester") and p.published == "2026-09-30" and p.location == "Kristiansand"
    assert p.url.startswith("https://pinchonationnorway.teamtailor.com/jobs/") and p.country == "NO"


def test_recman_list_keeps_employer_per_posting():
    tok, web = cs.recman_token((FX / "recman-jobs-page.html").read_text(encoding="utf-8"))
    assert tok.startswith("617-1141-") and web == "www.jeffersonwells.no"
    posts = cs.parse_recman_jobs(json.loads((FX / "recman-jobs.json").read_text(encoding="utf-8")), "https://jeffersonwells.recman.page")
    assert [p.employer for p in posts] == ["Aimo Park Norway", "KONGSBERG DEFENCE & AEROSPACE AS"]  # internal ad dropped
    assert posts[0].url == "https://jeffersonwells.recman.page/job/489341"
    assert posts[0].published == "2026-10-07" and posts[0].deadline == "2026-11-08"


def test_reachmee_list_and_customer_script():
    account, posts = cs.parse_reachmee_list((FX / "reachmee-list.html").read_text(encoding="utf-8"),
                                            "https://web103.reachmee.com/ext/I012/2645/main?site=6")
    assert account == "Finnfjord AS"
    assert [p.title for p in posts] == ["Åpen Søknad", "Lærling"]
    assert posts[1].deadline == "2030-12-31" and posts[1].location == "Senja" and posts[1].id == "7"
    url = cs.reachmee_main_from_js((FX / "reachmee-customer.js").read_text(encoding="utf-8"), "web103.reachmee.com")
    assert url == "https://web103.reachmee.com/ext/I010/2617/main?site=13&validator=18bde116e33a96c38adf01e0e74126e0&lang=NO"


def test_jobylon_embed():
    posts = cs.parse_jobylon_embed((FX / "jobylon-embed.html").read_text(encoding="utf-8"))
    assert len(posts) == 2
    assert all(p.employer == "JAG Assistanse AS" for p in posts)
    assert posts[0].url.startswith("https://emp.jobylon.com/jobs/390423-")
    assert posts[0].published == "2026-10-19" and posts[0].deadline == "2026-11-27"
    assert "\\u" not in posts[1].title


def test_easycruit_xml():
    posts = cs.parse_easycruit_xml((FX / "easycruit.xml").read_bytes())
    assert posts and all(p.url.startswith("https://kongsberg.easycruit.com/vacancy/") for p in posts)
    assert posts[0].published and posts[0].deadline and posts[0].employer


def test_jobbnorge_feed():
    posts = cs.parse_jobbnorge(json.loads((FX / "jobbnorge.json").read_text(encoding="utf-8")))
    bpa = [p for p in posts if p.extra["employer_id"] == 2823]
    assert len(bpa) == 2 and bpa[0].employer == "BPA Nord" and bpa[0].published and bpa[0].deadline is None
    assert bpa[0].deadline_text == "Løpende"


def test_greenhouse_and_lever():
    gh = cs.parse_greenhouse(json.loads((FX / "greenhouse.json").read_text(encoding="utf-8")))
    assert len(gh) == 2 and gh[0].published
    lv = cs.parse_lever(json.loads((FX / "lever.json").read_text(encoding="utf-8")))
    assert lv[0].published and lv[0].url.startswith("https://jobs.lever.co/")


def test_scan_finds_embeds_in_raw_html():
    html = ('<iframe src="https://web103.reachmee.com/ext/I012/2645/main?site=6&amp;validator=abc&amp;lang=NO"></iframe>'
            '<script>var jbl_company_id = 2556;</script>'
            '<script src="https://web103.reachmee.com/customerjs/I021-1798-6.js"></script>'
            '<a href="https://miogruppen.teamtailor.com/jobs">Jobs</a><a href="https://jobs.mojob.io/45906/">Søk</a>'
            '<a href="https://www.jobbnorge.no/ledige-stillinger/stilling/310353">x</a>'
            '<a href="https://candidate.webcruiter.com/cv?advertid=1">Søk</a>')
    targets, ads = cs.scan(html, VIA)
    kinds = {t.key for t in targets}
    assert {"reachmee:I012/2645/6", "jobylon:c2556", "reachmee:I021/1798/6", "teamtailor:miogruppen"} <= kinds
    rm = next(t for t in targets if t.key == "reachmee:I012/2645/6")
    assert rm.url == "https://web103.reachmee.com/ext/I012/2645/main?site=6&validator=abc&lang=NO"
    assert ads["mojob"] == ["https://jobs.mojob.io/45906/"] and ads["jobbnorge"] == ["310353"]
    assert cs.not_read(html) == ["webcruiter"]


def test_mojob_jsonld_names_a_sister_company():
    pg = sp.parse((FX / "mojob-ad.html").read_text(encoding="utf-8"), "https://jobs.mojob.io/45906/", "https://jobs.mojob.io/45906/")
    posts = cs.jsonld_postings(pg, "mojob")
    assert posts[0].employer == "Aberia Omsorg & Assistanse AS" and posts[0].published == "2026-05-05"
    assert not who("ABERIA AS").match(posts[0].employer)


def _publish(name, found, nav=None):
    p = Profile("923609016")
    for title, date in nav or []:
        p.add(Claim("jobs", "job_posting", {"title": title, "url": "https://arbeidsplassen.nav.no/x/" + title, "published": date},
                    [Evidence("https://pam-stilling-feed.nav.no/x", "public_job_board", "t", "0" * 64, "x", "nav")],
                    effective_date=date, key="jobs:job_posting:nav:" + title))
    src = cs.Careers()
    src._publish(p, who(name), found)
    return p, src


def test_group_account_listing_another_employer_is_skipped():
    posts = cs.parse_recman_jobs(json.loads((FX / "recman-jobs.json").read_text(encoding="utf-8")), "https://jeffersonwells.recman.page")
    f = F("https://jeffersonwells.recman.page/api/jobs")
    p, src = _publish("AIMO PARK NORWAY AS", [(x, VIA, f) for x in posts])
    jobs = [c for c in p.claims if c.field == "job_posting"]
    assert len(jobs) == 1 and jobs[0].value["employer"] == "Aimo Park Norway" and jobs[0].relationship == "exact"
    assert src.stats["skipped_other_employer"] == 1
    assert {e.source_class for e in jobs[0].evidence} == {"public_job_board", "company_owned"}
    assert any(c.field == "job_ad_published" and c.effective_date == "2026-10-07" for c in p.claims)


def test_account_name_rule_and_nav_duplicates():
    account, posts = cs.parse_teamtailor_rss((FX / "teamtailor.rss").read_bytes())
    for x in posts:
        x.extra["account"] = account
    f = F("https://pinchonationnorway.teamtailor.com/jobs.rss")
    # the first ad is also on NAV with the same title and date: published once
    p, src = _publish("PINCHO NATION NORGE AS", [(x, VIA, f) for x in posts], nav=[(posts[0].title, posts[0].published)])
    titles = [c.value["title"] for c in p.claims if c.field == "job_posting" and not c.key.startswith("jobs:job_posting:nav")]
    assert len(titles) == 2 and posts[0].title not in titles and src.stats["skipped_duplicate"] == 1
    # the same account read for another company publishes nothing
    p2, _ = _publish("PINCHO NATION TRONDHEIM AS", [(x, VIA, f) for x in posts])
    assert not [c for c in p2.claims if c.field == "job_posting"]


def test_expired_abroad_and_other_orgnr_are_skipped():
    base = dict(platform="teamtailor", title="Utvikler", url="https://firma.teamtailor.com/jobs/1-utvikler", employer="Firma AS")
    expired = cs.Posting(id="1", deadline="2020-01-01", **base)
    abroad = cs.Posting(id="2", country="united states", **{**base, "url": base["url"] + "2"})
    other = cs.Posting(id="3", orgnr="810034882", **{**base, "url": base["url"] + "3"})
    ok = cs.Posting(id="4", published="2026-10-01", **{**base, "url": base["url"] + "4", "title": "Selger"})
    p, src = _publish("FIRMA AS", [(x, VIA, F("https://firma.teamtailor.com/jobs.rss")) for x in (expired, abroad, other, ok)])
    assert [c.value["title"] for c in p.claims if c.field == "job_posting"] == ["Selger"]
    assert src.stats["skipped_expired"] == 1 and src.stats["skipped_abroad"] == 1 and src.stats["skipped_other_employer"] == 1


def _page(url, title, text, links=None):
    pg = sp.Page(url=url, final_url=url, title=title, text=text, links=links or [])
    pg.sha256, pg.retrieved_at, pg.status = "0" * 64, "2026-10-19T00:00:00Z", 200
    return pg


def test_own_site_ads():
    w = who("ÅDALEN TRUCK AS")
    ad = _page("https://www.aadalen.no/ledige-stillinger/ledig-tekniker-stilling-ostfold-akershus/",
               "Ledig tekniker stilling - Østfold/Akershus - Ådalen Truck",
               "Servicetekniker for lift og truck\nStillingsprosent: 100%\nÅdalen Truck AS er en av Norges ledende maskinleverandører")
    post = cs.own_site_ad(ad, "Se stillingsbeskrivelse", w)
    assert post and post.title == "Ledig tekniker stilling - Østfold/Akershus"
    # a shopping centre listing a tenant's ad
    tenant = _page("https://trondheimtorg.no/stillinger/ledig-stilling-hos-lekia/", "Ledig stilling hos Lekia - Trondheim Torg",
                   "Lekia Trondheim Torg søker butikkmedarbeider. Søknadsfrist: 1. november 2026. Trondheim Torg AS")
    assert cs.own_site_ad(tenant, "Ledig stilling hos Lekia", who("TRONDHEIM TORG AS")) is None
    # a page without any ad wording, or one that does not name the company, is not an ad
    assert cs.own_site_ad(_page(ad.url, ad.title, "Ådalen Truck AS selger truck"), "x", w) is None
    assert cs.own_site_ad(_page(ad.url, ad.title, "Stillingsprosent: 100%. Vi søker en tekniker."), "x", w) is None


def test_children_and_list_links():
    pg = _page("https://firma.no/karriere/", "Karriere",
               "", [("https://firma.no/karriere/ledige-stillinger/", "Se alle ledige stillinger"),
                    ("https://firma.no/karriere/utvikler-oslo/", "Utvikler i Oslo"),
                    ("https://firma.no/om-oss/", "Om oss"), ("https://annen.no/karriere/x/", "x")])
    assert cs._list_links(pg, "firma") == ["https://firma.no/karriere/ledige-stillinger/"]
    assert [u for u, _ in cs._children(pg, "firma")] == ["https://firma.no/karriere/ledige-stillinger/",
                                                          "https://firma.no/karriere/utvikler-oslo/"]
    assert cs.CAREERS_PATH.search("/jobb-hos-oss/") and not cs.CAREERS_PATH.search("/butikk/4-hjulstilling")
    assert not cs.CAREERS_PATH.search("/kurs/kursbestilling") and not cs.CAREERS_PATH.search("/digital-ku-utstilling/")


def test_several_jsonld_ads_on_one_careers_page():
    ld = [{"@context": "https://schema.org", "@type": "JobPosting", "title": t, "datePosted": "2026-06-17",
           "hiringOrganization": {"@type": "Organization", "name": "OPCOM AS"},
           "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "NO"}}}
          for t in ("Prosjektleder", "AI-utvikler")]
    html = "<html><head><title>Karriere</title>" + "".join(
        f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in ld) + "</head><body>x</body></html>"
    pg = sp.parse(html, "https://opcom.no/karriere", "https://opcom.no/karriere")
    posts = cs.jsonld_postings(pg)
    p, _ = _publish("OPCOM AS", [(x, VIA, None) for x in posts])
    assert sorted(c.value["title"] for c in p.claims if c.field == "job_posting") == ["AI-utvikler", "Prosjektleder"]


def test_page_about_working_here_is_not_an_ad():
    w = who("PRIMA ASSISTANSE AS")
    info = _page("https://prima-assistanse.no/karriere/jobbe-som-bpa-assistent/", "BPA-assistent - Mer enn bare en jobb - Prima Assistanse",
                 "Hvor stor stilling kan jeg få? Arbeidskontrakten regulerer stillingsprosent. Send en åpen søknad til Prima Assistanse AS.")
    assert cs.own_site_ad(info, "Les mer", w) is None


def test_platforms_not_yet_hand_checked_publish_nothing():
    posts = cs.parse_greenhouse(json.loads((FX / "greenhouse.json").read_text(encoding="utf-8")))
    for x in posts:
        x.employer = "Firma AS"
    assert "greenhouse" not in cs.ENABLED and "lever" not in cs.ENABLED and "mojob" not in cs.ENABLED
    p, _ = _publish("FIRMA AS", [(x, VIA, F("https://boards-api.greenhouse.io/v1/boards/firma/jobs")) for x in posts])
    assert not [c for c in p.claims if c.field == "job_posting"]
