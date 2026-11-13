"""Company news from a verified site: WordPress API, feeds, listings and article pages, and every reject rule.
No network: a fake client serves the saved responses under tests/fixtures/news."""
import asyncio
from datetime import date
from pathlib import Path

import pytest

from kildespor import news
from kildespor import siteparse as sp
from kildespor.claims import Profile
from kildespor.discovery import Candidate
from kildespor.http import Fetched
from kildespor.site import SiteResult
from kildespor.util import sha256_bytes

FX = Path(__file__).parent / "fixtures" / "news"
TODAY = date(2026, 11, 13)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(news, "today", lambda: TODAY)


def fetched(url, body: bytes, ctype="text/html; charset=utf-8", status=200, final=None):
    return Fetched(url, final or url, status, "2026-11-13T00:00:00Z", ctype, body, sha256_bytes(body))


class FakeClient:
    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    async def get(self, source, url, **kw):
        self.calls.append(url)
        for prefix, (name, ctype) in self.routes.items():
            if url.startswith(prefix):
                return fetched(url, (FX / name).read_bytes(), ctype)
        return fetched(url, b"not found", status=404)


def run(host="firma.no", client=None):
    return news.Run(client or FakeClient({}), host.removeprefix("www."), f"https://{host}", {"firma as"})


def page(url, html="", generator="", links=None, feeds=None):
    pg = sp.parse(html, url, url) if html else sp.Page(url=url, final_url=url, title="Firma AS")
    pg.sha256, pg.retrieved_at, pg.status = "0" * 64, "2026-11-13T00:00:00Z", 200
    if generator:
        pg.generator = generator
    if links is not None:
        pg.links = links
    if feeds is not None:
        pg.feeds = feeds
    return pg


def site(home, *more, domain="firma.no"):
    return SiteResult(Candidate(domain, "registry_website"), "exact", "orgnr", home=home, pages=[home, *more])


def go(client, res, p=None):
    p = p or Profile("810034882")
    trace = {}
    asyncio.run(news.add_company_news(client, p, res, trace))
    return p, trace


def items(p):
    return [c for c in p.claims if c.field == "company_news"]


# --- WordPress REST API ---------------------------------------------------------------------------------------

def test_wordpress_posts_keep_real_dated_posts_only():
    r = run("www.byggfirma.no")
    raw = (FX / "wp-posts.json").read_text(encoding="utf-8")
    got = news.parse_wp_posts(raw, fetched("https://www.byggfirma.no/wp-json/wp/v2/posts", raw.encode(), "application/json"), r)
    assert [(i.title, i.published) for i in got] == [
        ("Ny avtale med Åsane kommune om rehabilitering", "2026-10-02"),
        ("Vi har flyttet til nye lokaler på Kokstad", "2026-05-20"),
    ]
    assert got[0].url == "https://www.byggfirma.no/ny-avtale-med-asane-kommune/"
    assert got[0].source == "company WordPress API"
    span = got[0].evidence.claim_span
    assert '"date":"2026-10-02T09:15:00"' in span and "Ny avtale med \\u00c5sane" in span
    for piece in span.split(" · "):
        assert piece in raw  # quoted exactly as the API wrote it
    why = {w for w, _ in r.rejects}
    assert {"date in the future or before 2010", "link on another domain", "default post", "title under 12 characters"} <= why


def test_wordpress_hello_world_only_site_publishes_nothing():
    client = FakeClient({"https://firma.no/wp-json/": ("wp-hello.json", "application/json; charset=UTF-8")})
    home = page("https://firma.no/", generator="WordPress 6.6")
    p, trace = go(client, site(home))
    assert items(p) == []
    assert ("default post", "Hello world! <https://firma.no/hello-world/>") in trace["news"][0]["rejects"]


