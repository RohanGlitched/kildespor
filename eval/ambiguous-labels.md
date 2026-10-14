# Withheld ("ambiguous") websites: hand labels and candidate proof rules

Run: `out/d1000/envelopes.jsonl` (1,000 envelopes). Eligible: envelopes with no `official_website` claim and at least one `discovery_trace.sites[]` entry with status `ambiguous` = **317**. Sample: `random.seed(7); random.sample(eligible, 70)` = 70 companies with **90** ambiguous candidate sites (54 companies with 1 candidate, 13 with 2, 2 with 3, 1 with 4).

Method: for each company, `data.brreg.no/enhetsregisteret/api/enheter/{orgnr}` and `/roller` (2026-10-14). For each candidate, the `final` URL (else `https://{domain}/`), robots.txt checked first, home page plus up to one contact and one about page (≤4 requests in flight, 1 s pause per site between pages). One extra manual fetch: the three linked pages on `pharma.cybat.no` (the crawler's links pointed at a host that answers 404). Labels are by hand, reading the page text against the register record and roles. Rules were then run as code over the same fetched pages.

## Counts

| Label | Candidate sites | Companies |
|---|---:|---:|
| BELONGS | 7 | 6 |
| RELATED | 10 | 8 |
| UNSURE | 1 | 1 |
| DIFFERENT | 72 | 55 |
| total | 90 | 70 |

Company level: a company counts once, under its best label (BELONGS > RELATED > UNSURE > DIFFERENT).

**6 of 70 sampled companies (8.6%; Wilson 95% CI 4.0–17.5%) have a withheld site that is really theirs.** Scaled to the 317 eligible envelopes in this run that is about 27 companies (roughly 13–55). Another 8 companies (11%) have a site that belongs to a parent, sister company or brand: not theirs, and exactly the case a loose rule would publish by mistake.

DIFFERENT, by kind (72 sites): foreign company or namesake 28; parked / for-sale / placeholder / server default page 19; generic word, place name, surname or another person's site 16; Norwegian namesake or other company 9. The 19 placeholders (HugeDomains, Digimedia, fruits.co, one.com, united-domains, Nameshield, Apache/Nginx defaults, phpinfo, Google sign-in, plus `engebakken.no`'s Domeneshop "not found") all got status `ambiguous`, not `parked`, so the parked detector misses them. That does not change what gets published, but the trace is wrong.

## Every BELONGS, RELATED and UNSURE row

