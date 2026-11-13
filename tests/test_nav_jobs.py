"""NAV job feed: the index order, open/closed rules, the employer-orgnr match and literal evidence. No network."""
import asyncio
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from kildespor.claims import Profile
from kildespor.sources import nav_jobs as nj

FX = Path(__file__).parent / "fixtures" / "nav"
UUID = "ffb6925a-e81b-4745-b241-1c805f0e425f"
ORG = "915069614"  # Retyre AS


class F:  # a stand-in for http.Fetched
    def __init__(self, url, body=b"", status=200, ctype="application/json"):
        self.url = self.final_url = url
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.status = status
        self.content_type = ctype
        self.retrieved_at = "2026-11-13T00:00:00Z"
        self.sha256 = hashlib.sha256(self.body).hexdigest()
        self.error = self.blocked = ""

    @property
    def ok(self):
        return 200 <= self.status < 300

    def text(self):
        return self.body.decode("utf-8")


class Client:
    def __init__(self, details: dict[str, dict], pages: dict[str, str] | None = None):
        self.details, self.pages, self.calls, self.saved = details, pages or {}, [], []

    async def get(self, source, url, **kw):
        self.calls.append(url)
        if "/feedentry/" in url:
            u = url.rsplit("/", 1)[1]
            return F(url, json.dumps(self.details[u], separators=(",", ":"))) if u in self.details else F(url, b"", 404)
        if url in self.pages:
            return F(url, self.pages[url], ctype="text/html; charset=utf-8")
        return F(url, b"", 404)

    def save_snapshot(self, f):
        self.saved.append(f.url)


class Ctx:
    def __init__(self, client):
        self.client = client
        self.sources = []


def _detail(uuid=UUID, org=ORG, title=None, due="2027-05-12", status="ACTIVE", expires="2027-05-12T00:00:00+02:00"):
    d = json.loads((FX / "feedentry.json").read_text(encoding="utf-8"))
    d = copy.deepcopy(d)
    d["uuid"] = d["ad_content"]["uuid"] = uuid
    d["status"] = status
    d["ad_content"]["employer"]["orgnr"] = org
    d["ad_content"]["applicationDue"] = due
    d["ad_content"]["expires"] = expires
    if title:
        d["ad_content"]["title"] = title
    return d


def test_if_modified_since_uses_english_weekday_in_gmt():
    assert nj.if_modified_since(datetime(2026, 11, 13, 1, 2, 3, tzinfo=timezone.utc)) == "Fri, 13 Nov 2026 01:02:03 GMT"


def test_index_reads_company_ads_before_public_bodies():
    ads = {"a": {"status": "ACTIVE", "businessName": "Bergen kommune Årstad sykehjem"},
           "b": {"status": "ACTIVE", "businessName": "KIWI Fredensborg"},
           "c": {"status": "INACTIVE", "businessName": "Retyre AS"},
           "d": {"status": "ACTIVE", "businessName": "Helse Førde HF"},
           "e": {"status": "ACTIVE", "businessName": "Signo grunn- og videregående skole AS"}}
    assert nj.index_order(ads) == ["b", "e", "a", "d"]  # only ACTIVE ads; a name with a company form is a company


def test_due_dates_and_open_state():
    assert nj.parse_due("2026-11-15") == "2026-11-15"
    assert nj.parse_due("15.11.2026") == "2026-11-15"
    assert nj.parse_due("2026-10-20T00:00:00") == "2026-10-20"
    assert nj.parse_due("Snarest") is None
    today = "2026-11-13"
    assert nj.ad_state(_detail(), "ACTIVE", today) == "open"
    assert nj.ad_state(_detail(due="Snarest"), "ACTIVE", today) == "open"
    # NAV keeps the ad ACTIVE until it expires, but the application deadline has passed: not an open posting
    assert nj.ad_state(_detail(due="2026-10-20T00:00:00"), "ACTIVE", today) == "deadline_passed"
    assert nj.ad_state(_detail(status="INACTIVE"), "INACTIVE", today) == "inactive"
    assert nj.ad_state(_detail(due=None, expires="2026-11-01T00:00:00+01:00"), "ACTIVE", today) == "expired"
    # KALLAND BLØ AS: 'Åpen søknad for Rema 1000 Brattvåg' is a standing open application, not a posting
    assert nj.ad_state(_detail(title="Åpen søknad for Rema 1000 Brattvåg", due="2027-03-31"), "ACTIVE", today) == "open_application"
    assert nj.ad_state(_detail(due="2028-06-01", expires="2028-06-01T00:00:00+02:00"), "ACTIVE", today) == "evergreen"