def test_wordpress_detected_from_assets_and_claims_written():
    client = FakeClient({"https://www.byggfirma.no/wp-json/": ("wp-posts.json", "application/json"),
                         "https://www.byggfirma.no/ny-avtale": ("wp-post-page.html", "text/html")})
    home = page("https://www.byggfirma.no/", links=[("https://www.byggfirma.no/wp-content/uploads/logo.png", "")])
    p, trace = go(client, site(home, domain="byggfirma.no"))
    got = items(p)
    assert len(got) == 2 and got[0].effective_date == "2026-10-02"
    # the newest post's page shows readers its date, and that page joins the evidence
    assert [e.extraction_method for e in got[0].evidence] == ["wordpress_rest_api", "article_visible_date"]
    assert got[0].evidence[1].claim_span == "Ny avtale med Åsane kommune om rehabilitering · 2. oktober 2026"
    assert len(got[1].evidence) == 1
    assert got[0].value == {"title": "Ny avtale med Åsane kommune om rehabilitering",
                            "url": "https://www.byggfirma.no/ny-avtale-med-asane-kommune/", "published": "2026-10-02",
                            "source": "company WordPress API"}
    assert got[0].key == "activity:company_news:https://www.byggfirma.no/ny-avtale-med-asane-kommune/"
    assert got[0].evidence[0].source_url.startswith("https://www.byggfirma.no/wp-json/wp/v2/posts?per_page=10&_fields=")
    assert client.calls[0].endswith("_fields=id,date,date_gmt,link,title,slug,type")
    assert trace["news"][0]["requests"] <= news.MAX_REQUESTS


def test_posts_that_show_no_date_are_projects_not_news():
    # a builder keeps its projects (homes for sale) as WordPress posts: the pages show readers no date
    client = FakeClient({"https://www.byggfirma.no/wp-json/": ("wp-posts.json", "application/json"),
                         "https://www.byggfirma.no/": ("wp-project-page.html", "text/html")})
    home = page("https://www.byggfirma.no/", generator="WordPress 6.6")
    p, trace = go(client, site(home, domain="byggfirma.no"))
    assert items(p) == []
    assert any(w == "posts show readers no date (projects, products or pages)" for w, _ in trace["news"][0]["rejects"])
    assert trace["news"][0]["requests"] == 3  # the API and two post pages


def test_stamps_keep_their_own_day():
    # the day the quoted stamp shows; a page that shows readers the neighbouring day wins when it is opened
    assert news.parse_machine_date("Wed, 26 Jul 2023 22:00:00 GMT") == date(2023, 7, 26)
    assert news.parse_machine_date("2021-12-01T00:13:00+0800") == date(2021, 12, 1)
    assert news.parse_machine_date("2026-06-30T22:30:00") == date(2026, 6, 30)
    html = "<html><body><h1>Discovering the Norwegian language</h1><p>Jul 27, 2023</p></body></html>"
    assert news.visible_date(html, "https://firma.no/post/x", "2023-07-26") == ("Jul 27, 2023", "2023-07-27")
    assert news.visible_date(html, "https://firma.no/post/x", "2023-07-20") == ("", "")


# --- feeds ----------------------------------------------------------------------------------------------------------

def test_rss_uses_pubdate_and_refuses_default_foreign_and_undated_items():
    r = run()
    got = news.parse_feed(fetched("https://firma.no/feed/", (FX / "feed.rss").read_bytes(), "application/rss+xml"), r)
    assert [(i.title, i.published) for i in got] == [("Firma AS åpner nytt verksted i Drammen", "2026-09-08"),
                                                     ("Vi søker nye lærlinger til høsten 2026", "2026-03-12")]
    assert got[0].evidence.claim_span == "Firma AS åpner nytt verksted i Drammen · Tue, 08 Sep 2026 08:30:00 +0000"
    assert got[0].evidence.extraction_method == "rss_item"
    why = dict((t.split(" <")[0], w) for w, t in r.rejects)
    assert why["Hello world!"] == "default post"
    assert why["Sak uten publiseringsdato i feeden"].startswith("no publish date")
    assert why["Omtale av oss hos en samarbeidspartner"] == "link on another domain"


