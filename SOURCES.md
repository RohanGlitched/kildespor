# Sources, rights and access

Every source is keyless or uses a token its owner publishes for public use. No personal account,
no paid API, no search-engine scraping, no social-platform scraping. Third-party cost per run: $0.

| Source | What we take | Access | Rights and terms | Join key |
|---|---|---|---|---|
| Brønnøysundregistrene, Enhetsregisteret API | entity, contact fields, roles, subunits | `data.brreg.no/enhetsregisteret/api/…` | open data, [NLOD 2.0](https://data.norge.no/nlod/en/2.0) | organisation number |
| Brønnøysundregistrene, Regnskapsregisteret API | filed annual accounts (all years the API returns) | `data.brreg.no/regnskapsregisteret/regnskap/{orgnr}` | NLOD 2.0 | organisation number |
| The company's own website | identity proof, contact, profiles, addresses, description, careers, news | home page + up to 8 priority pages + its RSS/Atom feed | robots.txt obeyed for our user agent; one request at a time per site | site must prove the organisation number (IDENTITY_RESOLUTION.md) |
| NAV Job Vacancy Feed | job ads with employer organisation number | `pam-stilling-feed.nav.no`, public token fetched at run time from NAV's `/api/publicToken` | free for anyone under [NAV's terms](https://navikt.github.io/pam-stilling-feed/); we publish only the ad's title, dates, place and link, no contact persons | `employer.orgnr` = ours or a registered subunit's |
| Wikidata SPARQL | website, social IDs, inception, listing, HQ | `query.wikidata.org`, one POST query per 1,200 companies | CC0 | P2333 (Norwegian organisation number) |
| Brønnøysundregistrene, Regnskapsregisteret copies | the list of filed annual-account PDFs by year | `…/regnskap/aarsregnskap/kopi/{orgnr}/aar` (≈30 calls per few minutes; we pause on 429 instead of retrying) | NLOD 2.0 | organisation number |
| Brønnøysundregistrene, update log | dated register updates for the entity | `…/enhetsregisteret/api/oppdateringer/enheter?organisasjonsnummer=` | NLOD 2.0 | organisation number |
| Støtteregisteret (Brreg) | state-aid awards received | `stottetiltak-registerinfo-api.app.brreg.no/api/v1/soek/stoettetildeling` | NLOD 2.0 | recipient organisation number, checked again on every row |
| Mattilsynet | food-safety inspections and grades | one CSV per run, `matnyttig.mattilsynet.no/smilefjes/tilsyn.csv` | NLOD | organisation number of the company or a registered workplace |
| TED (EU Publications Office) | public-contract award notices won | `api.ted.europa.eu/v3/notices/search`, one query per 100 companies | EU open data | winner identifier = organisation number |
| Finanstilsynet | supervision record, LEI, licences | `api.finanstilsynet.no/registry/v2/…` | public API | register's organisation number must equal ours |
| Arbeidstilsynet | approval in the cleaning and occupational-health registers | one XML per register per run, `registerdata.arbeidstilsynet.no` | public data | organisation number |
| DNS | which name-derived domains exist | public resolvers via dnspython | n/a | candidate generation only, never evidence |

## Crawler behaviour

- User agent `KildesporBot/1.0 (+https://github.com/RohanGlitched/kildespor; …)`.
- robots.txt is fetched once per host and obeyed; a 401/403 robots file is treated as "disallow all".
- One request at a time per company host, 48 requests in flight overall; public APIs have their own
  small parallel limits (Brreg 8, NAV 12, Finanstilsynet 6, Støtteregisteret 4, TED 2, Wikidata 2), and HTTP 429 is
  answered with backoff (Retry-After honoured).
- Only `http`/`https`; hosts resolving to private, loopback, link-local or reserved addresses are
  refused; at most 5 redirects; bodies capped at 3 MB; 10 s read and 5 s connect timeouts, 60 s per candidate site.
- Raw responses are stored gzip-compressed by SHA-256 in `snapshots/` next to the output, so every
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