| Org.nr | Legal name | Municipality | Domain | Label | What ties it (or what it really is) |
|---|---|---|---|---|---|
| 918880038 | CYBAT AS | Trondheim | cybat.no | BELONGS | Terms page (pharma.cybat.no, not crawled): "CybAt AS \| Buktabakkan 41 \| 7070 Bosberg \| ... Org.nr: 918 880 038". |
| 924641320 | VASKERIKOMPETANSE MAGNE FJØRTOFT AS | Lillehammer | vaskerikompetanse.no | BELONGS | Exact legal name with form on home page: "Vaskerikompetanse Magne Fjørtoft AS"; contact "Magne Fjørtoft" = styreleder. |
| 930670685 | CHRISTIAN MEAAS SVENDSEN AS | Kvinnherad | christianmeaassvendsen.com | BELONGS | One-person company named after its daglig leder; site is that person's: "Christian Meaas Svendsen - electric and double bass" (title = legal name minus AS). |
| 933989178 | PLATO CATERING AS | Oslo | platocatering.com | BELONGS | Redirects to platocatering.no; same evidence: "Kjølberggata 21, 0653 Oslo" and founders Mariia Chernat / Elena Lopez. |
| 933989178 | PLATO CATERING AS | Oslo | platocatering.no | BELONGS | Registered c/o address and founders: "Kjølberggata 21, 0653 Oslo"; "founded by two food lovers, Mariia Chernat and Elena Lopez" (both in role register). |
| 953956233 | BREKKENE BORETTSLAG | Bergen | brekkene.no | BELONGS | Exact name plus the full board from the role register: "Geir Jakobsen \| Styrets leder", Elise Lund, Kjetil Rasmussen, Arne Sandal; Flaktveit, Bergen. |
| 975988694 | STORD MARITIME MUSEUM STI | Stord | stordmaritime.no | BELONGS | Name minus STI, same town, founding year and family: "Stord Maritime Museum ... vart etablert i 1994 av Oma-familien. Stiftinga ..." (borderline: run day-to-day by Venelaget, org 913294548). |
| 829967952 | SOLØR HUS EIENDOM AS | Åsnes | solorhus.no | RELATED | Site of sister company Solør Hus AS (925809101): same address "Idrettsvegen 43, 2270 FLISA" and the same people (daglig leder Øystein Aurland). |
| 912664228 | D-S BREKKEVEIEN AS | Sauda | idehus.no | RELATED | Registered e-mail domain is the Idéhus chain site (house brand); D-S Brekkeveien AS is a Sauda project holding company using that domain. |
| 922834199 | AOP ORPHAN PHARMACEUTICALS SWEDEN AB NUF | Sverige | aoporphan.com | RELATED | Redirects to aop-health.com, the parent group site; its Norway entry is "AOP Orphan Pharmaceuticals Sweden AB \| Köpsvängen 16, 168 67 Bromma" (the NUF's head entity). |
| 926456075 | UNIKE HOTELLER EIENDOM AS | Sandefjord | unikehoteller.no | RELATED | Site of Unike Hoteller AS (916830572), the c/o host: "Midtåsveien 2A, 3226 Sandefjord"; CEO Morten Christensen also daglig leder here. |
| 927814536 | KVEDNATUNET BORETTSLAG | Haugesund | kvednatunet.no | RELATED | Redirects to kvednatunethageby.no, the developer's sales site for the area ("Sigurd A. Sande – prosjekteier"); several Kvednatunet entities exist. |
| 928775305 | NORDLO VENNESLA AS | Vennesla | nordlo.com | RELATED | Same Nordlo group site as nordlo.no. |
| 928775305 | NORDLO VENNESLA AS | Vennesla | nordlo.no | RELATED | Group site of Nordlo (nordlo.com/no); Nordlo Vennesla AS is one of ~8 Nordlo subsidiaries. Vennesla not named on the pages fetched. |
| 965641505 | HOTELLDRIFT Q ENTRY AS | Nordre Follo | choice.no | RELATED | Registered e-mail domain choice.no redirects to strawberry.no (group brand site). |
| 965641505 | HOTELLDRIFT Q ENTRY AS | Nordre Follo | nordicchoicehotels.no | RELATED | Registered hjemmeside now redirects to strawberry.no, the hotel group's brand site (operator of Quality Hotel Entry); no hotel-level tie on pages fetched. |
| 996963497 | LÆRINGSVERKSTEDET LILLEHAMMER IDRETTSBARNEHAGE AS | Ullensaker | laringsverkstedet.no | RELATED | Chain parent site (Læringsverkstedet); registered address is chain HQ "Aktivitetsvegen 2, 2069 Jessheim"; individual kindergarten not identified. |
| 993007102 | ENGEBAKKEN EIENDOM AS | Stange | engebakken.no | UNSURE | Domain is the entity's (registered e-mail mail@engebakken.no) but no website is configured (Domeneshop 'not found'). |

### Why the current gate missed each BELONGS

| Domain | Gate it should have passed | Why it did not |
|---|---|---|
| platocatering.no / .com | `name_address` | The register address has two lines, `["c/o Factory Tøyen", "Kjølberggata 21"]`. `verify()` uses only `adresse[0]`, the c/o line, so the street can never match. 14 of the 70 sampled companies have a c/o or building line first. |
| vaskerikompetanse.no | `legal_name` | The page shows "Vaskerikompetanse Magne Fjørtoft AS" exactly, but `_domain_from_name` rejects the label: `vaskerikompetanse` is 17 of the 30 joined name letters, under the 0.6 threshold, and it is neither all tokens nor the first two. |
| brekkene.no | `legal_name` | Legal form BRL is not in `FORMS`, so `_exact_name_rx` returns None for "BREKKENE BORETTSLAG". Note that two Brekkene Borettslag exist (Bergen and Haugesund), so the exact name alone is not enough. The board names decide it. |
| stordmaritime.no | `legal_name` | Legal form STI maps to "" in `FORMS`, so there is no exact-name test. The site writes the name without "STI". |
| christianmeaassvendsen.com | none | One-person company named after its owner. The site never prints "AS", an org.nr, a phone or an address. Only the role register ties it. |
| cybat.no | `orgnr` | `cybat.no` redirects to `pharma.cybat.no`, and its menu links point back to `cybat.no/om-oss/...`. `siteparse.internal_links(home, home.host())` drops them, because `cybat.no` is not `pharma.cybat.no` or a subdomain of it (and fetched as written they return 404). The org.nr is on the shop terms page, `pharma.cybat.no/om-oss/vilkar-og-betingelser/`, a `privacy`-kind page the crawler would otherwise have fetched. |

## Candidate rules, ranked

Each rule was run as code over all 90 fetched candidates. "Recovered" counts BELONGS sites (companies in brackets) out of 7 (6). "Wrong" counts DIFFERENT sites accepted out of 72, and RELATED sites accepted out of 10. Publishing a RELATED site as `exact` is also an error.

| # | Rule | Recovered | Wrong: DIFFERENT | Wrong: RELATED | Accepted sites |
|---|---|---:|---:|---:|---|
| 1 | **Union of rules 2 to 7** (run as code) | 6 (5) | 0 | 0 | brekkene.no, christianmeaassvendsen.com, platocatering.com, platocatering.no, stordmaritime.no, vaskerikompetanse.no |
| 1+8 | **Union of rules 2 to 8** (rule 1 plus the crawl fix) | 7 (6) | 0 | 0 | rule 1 plus cybat.no |
| 2 | **Role holder + name**: at least one current role holder from `/roller` (full name, or first + last name) appears on the site, and every legal-name token (forms dropped) appears on the site | 5 (4) | 0 | 0 | brekkene.no, christianmeaassvendsen.com, platocatering.com, platocatering.no, vaskerikompetanse.no |
| 3 | **Two role holders + name**: as above but with two or more role holders | 3 (2) | 0 | 0 | brekkene.no, platocatering.com, platocatering.no |
| 4 | **Form-less legal forms** (BRL, STI, SAM, ENK, FLI): exact legal name (keeping "Borettslag", dropping "STI") on a name-derived domain, plus the registered poststed or municipality as a whole word | 2 (2) | 0 | 0 | brekkene.no, stordmaritime.no |
| 5 | **c/o fix for `name_address`**: test every non-c/o line of the register address, not just `adresse[0]`. Otherwise unchanged (all name tokens + street + postcode on one page) | 2 (1) | 0 | 0 | platocatering.com, platocatering.no |
| 6 | **Relaxed name-domain test for `legal_name`**: also accept a domain label equal to the first k name tokens joined (k ≥ 1, at least 6 letters) | 1 (1) | 0 | 0 | vaskerikompetanse.no |
| 7 | **Personal-name company**: the name minus its form equals a role holder's full registered name, the domain is derived from it, and the name appears on the site | 1 (1) | 0 | 0 | christianmeaassvendsen.com |
| 8 | **Crawl fix (orgnr proof unchanged)**: treat links on the same registrable domain as internal (here `cybat.no` from `pharma.cybat.no`), and when such a link 404s after a cross-host redirect, retry its path on the final host | 1 (1) | 0 | 0 | cybat.no (checked by hand, not in the code run) |

Rules that look attractive but are **not safe**, for comparison:

| Rule | Recovered | Wrong: DIFFERENT | Wrong: RELATED | Accepted sites |
|---|---:|---:|---:|---|
| Brand = legal name minus form + registered town, on a name-derived domain | 4 (3) | 1 | 0 | brekkene.no, lovenskiold.no, platocatering.com, platocatering.no, stordmaritime.no |
| Same, without the domain test | 4 (3) | 1 | 1 | brekkene.no, kvednatunet.no, lovenskiold.no, platocatering.com, platocatering.no, stordmaritime.no |
| Registered street + postcode on a page, without the name tokens | 2 (1) | 0 | 3 | laringsverkstedet.no, platocatering.com, platocatering.no, solorhus.no, unikehoteller.no |
| Two or more role holders on the site, without the name tokens | 3 (2) | 0 | 1 | brekkene.no, platocatering.com, platocatering.no, solorhus.no |

What the unsafe rows show:

- **Address alone accepts sister companies.** `solorhus.no` (Solør Hus AS for SOLØR HUS EIENDOM AS), `unikehoteller.no` (Unike Hoteller AS, the c/o host, for UNIKE HOTELLER EIENDOM AS) and `laringsverkstedet.no` (chain HQ for one kindergarten AS) all carry the registered street and postcode. Keeping every legal-name token in the test ("eiendom", "idrettsbarnehage") is what rejects them.
- **Role holders without the name accept sister companies too.** `solorhus.no` lists the daglig leder and a board member of the Eiendom company, because the same people run the operating company.
- **Brand + town accepts a namesake.** `lovenskiold.no` (Løvenskiold-Vækerø) contains both "Løvenskiold" and "forvaltning" and is in Oslo, but LØVENSKIOLD FORVALTNING AS is a separate family investment company.

## Recommendation

Ship, in this order: rule 5 (c/o fix; it is a plain bug), rule 8 (crawl fix; same orgnr proof, so no new risk), rule 6 (relaxed domain test), rule 4 (BRL/STI form words; keep the town check, since names like Brekkene Borettslag repeat across towns), and then rule 2, the role-holder rule, as a new proof (`role_holder_name`, about 0.9). Rule 7 is already covered by rule 2 in this sample. Keep it only if rule 2 is given a two-person minimum, because one common personal name (e.g. "Per Haugen") is a weak tie by itself. Together they recover all 7 BELONGS sites (6 companies) with 0 DIFFERENT and 0 RELATED accepted in this sample.

Caveats: 70 companies is small. Zero false accepts out of 72 DIFFERENT gives an upper bound of about 4% (rule of three), and most DIFFERENT sites are easy namesakes. The hard negatives are the 10 RELATED sites, and every safe rule above rejects all of them. `stordmaritime.no` is a borderline BELONGS: it is the museum's site, but day-to-day it is run by Venelaget for Stord Maritime Museum (913294548), a separate organisation. The 8 RELATED companies could be published as a `group_member` relation, never as `exact`.