def test_atom_updated_is_not_a_publish_date():
    r = run()
    got = news.parse_feed(fetched("https://firma.no/blogg/feed.atom", (FX / "feed-updated.atom").read_bytes(), "application/atom+xml"), r)
    assert [(i.title, i.published) for i in got] == [("Vi er sertifisert som Miljøfyrtårn", "2026-04-02")]
    assert ("no publish date (only an updated date)", "Slik velger du riktig varmepumpe") in r.rejects


def test_feed_where_every_item_shares_one_date_is_a_template():
    r = run()
    got = news.parse_feed(fetched("https://firma.no/feed/", (FX / "feed-template.rss").read_bytes(), "application/rss+xml"), r)
    assert got == [] and any("template" in w for w, _ in r.rejects)


def test_comment_and_foreign_feeds_are_not_read():
    r = run()
    home = page("https://firma.no/", feeds=["https://firma.no/comments/feed/", "https://firma.no/feed/",
                                            "https://medium.com/feed/@firma", "https://firma.no/category/nyheter/feed/"])
    assert news.feed_urls(site(home), r) == ["https://firma.no/feed/", "https://firma.no/category/nyheter/feed/"]


# --- article pages -------------------------------------------------------------------------------------------------

def art(name, url="https://firma.no/nyheter/sak/"):
    r = run()
    body = (FX / name).read_bytes()
    return news.article_from_html(body.decode("utf-8"), fetched(url, body), r), r


def test_article_jsonld_date_published_not_modified():
    it, _ = art("article-jsonld.html")
    assert (it.title, it.published) == ("Ny kontrakt med Statens vegvesen på E39", "2026-10-14")
    assert it.evidence.extraction_method == "article_jsonld_datePublished"
    assert it.evidence.claim_span == "Ny kontrakt med Statens vegvesen på E39 · 2026-10-14T08:00:00+02:00"


def test_article_meta_published_time():
    it, _ = art("article-meta.html")
    assert (it.title, it.published) == ("Vi ansetter ny prosjektleder i Bergen", "2026-09-02")


def test_article_time_beside_headline_not_the_page_clock():
    it, _ = art("article-time.html")
    assert (it.title, it.published) == ("Firma AS fyller 30 år i år", "2026-01-15")


def test_article_header_text_date_skips_updated():
    it, _ = art("article-text.html")
    assert (it.title, it.published) == ("Firma AS vant anbudet på Lade skole", "2026-03-03")
    assert it.evidence.claim_span == "Firma AS vant anbudet på Lade skole · 3. mars 2026"


def test_article_rejects():
    for name, why in [("article-updated-only.html", "no publish date on the article"),
                      ("article-nodate.html", "no publish date on the article"),   # a URL with "news" is not enough
                      ("product.html", "product page"),
                      ("article-clock.html", "today's date beside the headline (a page clock, not a publish date)")]:
        it, r = art(name)
        assert it is None, name
        assert r.rejects and r.rejects[-1][0] == why, (name, r.rejects)


def test_url_rules():
    bad = ["https://firma.no/kontakt/", "https://firma.no/om-oss/historie", "https://firma.no/tjenester/elektro",
           "https://firma.no/produkter/x200", "https://firma.no/nyheter/kategori/prosjekter/", "https://firma.no/blog/tag/bygg/",
           "https://firma.no/blog/author/ola/", "https://firma.no/nyheter/page/2/", "https://firma.no/nyheter/2/",
           "https://firma.no/nyheter/?page=3", "https://firma.no/hei-verden/", "https://firma.no/"]
    assert all(news.url_rejected(u) for u in bad)
    assert not news.url_rejected("https://firma.no/nyheter/ny-kontrakt-med-statens-vegvesen/")
    assert not news.url_rejected("https://firma.no/aktuelt/123456-ny-avtale")


def test_title_rules():
    for t in ("Hello world!", "Hei verden!", "Hallo verden", "Velkommen til WordPress", "Sample Page", "Eksempelside",
              "Les mer", "Nyheter", "Kort tittel", "Alle nyheter", "Firma AS", "Elementor #1115",
              "Her kommer snart vår nettside."):
        assert news.title_rejected(t, {"firma as"}), t
    assert not news.title_rejected("Ny kontrakt med Statens vegvesen på E39")


