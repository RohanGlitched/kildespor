# Identity resolution

The organisation number is the only key. A website, profile or job ad is a candidate until it is
tied back to that number. It is better to miss a fact than to publish it under the wrong company.

## Website candidates

In priority order:

| Origin | Where it comes from |
|---|---|
| `registry_website` | the `hjemmeside` field the entity registered in Enhetsregisteret |
| `wikidata_website` | P856 on the Wikidata item whose P2333 equals the organisation number |
| `registry_email` | the domain of the e-mail address the entity registered (free-mail and shared platforms excluded) |
| `subunit_website`, `subunit_email` | the same fields on the entity's registered workplaces |
| `job_ad_homepage` | the employer homepage in a NAV job ad whose employer organisation number is ours |
| `name_derived` | domains built from the legal name (`.no` first, then `.com`), kept only if they resolve in DNS |

Each candidate's home page and up to eight priority pages (contact, about, privacy, careers, news,
people, locations) are fetched, obeying robots.txt.

## Publication gate

A site is published as the official website only with one of these proofs, recorded as evidence
with the page URL, retrieval time, content hash and the exact text span:

| Proof | Rule | Confidence |
|---|---|---|
| `orgnr` | the page shows our organisation number (or a registered subunit's), checksum-valid, any spacing | 1.00 |
| `phone` | a phone number registered for the entity or its workplaces appears on the site | 0.96 |
| `email` | the registered e-mail address appears on the site | 0.95 |
| `name_address` | every legal-name token **and** the registered street address **and** postcode appear on one page | 0.93 |
| `legal_name` | the exact legal name with its legal form ("Fjellform AS") appears, letters æ/ø/å and punctuation kept, on a site whose domain is derived from that name or was declared | 0.90 |
| `registry_declared` | the register's own website field, live, not parked, and not claiming another organisation number | 0.85–0.90 |

Rejections, all visible in the discovery trace:

- **other_entity**: the site prints a different organisation number next to an "org.nr"/"MVA" label
  and never ours. A shared management company, a parent or a namesake is never collapsed into
  our entity.
- **parked**: placeholder, for-sale, under-construction or empty pages.
- **ambiguous**: a live site with none of the proofs above (for example a dictionary-word domain such
  as `nordlys.no`, or `raservice.no`, which belongs to *RA Service AS* in Oslo, not *RÅ SERVICE AS* in
  Holmestrand).
- **blocked**: robots.txt disallows our user agent.

## Everything else hangs off the verified site or the organisation number

- **Social profiles**: only outbound links on the verified site, its JSON-LD `sameAs`, or Wikidata
  properties on the item that carries our organisation number.
- **Contact details**: e-mail addresses on the verified site's own domain (or the registered address),
  phone numbers printed on the verified site.
- **Job ads**: NAV records whose `employer.orgnr` is ours or one of our registered subunits'
  (subunit matches are labelled `registered_subunit`). JobPosting JSON-LD on the verified site.
- **News**: the verified site's own RSS/Atom feed, JSON-LD articles, or dated headlines on its news page.
- **Registered workplaces, roles and accounts**: official records keyed by the organisation number.

Relationships are labelled, never collapsed: `exact`, `registered_subunit`, `group_member`.
