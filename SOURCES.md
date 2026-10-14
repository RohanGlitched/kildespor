# Sources, rights and access

Every source is keyless or uses a token its owner publishes for public use. No personal account,
no paid API, no search-engine scraping, no social-platform scraping. Third-party cost per run: $0.

| Source | What we take | Access | Rights and terms | Join key |
|---|---|---|---|---|
| Brønnøysundregistrene, Enhetsregisteret API | entity, contact fields, roles, subunits | `data.brreg.no/enhetsregisteret/api/…` | open data, [NLOD 2.0](https://data.norge.no/nlod/en/2.0) | organisation number |
| Brønnøysundregistrene, Regnskapsregisteret API | filed annual accounts (all years the API returns) | `data.brreg.no/regnskapsregisteret/regnskap/{orgnr}` | NLOD 2.0 | organisation number |
| The company's own website | identity proof, contact, profiles, addresses, description, careers, news | home page + up to 8 priority pages + its RSS/Atom feed | robots.txt obeyed for our user agent; one request at a time per site | site must prove the organisation number (IDENTITY_RESOLUTION.md) |
| NAV Job Vacancy Feed | job ads with employer organisation number | `pam-stilling-feed.nav.no`, public token fetched at run time from NAV's `/api/publicToken` | free for anyone under [NAV's terms](https://navikt.github.io/pam-stilling-feed/); we publish only the ad's title, dates, place and link, no contact persons | `employer.orgnr` = ours or a registered subunit's |
| Wikidata SPARQL | website, social IDs, inception, listing, HQ | `query.wikidata.org`, one batched query per 250 companies | CC0 | P2333 (Norwegian organisation number) |
| DNS | which name-derived domains exist | public resolvers via dnspython | n/a | candidate generation only, never evidence |

## Crawler behaviour

- User agent `KildesporBot/1.0 (+https://github.com/RohanGlitched/kildespor; …)`.
- robots.txt is fetched once per host and obeyed; a 401/403 robots file is treated as "disallow all".
- One request at a time per company host, 48 requests in flight overall; public APIs have their own
  small parallel limits (Brreg 8, NAV 12, Wikidata 2).
- Only `http`/`https`; hosts resolving to private, loopback, link-local or reserved addresses are
  refused; at most 5 redirects; bodies capped at 3 MB; 12 s timeout.
- Raw responses are stored gzip-compressed by SHA-256 in `snapshots/` next to the output, so every
  evidence hash can be checked against the bytes we saw.

## Not used, on purpose

- LinkedIn, Facebook, Instagram, Glassdoor, Indeed: their terms restrict automated collection. We
  publish a profile URL only when the company's own site links to it (or Wikidata lists it), and we
  never fetch the profile.
- Search engines (Google, Bing, DuckDuckGo result pages). An optional search-provider connector can
  be added if Builderr supplies a licensed key, but the official run does not need one.
- Directories (Proff, Purehelp, Gulesider): we prefer primary sources and do not rely on their terms.
