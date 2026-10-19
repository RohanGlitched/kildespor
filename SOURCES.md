# Sources, rights and access

Every source is keyless or uses a token its owner publishes for public use. No personal account,
no paid API, no search-engine scraping, no social-platform scraping. Third-party cost per run: $0.

| Source | What we take | Access | Rights and terms | Join key |
|---|---|---|---|---|
| Brønnøysundregistrene, Enhetsregisteret API | entity, contact fields, roles, subunits | `data.brreg.no/enhetsregisteret/api/…` | open data, [NLOD 2.0](https://data.norge.no/nlod/en/2.0) | organisation number |
| Brønnøysundregistrene, Regnskapsregisteret API | filed annual accounts (all years the API returns) | `data.brreg.no/regnskapsregisteret/regnskap/{orgnr}` | NLOD 2.0 | organisation number |
| The company's own website | identity proof, contact, profiles, addresses, description, careers, news | home page + up to 8 priority pages + its RSS/Atom feed | robots.txt obeyed for our user agent; one request at a time per site | site must prove the organisation number (IDENTITY_RESOLUTION.md) |
| NAV Job Vacancy Feed | job ads with employer organisation number | `pam-stilling-feed.nav.no`, public token fetched at run time from NAV's `/api/publicToken` | free for anyone under [NAV's terms](https://navikt.github.io/pam-stilling-feed/); we publish only the ad's title, dates, place and link, no contact persons | `employer.orgnr` = ours or a registered subunit's |
| Recruitment platforms the verified site links or embeds | open job postings: title, link, posting date, deadline, place | see the next table; at most 3 platform accounts, 8 single-ad pages and 20 postings per company, 6 s of fetching per company | public pages and feeds the platform serves to every visitor; robots.txt obeyed; no contact persons or ad text kept | the link or embed is on the verified site **and** the employer (or account) name is the legal name |
| SSB Klass (Statistics Norway classification API) | English names of the industry codes, for the plain-English profile line | `data.ssb.no/api/klass/v1/classifications/6/codes`, one request per run | open data, NLOD 2.0 | industry code |
| Wikidata SPARQL | website, social IDs, inception, listing, HQ | `query.wikidata.org`, one POST query per 1,200 companies | CC0 | P2333 (Norwegian organisation number) |
| Brønnøysundregistrene, Regnskapsregisteret copies | the list of filed annual-account PDFs by year | `…/regnskap/aarsregnskap/kopi/{orgnr}/aar` (≈30 calls per few minutes; we pause on 429 instead of retrying) | NLOD 2.0 | organisation number |
| Brønnøysundregistrene, update log | dated register updates for the entity | `…/enhetsregisteret/api/oppdateringer/enheter?organisasjonsnummer=` | NLOD 2.0 | organisation number |
| Støtteregisteret (Brreg) | state-aid awards received | `stottetiltak-registerinfo-api.app.brreg.no/api/v1/soek/stoettetildeling` | NLOD 2.0 | recipient organisation number, checked again on every row |
| Mattilsynet | food-safety inspections and grades | one CSV per run, `matnyttig.mattilsynet.no/smilefjes/tilsyn.csv` | NLOD | organisation number of the company or a registered workplace |
| TED (EU Publications Office) | public-contract award notices won | `api.ted.europa.eu/v3/notices/search`, one query per 100 companies | EU open data | winner identifier = organisation number |
| Finanstilsynet | supervision record, LEI, licences | `api.finanstilsynet.no/registry/v2/…` | public API | register's organisation number must equal ours |
| Arbeidstilsynet | approval in the cleaning and occupational-health registers | one XML per register per run, `registerdata.arbeidstilsynet.no` | public data | organisation number |
| Fagfolkguiden | the Google aggregate rating a tradesperson-directory page displays (no review text) | `www.fagfolkguiden.no/bedrift/{slug}-{orgnr}`; robots.txt allows `/bedrift/` | public page | JSON-LD `identifier` = organisation number |
| DNS | which name-derived domains exist | public resolvers via dnspython | n/a | candidate generation only, never evidence |

## Recruitment platforms (`kildespor/sources/careers.py`)

Found from the verified site only: links on any crawled page, the raw HTML of the site's careers page
(iframes and widget scripts are not links), a career subdomain (`karriere.firma.no`), and one hop from
the careers page to its vacancy list. Each platform is read the way its own public page reads itself.

| Platform | What we read | robots.txt / terms |
|---|---|---|
| Teamtailor (`*.teamtailor.com` and custom career domains) | the account's public `/jobs.rss` (title, date, places, country) | allowed; only `/app/`, `/messages/`, `/jobs/internal/` are disallowed |
| Recman (`*.recman.page`, `*.recman.io`) | the account's `/jobs` page, then the JSON list that page loads (`/api/jobs`, with the page's own CSRF token); employer named per posting | allowed (`/profile/`, `/employee/`, `/sys/`, `/drive/` are disallowed) |
| ReachMee (`web1xx.reachmee.com`) | the vacancy list the customer's iframe or `customerjs` script points at (HTML table: title, place, deadline) | the hosts serve no robots.txt |
| Jobylon | the company embed list `cdn.jobylon.com/jobs/companies/{id}/embed/v2/` (employer per posting), or JobPosting JSON-LD on linked `emp.jobylon.com/jobs/…` ads | allowed for general crawlers (named job-aggregator bots are disallowed); `static-eu.jobylon.com` is never fetched (its robots.txt is 403) |
| Jobbnorge | its Public API `publicapi.jobbnorge.no/v3/Jobs` (one request per run), filtered to the employer whose ads the site links | no robots.txt; published as a public API; `/ledige-stillinger/joblisting/pdf/` on the main site is disallowed and never fetched |
| Easycruit (`*.easycruit.com`) | the public XML export `/export/xml/vacancy/list.xml` (employer per vacancy) | allowed (`/intranet/` disallowed) |
| Mojob *(parser kept, switched off)* | JobPosting JSON-LD on each linked `jobs.mojob.io/{id}/` ad | allowed |
| Lever / Greenhouse / Recruitee *(parsers kept, switched off)* | `api.lever.co/v0/postings/{account}`, `boards-api.greenhouse.io/v1/boards/{token}/jobs`, `{account}.recruitee.com/api/offers/` — documented public job-board APIs; Lever and Greenhouse postings kept only in Norwegian locations | allowed (Greenhouse disallows `/embed/`, which we do not use) |
| The company's own careers page | JobPosting JSON-LD; plain ads one level under the careers page that read like an ad (deadline, "stillingsprosent", "how to apply"), name the company, and name no other employer or organisation number | the company site's own robots.txt |