def test_public_body_shown_on_a_company_workplace_ad_is_not_the_companys():
    # an ad filed under a TINE SA workplace whose page shows 'Statsforvaltaren i Vestland'
    w = nj.DisplayedEmployer({"navn": "TINE SA"}, [], "947942638", ["tine"])
    assert w.other("Statsforvaltaren i Vestland")
    assert not w.other("TINE Byrkjelo")


def test_public_page_facts_take_the_ad_not_the_similar_ads():
    facts = nj.public_page_facts((FX / "stilling.html").read_text(encoding="utf-8"))
    assert facts["title"] == "Senior Industrialization Engineer"
    assert facts["employer"] == "Retyre AS"  # the page also lists a similar ad by Norrøna Sport AS further down
    assert facts["deadline_line"].startswith("Søk senest")


def test_feed_span_quotes_the_feed_entry_literally():
    raw = (FX / "feedentry.json").read_text(encoding="utf-8")
    span = nj.feed_span(raw, UUID, "Senior Industrialization Engineer", ORG)
    pieces = span.split(" · ")
    assert len(pieces) == 3 and all(x in raw for x in pieces)
    assert f'"orgnr":"{ORG}"' in pieces[0] and pieces[2] == '"status":"ACTIVE"'


def test_short_names_match_only_the_whole_employer_name():
    nav = nj.NavJobs()
    nav.ads = {"1": {"businessName": "SFE AS", "status": "ACTIVE"}, "2": {"businessName": "SFE Nett AS", "status": "ACTIVE"},
               "3": {"businessName": "Retyre AS", "status": "ACTIVE"}}
    for u, e in nav.ads.items():
        for t in set(nj._sig(e["businessName"])):
            nav.by_token.setdefault(t, []).append(u)
    assert nav._candidates([nj._sig("SFE AS")]) == ["1"]
    assert nav._candidates([nj._sig("RETYRE AS")]) == ["3"]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_index_then_enrich_publishes_only_open_ads_of_this_orgnr(monkeypatch):
    monkeypatch.setattr(nj, "_today", lambda: "2026-11-13")
    details = {UUID: _detail(),
               "u-brand": _detail("u-brand", title="Operatør"),                       # posted under a brand name
               "u-late": _detail("u-late", title="Gammel annonse", due="2026-10-01"),  # deadline passed
               "u-other": _detail("u-other", org="810034882", title="Annen bedrift"),   # another employer, same name
               "u-pub": _detail("u-pub", org="964338531", title="Sykepleier")}
    ads = {UUID: {"status": "ACTIVE", "businessName": "Retyre AS", "title": "Senior Industrialization Engineer"},
           "u-brand": {"status": "ACTIVE", "businessName": "reTyre Ski", "title": "Operatør"},
           "u-late": {"status": "ACTIVE", "businessName": "Retyre AS", "title": "Gammel annonse"},
           "u-other": {"status": "ACTIVE", "businessName": "Retyre AS", "title": "Annen bedrift"},
           "u-pub": {"status": "ACTIVE", "businessName": "Bergen kommune", "title": "Sykepleier"}}
    page = (FX / "stilling.html").read_text(encoding="utf-8")
    client = Client(details, {nj.PUBLIC.format(UUID): page})
    ctx = Ctx(client)
    nav = nj.NavJobs()

    async def go():
        nav.ads = ads
        for u, e in ads.items():
            for t in set(nj._sig(e["businessName"])):
                nav.by_token.setdefault(t, []).append(u)
        nav.total_companies = 1
        await nav._index(ctx)
        assert nav.index_complete and nav.index_done.is_set()
        assert client.calls[-1].endswith("/u-pub")  # the public body's ad was read last
        p = Profile(ORG)
        ent = {"navn": "RETYRE AS", "organisasjonsnummer": ORG}
        await nav.enrich(ctx, p, ent, [], [])
        return p
    p = _run(go())
    jobs = [c for c in p.claims if c.field == "job_posting"]
    titles = sorted(c.value["title"] for c in jobs)
    assert titles == ["Operatør", "Senior Industrialization Engineer"]
    assert nav.skipped == {"deadline_passed": 1}
    main = next(c for c in jobs if c.value["title"].startswith("Senior"))
    v = main.value
    assert v["url"] == f"https://arbeidsplassen.nav.no/stillinger/stilling/{UUID}" and v["status"] == "open"
    assert v["deadline"] == "2027-05-12" and v["posted"] == "2026-11-05" and v["source"] == "NAV arbeidsplassen"
    assert main.relationship == "exact"
    # the first evidence is the public ad page, quoted literally
    ev = main.evidence[0]
    assert ev.source_url == v["url"] and ev.extraction_method == "nav_public_ad_page"
    assert ev.claim_span.startswith("Senior Industrialization Engineer · Retyre AS · Søk senest")
    assert main.evidence[1].extraction_method == "nav_feed_employer_orgnr" and f'"orgnr":"{ORG}"' in main.evidence[1].claim_span
    # the brand ad had no public page in this test: it keeps the feed evidence only
    brand = next(c for c in jobs if c.value["title"] == "Operatør")
    assert [e.extraction_method for e in brand.evidence] == ["nav_feed_employer_orgnr"]
    assert p.notes["nav_homepages"]  # the ad's homepage is kept as a discovery hint only


