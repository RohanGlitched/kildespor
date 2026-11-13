# Output schema

`envelopes.jsonl` holds exactly one JSON object per input organisation number, in input order.

```jsonc
{
  "organisation_number": "918468919",
  "status": "available",                 // "failed" only when the register itself cannot anchor the entity
  "legal_name": "NILLE AS",
  "run": {"run_id": "…", "started_at": "…Z", "completed_at": "…Z", "terminal_status": "completed"},
  "summary": {
    // the one fact a buyer would want first, with its source in brackets
    "headline": "Hiring now: 3 open positions (“Butikkmedarbeider”; “Lagermedarbeider”), latest posted 2026-11-02 (NAV job board).",
    // a short brief: the lead fact, what the company does, how it is doing, what changed, what is still unknown;
    // every sentence names its source in brackets
    "text": "Hiring now: … (NAV job board). A large operating business in retail sale … Its own website (nille.no) says: “…”. …",
    "lead_fact": {"text": "…", "claim_keys": ["jobs:job_posting:…"], "sources": [{"name": "NAV job board", "url": "https://…"}]},
    "what_it_does": "…", "what_changed": "In the last 12 months: new general manager registered (2026-09-01).",
    "sentences": [{"topic": "financials", "text": "Latest filed accounts (2025): revenue NOK 1.8 bn (+6% on 2024) …",
                   "claim_keys": ["financials:revenue:2025:SELSKAP", "…"],
                   "sources": [{"name": "Brønnøysund annual accounts", "url": "https://data.brreg.no/regnskapsregisteret/…"}]}],
    "unknowns": ["contact"],
    "unknowns_explained": [{"family": "reviews", "state": "not_available", "text": "no customer rating was found"}]
  },
  "sections": {                          // the seven required sections, each with a state
    "legal_identity_and_brand":   {"state": "available", "families": ["identity", "description"], "claim_keys": ["…"]},
    "annual_accounts":            {"state": "available", "families": ["financials"]},
    "leadership_and_workplaces":  {"state": "available", "families": ["people", "locations"]},
    "website_and_profiles":       {"state": "available", "families": ["website", "social", "contact"]},
    "hiring_and_activity":        {"state": "available", "families": ["jobs", "activity"]},
    "evidence_and_availability":  {"state": "available", "claims": 412, "evidence_records": 380},
    "refresh":                    {"state": "available", "previous_run_id": "…", "changes": 3}
  },
  "field_states": [                      // one per field family, always present
    {"family": "website", "state": "available", "claims": 1, "checked_sources": ["…"]},
    {"family": "contact", "state": "not_available", "note": "Checked; nothing found for this entity", "checked_sources": ["…"]}
  ],
  "claims": [{
    "key": "jobs:job_posting:nav:…",     // stable across runs; used for refresh diffs
    "family": "jobs", "field": "job_posting", "label": "Job posting (NAV)",
    "value": {"title": "…", "uuid": "…", "url": "https://arbeidsplassen.nav.no/stillinger/stilling/…", "status": "open",
              "employer_orgnr": "…", "published": "2026-10-13", "expires": "…"},
    "availability": "available", "confidence": 0.99,
    "relationship": "registered_subunit", // exact | registered_subunit | group_member
    "effective_date": "2026-10-13",       // date the fact refers to
    "reporting_period": null,             // accounting period for financial values
    "evidence_ids": ["ev-…"],
    "first_observed": "…Z", "last_observed": "…Z",
    "carried_forward": false              // true when kept from the previous run because the source failed
  }],
  "evidence": [{
    "id": "ev-…",
    "source_url": "https://pam-stilling-feed.nav.no/api/v1/feedentry/…",
    "source_name": "NAV arbeidsplassen",
    "source_class": "public_job_board",   // official_registry | company_owned | public_job_board | open_knowledge_base
    "retrieved_at": "…Z",
    "content_sha256": "…",                // hash of the exact bytes fetched
    "claim_span": "employer.orgnr 973… · … · published 2026-10-13 · status ACTIVE",
    "extraction_method": "nav_feed_employer_orgnr",
    "http_status": 200
  }],
  "changes": [{"type": "new_role", "change": "added", "family": "people", "materiality": "high",
               "current": {"name": "…", "role": "Daglig leder"}, "current_evidence": ["…"]}],
  "refresh": {"previous_run_id": "…", "previous_completed_at": "…", "carried_forward": 0},
  "errors": [{"source": "website_feed", "message": "…"}],
  "operations": {"requests": 14, "runtime_ms": 8120, "third_party_cost_usd": 0.0}
}
```

## Field families

| Family | Typical fields |
|---|---|
| `identity` | legal name, form, NACE codes, addresses, founded, registered employees, share capital, flags, former names, public brand, Wikidata item |
| `financials` | revenue, operating result, result before tax, annual result, payroll, assets, equity, debt, cash: one claim per figure per year |
| `people` | every active registered role (person or organisation) with its role code |
| `locations` | registered workplaces (subunits) with address and employees, addresses printed on the verified site, opening hours |
| `website` | the verified official website with its proofs |
| `contact` | registered phone, mobile and e-mail; e-mail and phone on the verified site |
| `social` | company-owned profiles (Facebook, Instagram, LinkedIn, YouTube, X, TikTok, …) |
| `jobs` | job postings (NAV, site JobPosting, postings on recruitment platforms the verified site links: Teamtailor, Recman, ReachMee, Jobylon, Jobbnorge, Easycruit, …), careers pages, linked recruitment platforms |
| `activity` | dated items: `company_news` (a real, dated article on the verified site: `{title, url, published, source}`, from the site's WordPress API, RSS/Atom feed or article pages; the publish date, never an "updated" date; default "Hello world" posts, product, contact and category pages are rejected), `news_page` (the site's news section, when it links an article we published), register events, public contract awards, state aid, food inspections |
| `description` | the registered purpose, the site's own description |

## States

`available`, `not_available` (checked, nothing there), `blocked` (the source refused: robots.txt or
HTTP 401/403), `not_applicable`, `ambiguous` (candidates found, none proven to be this entity),
`failed` (the source broke this run). A missing value is never written as zero.