Switched off until a real Norwegian company's postings through them have been hand-checked (the parsers
are tested on saved responses and turned on by adding the platform to `ENABLED` in `careers.py`): Mojob,
Lever, Greenhouse, Recruitee. Fetching stops after 6 s per company (5 s per request); what was read by
then is kept.

Not read, on purpose: **Webcruiter** (robots.txt disallows every path for general crawlers),
**HR-manager / Talentech** (robots.txt allows only application forms; its file starts with a byte-order mark,
which Python's robots parser would otherwise misread as "allow all", so the client now strips it),
**FINN.no** (terms forbid automated use), **Workday** (group tenants list many employers without naming
the employer per posting), **SmartRecruiters** (its posting API is disallowed in robots.txt). Links to
them are counted in the run report (`careers.not_read`).

## Crawler behaviour

- User agent `KildesporBot/1.0 (+https://github.com/RohanGlitched/kildespor; …)`.
- robots.txt is fetched once per host and obeyed; a 401/403 robots file is treated as "disallow all".
- One request at a time per company host, 96 requests in flight overall. Public APIs get their own
  limits, set from measurement rather than guesswork: Brønnøysund 16 (its throughput peaks at about
  33 requests a second; more parallel requests only add latency), NAV 16, Støtteregisteret 8,
  Finanstilsynet 6, Fagfolkguiden 6, TED 2, Wikidata 2. HTTP 429 is answered with backoff
  (Retry-After honoured), and the account-copies endpoint is paused for three minutes after a 429.
- Sources that do not feed website discovery run after a company's research slot is released, so the
  slow run-wide index (NAV) never holds up the crawl.
- DNS: configured nameservers that do not answer are dropped at start-up, public resolvers (1.1.1.1,
  8.8.8.8, 9.9.9.9) are kept as a fallback, a timeout is never recorded as "domain does not exist", and
  if the operating system's resolver cannot answer for a host the public resolvers are asked before
  giving up.
- Only `http`/`https`; hosts resolving to private, loopback, link-local or reserved addresses are
  refused; at most 5 redirects; bodies capped at 3 MB; 10 s read and 5 s connect timeouts, 60 s per candidate site.
- Raw responses are stored in `snapshots.zip` next to the output, one entry per SHA-256, so every
  evidence hash can be checked against the bytes we saw.

## Not used, on purpose

- LinkedIn, Facebook, Instagram, Glassdoor, Indeed: their terms restrict automated collection. We
  publish a profile URL only when the company's own site links to it (or Wikidata lists it), and we
  never fetch the profile.
- Brønnøysund announcements (`w2.brreg.no/kunngjoring`), YouTube feeds, Google News RSS and eInnsyn: their
  robots.txt or terms forbid this use. Dated events are rebuilt from fields the register already publishes.
- Search engines (Google, Bing, DuckDuckGo result pages). An optional search-provider connector can
  be added if Builderr supplies a licensed key, but the official run does not need one.
- Directories (Proff, Purehelp, Gulesider): we prefer primary sources and do not rely on their terms.