def test_subunit_ads_are_registered_subunit_claims(monkeypatch):
    monkeypatch.setattr(nj, "_today", lambda: "2026-11-13")
    details = {UUID: _detail(org="999999999")}
    ads = {UUID: {"status": "ACTIVE", "businessName": "Retyre Ski", "title": "x"}}
    client = Client(details)
    ctx = Ctx(client)
    nav = nj.NavJobs()

    async def go():
        nav.ads = ads
        await nav._index(ctx)
        p = Profile(ORG)
        await nav.enrich(ctx, p, {"navn": "RETYRE AS"}, [{"organisation_number": "999999999", "name": "RETYRE SKI"}], [])
        return p
    p = _run(go())
    jobs = [c for c in p.claims if c.field == "job_posting"]
    assert len(jobs) == 1 and jobs[0].relationship == "registered_subunit"


def test_index_stops_at_the_soft_cap_once_research_is_over(monkeypatch):
    monkeypatch.setattr(nj, "INDEX_SOFT_SECONDS", 0.0)
    monkeypatch.setattr(nj, "INDEX_WORKERS", 1)

    class Slow(Client):
        async def get(self, source, url, **kw):
            await asyncio.sleep(0.3)
            return await super().get(source, url, **kw)
    ads = {f"u{i}": {"status": "ACTIVE", "businessName": f"Firma {i} AS"} for i in range(50)}
    client = Slow({u: _detail(u) for u in ads})
    nav = nj.NavJobs()

    async def go():
        nav.ads = ads
        nav.total_companies = 1
        nav.research_done()  # the only company has finished its research
        await asyncio.wait_for(nav._index(Ctx(client)), timeout=10)
    _run(go())
    assert not nav.index_complete and nav.index_done.is_set() and len(client.calls) < 10


def test_ads_shown_for_another_employer_are_not_this_companys_postings(monkeypatch):
    # Job Norway registers the ad under its own orgnr, but the public page shows 'Arbeidsgiver Stotvig Hotel AS'
    monkeypatch.setattr(nj, "_today", lambda: "2026-11-13")
    ads = {"u1": {"status": "ACTIVE", "businessName": "Stotvig Hotel AS", "title": "Spa Therapist"},
           "u2": {"status": "ACTIVE", "businessName": "Anonym arbeidsgiver", "title": "Selger"},
           "u3": {"status": "ACTIVE", "businessName": "Job Norway", "title": "Kokk"}}
    client = Client({u: _detail(u, org="992399473", title=a["title"]) for u, a in ads.items()})
    nav = nj.NavJobs()

    async def go():
        nav.ads = ads
        await nav._index(Ctx(client))
        p = Profile("992353171")
        await nav.enrich(Ctx(client), p, {"navn": "JOB NORWAY NUF"}, [{"organisation_number": "992399473", "name": "JOB NORWAY"}], [])
        return p
    p = _run(go())
    assert [c.value["title"] for c in p.claims if c.field == "job_posting"] == ["Kokk"]
    assert nav.skipped["shown_for_another_employer"] == 2
    w = nj.DisplayedEmployer({"navn": "NG KIWI OSLO AKERSHUS AS"}, [], "1", [])
    assert not w.other("KIWI Fredensborg")  # a store name without a legal form: the orgnr decides
    g = nj.DisplayedEmployer({"navn": "GRAND HOTEL ARENDAL DRIFT AS"}, [], "1", [])
    assert not g.other("Grand Hotel Arendal AS")  # the same family of names
    assert nj.DisplayedEmployer({"navn": "JOB NORWAY NUF"}, [], "1", []).other("Støtvig Hotel AS")


def test_public_page_employer_is_the_ads_not_a_similar_ads():
    html = ("<html><body><h1>Kafe og skiutleie</h1><section><div><div></div><p>Lifjell Skisenter AS</p></div>"
            "<div><div></div><p>Lifjellvegen 833, 3804 Bø</p></div></section><div><h2>Søk på jobben</h2><p>Søk snarest mulig</p></div>"
            "<h2>Lignende annonser</h2><article><div><p>Arbeidsgiver</p></div><p>JYSK AS</p></article></body></html>")
    facts = nj.public_page_facts(html)
    assert facts == {"title": "Kafe og skiutleie", "employer": "Lifjell Skisenter AS", "deadline_line": "Søk snarest mulig"}