def test_dates():
    assert news.parse_text_date("Publisert 12. mars 2024 kl 10")[0] == date(2024, 3, 12)
    assert news.parse_text_date("May 3, 2025")[0] == date(2025, 5, 3)
    assert news.parse_text_date("03.05.2025")[0] == date(2025, 5, 3)
    assert news.parse_machine_date("Tue, 08 Sep 2026 08:30:00 +0000") == date(2026, 9, 8)
    assert not news.date_ok(date(2009, 12, 31)) and not news.date_ok(date(2026, 11, 14)) and news.date_ok(TODAY)


# --- listing end to end -----------------------------------------------------------------------------------------------

def listing_client():
    return FakeClient({
        "https://firma.no/nyheter/ny-kontrakt": ("article-jsonld.html", "text/html"),
        "https://firma.no/nyheter/vi-ansetter": ("article-meta.html", "text/html"),
        "https://firma.no/nyheter/firma-fyller": ("article-time.html", "text/html"),
        "https://firma.no/nyheter/vant-anbud": ("article-text.html", "text/html"),
        "https://firma.no/nyheter/gratulerer": ("article-clock.html", "text/html"),
        "https://firma.no/nyheter/": ("listing.html", "text/html"),
    })


def test_listing_articles_and_confirmed_listing_dates():
    client = listing_client()
    home = page("https://firma.no/", links=[("https://firma.no/nyheter/", "Nyheter"), ("https://firma.no/kontakt/", "Kontakt")])
    p, trace = go(client, site(home))
    got = {c.value["url"]: (c.value["title"], c.effective_date, c.value["source"], c.evidence[0].extraction_method) for c in items(p)}
    assert got == {
        "https://firma.no/nyheter/ny-kontrakt-med-statens-vegvesen/": ("Ny kontrakt med Statens vegvesen på E39", "2026-10-14", "company website", "article_jsonld_datePublished"),
        "https://firma.no/nyheter/vi-ansetter-prosjektleder/": ("Vi ansetter ny prosjektleder i Bergen", "2026-09-02", "company website", "article_meta_published_time"),
        "https://firma.no/nyheter/firma-fyller-30-ar/": ("Firma AS fyller 30 år i år", "2026-01-15", "company website", "article_time_element"),
        "https://firma.no/nyheter/vant-anbud-lade-skole/": ("Firma AS vant anbudet på Lade skole", "2026-03-03", "company website", "article_header_date"),
        # not opened (four articles per site), but its listing date is trusted: the opened articles agree with theirs
        "https://firma.no/nyheter/gratulerer-til-ola/": ("Gratulerer til Ola med fagbrevet", "2026-02-20", "company website", "news_listing_date"),
    }
    assert not any("andrefirma" in u or "kategori" in u or u.endswith("/2/") for u in got)
    sec = [c for c in p.claims if c.field == "news_page"]
    assert len(sec) == 1 and sec[0].value["url"] == "https://firma.no/nyheter/" and sec[0].value["title"] == "Nyheter | Firma AS"
    assert sec[0].evidence[0].claim_span == "Ny kontrakt med Statens vegvesen på E39"
    assert trace["news"][0]["requests"] == 5  # the listing and four articles
    assert len(client.calls) == 5
    # newest first
    assert [c.effective_date for c in items(p)] == sorted((c.effective_date for c in items(p)), reverse=True)


def test_listing_dates_alone_are_not_trusted():
    # every article page is unreachable: the listing's dates are never confirmed, nothing is published
    client = FakeClient({"https://firma.no/nyheter/": ("listing.html", "text/html")})
    home = page("https://firma.no/", links=[("https://firma.no/nyheter/", "Nyheter")])
    p, trace = go(client, site(home))
    assert items(p) == [] and not [c for c in p.claims if c.field == "news_page"]


