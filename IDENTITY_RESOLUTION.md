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
| `name_address` | every legal-name token **and** a registered street line (c/o lines skipped) **and** the postcode appear on one page | 0.93 |
| `legal_name` | the exact legal name with its legal form in capitals ("Fjellform AS", never the English word "as"), letters æ/ø/å and punctuation kept, on a name-derived or declared domain, **and** the registered town or postcode on the site | 0.90 |
| `legal_name_town` | for co-ops, foundations and other forms without a suffix: the exact full name plus the registered town, on a name-derived domain | 0.90 |
| `role_holder_and_name` | a current role holder's full name from the role register **and** every legal-name token on the same page | 0.88–0.90 |

A website or e-mail domain declared in the register is a *candidate*, never proof on its own: property
managers, parents, chains and sister companies are often declared (our audit found 2 of 12 such sites
were the entity's own). The declared value is still published as a registry fact (`registered_website`).

A second website is published only when it too shows the organisation number.

Rejections, all visible in the discovery trace:

- **other_entity**: the site prints a different organisation number next to an "org.nr", "MVA",
  "organisation number" or "company no." label, or its ©/copyright, "drevet av" or data-controller
  line names a different legal entity, and the site never shows our number. A shared management company, a parent or a namesake is never collapsed into
  our entity.
- **parked**: placeholder, for-sale, under-construction or empty pages.
- **ambiguous**: a live site with none of the proofs above (for example a dictionary-word domain such
  as `nordlys.no`, or `raservice.no`, which belongs to *RA Service AS* in Oslo, not *RÅ SERVICE AS* in
  Holmestrand).
- **blocked**: robots.txt disallows our user agent.

## Everything else hangs off the verified site or the organisation number

- **Social profiles**: only outbound links on the verified site, its JSON-LD `sameAs`, or Wikidata
  properties on the item that carries our organisation number. When a site links several profiles on
  one platform (client portfolios, partners, template leftovers) only those whose handle resembles the
  company's name, domain or brand are kept; platform pages (policies, business, privacy) are ignored.
- **Contact details**: e-mail addresses on the verified site's own domain (or the registered address);
  Norwegian phone numbers from the home, contact and about pages only (privacy pages quote regulators,
  store lists quote retailers), at most three, none from pages listing more than four numbers unless
  registered; foreign numbers, digit runs and year pairs are rejected.
- **Job ads**: NAV records whose `employer.orgnr` is ours or one of our registered subunits'
  (subunit matches are labelled `registered_subunit`). JobPosting JSON-LD on the verified site.
- **News**: the verified site's own RSS/Atom feed, JSON-LD articles, or dated headlines on its news page.
- **Registered workplaces, roles and accounts**: official records keyed by the organisation number.

Relationships are labelled, never collapsed: `exact`, `registered_subunit`, `group_member`.
