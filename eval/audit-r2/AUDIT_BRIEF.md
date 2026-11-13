# Independent audit: are these claims about the right company? (revision 2, Nov 14 2026)

You are an independent checker for a Norwegian company-research agent. Builderr, the challenge organiser, checks a
sample of claims and counts every claim that is about a different company (or is not what it claims to be) against us.
We need at least 95% right; aim for 100%. Be skeptical: your job is to find wrong claims, not to confirm ours.

Input: one JSON object per line with orgnr, company (legal name), municipality, registered_address, verified_site (the
site our agent proved is the company's), field, value, date, url, evidence_url, evidence_span.

For EACH line, open the URL (and the company site / Brønnøysund entry https://data.brreg.no/enhetsregisteret/api/enheter/<orgnr>
when needed; https://virksomhet.brreg.no/nb/oppslag/enheter/<orgnr> is the human page) and decide:
- `correct`: the claim is about this exact legal entity (org number) and is what it says it is.
- `wrong_company`: it belongs to another entity (a sister company, parent group, a namesake, a web agency, a franchise
  chain HQ, a different branch registered as its own company...).
- `not_what_it_claims`: right company but the claim is mislabelled, e.g. "company_news" that is a product/service/contact
  page or has no real publish date or the wrong date; "job_posting" that is closed, an open application or a service page;
  "careers_page" that is not a careers page; a phone/e-mail that is the web agency's or a different office's; a social
  profile that is a personal profile.
- `unverifiable`: the page will not load or is blocked; say why. Do not count these as wrong.

Field rules:
- official_website: the site must be the company's own (org number on the site, its exact name and address, or it is
  clearly the same business). A parent group's or chain's site for a separate subsidiary is wrong_company.
- company_profile: the profile must be the company's own (its name/brand, links back to its site). A sister company's,
  parent's, owner's personal or a product brand owned by another entity is wrong_company. You may not be able to load
  Facebook/Instagram/LinkedIn pages; judge from the handle, the site that links it, and what search engines show only if
  you can fetch them; otherwise mark unverifiable with your best judgement in the note.
- company_news / news_page: a real dated article (or the news section) on the company's own site, with that publish date.
- job_posting: an open posting for this company (NAV ad's employer or the company's careers site).
- email / phone / address_on_site: printed on the company's own site as the company's own contact.

Write your verdicts to the output file named in your task as JSON lines:
{"orgnr", "field", "url", "verdict", "note"} and finish with a short summary: counts per verdict and every non-correct
line with a one-line reason and what rule would have caught it. Do not edit any code. Work quickly but open every URL
you judge (WebFetch; if WebFetch is not available, use the web-fetch agent or curl via Bash with a normal browser UA).