def test_foreign_host_and_unverified_sites_publish_nothing():
    client = listing_client()
    home = page("https://firma.no/", links=[("https://firma.no/nyheter/", "Nyheter")])
    res = site(home)
    res.foreign_host = True
    p, _ = go(client, res)
    assert items(p) == [] and client.calls == []
    res = site(home)
    res.status = "ambiguous"
    p, _ = go(client, res)
    assert items(p) == [] and client.calls == []


def test_cap_and_dedupe_across_sites():
    client = listing_client()
    home = page("https://firma.no/", links=[("https://firma.no/nyheter/", "Nyheter")])
    p, _ = go(client, site(home))
    n = len(items(p))
    go(listing_client(), site(home), p)  # the same site again (a second verified domain with the same articles)
    assert len(items(p)) == n
    assert len([c for c in p.claims if c.field == "news_page"]) == 1


def test_title_without_the_site_name():
    names = {"firma as", "austin lyngmyr & co advokatfirma", "tempolex"}
    assert news.clean_title("Nattestøy fra naboen var en mangel - Austin Lyngmyr & Co Advokatfirma", names) == \
        "Nattestøy fra naboen var en mangel"
    assert news.clean_title("Tempolex - Feide-pålogging uke 10, 2020", names) == "Feide-pålogging uke 10, 2020"
    assert news.clean_title("NC2 Marås - Ulrik superhappy med nye biler", names) == "NC2 Marås - Ulrik superhappy med nye biler"
    assert news.clean_title("Firma AS | Kort", names) == "Firma AS | Kort"  # nothing left worth calling a headline


def test_template_and_malformed_urls():
    assert news.url_rejected("https://tempolex.no/info/nyheter/item/28-sample-items-on-nyheter") == "default post"
    assert news.url_rejected("https://www.patentprodukter.no/%20agtos%20slyng%20rens") == "malformed link"
    assert news.title_rejected("Blog Post Title One") == "default post"


def test_article_links_from_home_and_post_folders():
    r = run()
    home = page("https://firma.no/", links=[
        ("https://firma.no/aktuelt/arsrapporten-for-2025-er-klar", "17.06.2026Årsrapporten for 2025 er klar"),
        ("https://firma.no/aktuelt/arkiv", "Arkiv"),                       # another section page, not an article
        ("https://firma.no/blog-posts/hvordan-hjelpe-merkevaren", "Hvordan hjelpe merkevaren"),  # a post folder only counts on a listing
        ("https://firma.no/prosjekter/kvalavag/nyheter/drommehus", "Drømmehus i Kvalavåg"),
        ("https://firma.no/tjenester/elektro", "Elektro")])
    assert [u for u, _ in news.article_links(home, r, listing=False)] == [
        "https://firma.no/aktuelt/arsrapporten-for-2025-er-klar", "https://firma.no/prosjekter/kvalavag/nyheter/drommehus"]
    listing = page("https://firma.no/blog", links=[("https://firma.no/blog-posts/hvordan-hjelpe-merkevaren", "Hvordan hjelpe merkevaren"),
                                                   ("https://firma.no/blog/category/te", "Te"),
                                                   ("https://firma.no/om-oss", "Om oss")])
    assert [u for u, _ in news.article_links(listing, r)] == ["https://firma.no/blog-posts/hvordan-hjelpe-merkevaren"]


def test_home_linked_articles_are_opened():
    client = FakeClient({"https://firma.no/aktuelt/ny-kontrakt": ("article-jsonld.html", "text/html")})
    home = page("https://firma.no/", links=[("https://firma.no/aktuelt/ny-kontrakt", "14.10.2026 Ny kontrakt med Statens vegvesen")])
    p, trace = go(client, site(home))
    assert [(c.value["title"], c.effective_date) for c in items(p)] == [("Ny kontrakt med Statens vegvesen på E39", "2026-10-14")]


def test_feed_links_lose_campaign_parameters():
    assert news.untrack("https://firma.no/blogpost/cv/?utm_source=rss&utm_medium=rss") == "https://firma.no/blogpost/cv/"
    assert news.untrack("https://firma.no/?p=12&utm_source=rss") == "https://firma.no/?p=12"
