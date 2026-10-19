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
| `name_street` | every legal-name token **and** the registered street line with its house number on one page (no postcode needed), on a site whose domain spells the whole name or that the entity declared | 0.92 |
| `registry_declared_name` | a site the entity declared in the register (or for a registered workplace) whose home page names it in full: every distinctive legal-name word together in the title, site name, description, Organization JSON-LD or host name; a one-word name needs five or more letters and a home page with real content | 0.90 |
| `name_domain_town` | a guessed domain that spells the whole name (eight or more letters), a home page titled with the whole name, **and** the registered town or postcode on the site (a town that is part of the name does not count; then only the postcode does) | 0.90 |
| `unique_name_domain` | a guessed **.no** domain that spells the whole name, a home page titled with it, and a register search (entities and workplaces) that finds no other active entity whose name equals or starts with ours | 0.90 |

Every name-based proof refuses a title or name that carries a foreign company form ("Kriss Consulting Inc",
"… GmbH", "… Ltd"): that names another legal entity. A site that the browser draws from JavaScript has
little HTML text; its page data and up to three of its own script bundles are read as extra pages, so an
"Org.nr" printed by a React footer still proves the site (the quoted span is the exact line in the archived
bundle).

A website or e-mail domain declared in the register is a *candidate*, never proof on its own: property
managers, parents, chains and sister companies are often declared (our audit found 2 of 12 such sites
were the entity's own). The declared value is still published as a registry fact (`registered_website`).
The `registry_declared_name` proof is the narrow exception: the declared site must also name the entity in
full on its home page, which managers' and parents' sites do not.

**Sibling check.** A site proven without the organisation number is withheld when its brand stem (domain
label, site name, or the title part that is not a page word such as "Hjem" or "Forside") is the exact name of
another active entity, because sister companies share addresses, phones and owners. The exception: when the
site prints our exact legal name with its legal form and that other entity is registered in a different
municipality, it is a namesake, not a sister (`okkenhaug.no` is Okkenhaug Bil AS in Trondheim, not the
ceramics firm "Okkenhaug" in Oslo; `andvordgruppen.no` stays rejected for Andvord Invest AS because
Andvordgruppen AS sits at the same Oslo address).

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
- **blocked**: robots.txt disallows our user agent. The company's website state is `blocked` only when a
  site the entity declared refuses us; a guessed domain that refuses crawlers says nothing about the company.

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
- **Job ads on recruitment platforms** (Teamtailor, Recman, ReachMee, Jobylon, Jobbnorge, Easycruit, Mojob,
  Lever, Greenhouse, Recruitee, and the site's own careers page; see SOURCES.md). A posting is published,
  labelled `exact`, only when all of these hold:
  1. the platform page was reached from a link or embed on the verified site (never from a search);
  2. the employer the platform names for that posting — or, when the platform names none per posting
     (Teamtailor, ReachMee, Lever, Greenhouse), the account's own name — is our legal name. "Matches" is
     strict: the same name words (legal form, "og/&" and Norway/Norge ignored); or our full name followed
     only by a place or a department word; or our name without a trailing "Norge". A name carrying its own
     legal form ("Aberia Omsorg & Assistanse AS" for ABERIA AS, "Pincho Nation Tromsø AS"), a foreign form
     (AB, GmbH, Ltd), a group name ("MiO Gruppen" for MIO BPA AS) or a parent ("ScaleAQ" for PROBOTIC AS)
     never matches. A staffing agency's account (Recman, "Jefferson Wells") listing ads for many clients
     keeps only the ads whose employer is us; a group account listing several companies keeps only ours;
  3. the posting names no organisation number other than ours or a registered subunit's;
  4. it is not expired (deadline in the past), not an open application, and not located abroad
     (Lever and Greenhouse boards of international companies: Norwegian locations only);
  5. it is not already in the profile from NAV (same link, or same title within 7 days of the NAV date;
     the careers source waits for NAV's postings first).
  Plain ads on the company's own careers page also need ad wording, the company's name on the ad page,
  and no "hos X"/"Arbeidsgiver: X" naming another employer — a shopping centre's "Ledig stilling hos Lekia"
  is never published under the centre.
- **News**: the verified site's own RSS/Atom feed, JSON-LD articles, or dated headlines on its news page.
- **Registered workplaces, roles and accounts**: official records keyed by the organisation number.

Relationships are labelled, never collapsed: `exact`, `registered_subunit`, `group_member`.
