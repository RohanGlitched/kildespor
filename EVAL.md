# Evaluation

How we measured precision and recall, what went wrong, and what each finding changed. The labelled
sets and audit reports are in `eval/`.

## Corpora

| Set | What it is | Use |
|---|---|---|
| `eval/dev-100.jsonl` | 100 random organisation numbers from the public universe (seed 11) | development |
| `eval/dev-1000.jsonl` | 1,000 random organisation numbers (seed 33) | scale, runtime and precision audits |
| `eval/hiring-30.jsonl` | 30 companies with an active NAV ad, ads labelled from NAV's own records | job recall |
| `eval/smoke-*.jsonl` | single companies chosen for one source each (food inspections, TED, Finanstilsynet, cleaning register) | connector checks |

The official batch is chosen by Builderr; none of these sets tunes a threshold on it.

## Job recall (NAV)

Labelled set of 30 companies with 31 known active ads: **30/30 companies, 31/31 ads** found once every
active ad is indexed by its employer organisation number. Name matching alone found 15/30.

## Website precision: three independent audits on the 1,000-company run

Each audit was done by a separate agent that re-fetched every audited site and compared it with the
Brønnøysund entity, its roles and its registered workplaces.

| Run | Websites published | Audited | Wrong entity | Related entity (parent, sister, chain, manager) | Unclear |
|---|---:|---:|---:|---:|---:|
| d1000 | 174 | 147 | 3 | 13 | 2 |
| d1000c | 167 | 102 (all without an org.nr proof) | 1 | 9 | 2 |
| d1000d | 154 | 83 (all 73 without an org.nr proof + 10) | 0 | 3 (two sister companies sharing an address, one sports club) | 0 |
| d1000h | 136 | 70 (all 60 without an org.nr proof + 10) | **0** | **0** | **0** |

In every audit, **every website proven by its own organisation number was correct**. Every bad match
came from the weaker proofs, and each pattern became a rule and a regression test:

| Pattern found | Example | Rule now |
|---|---|---|
| The register declares a manager's, parent's or chain's site | a sameie's property manager (bate.no, obos.no); bilxtra.no for a dealer | a declared website is a candidate, never proof |
| English "as" read as the legal form | "upload … to Nemitek as part of" | legal form must be in capitals, and the town or postcode must be on the site |
| Copyright or data-controller line names another company | "© Norrøn Bolig AS" on a site for Norrøn AS | any operator line naming another entity rejects the site |
| Organisation-number labels in English, or numbers failing the checksum | abpre.no, universi.no | all labelled numbers count |
| A group switchboard or owner's phone matched | klaveness.com for Klaveness Finans AS | phone and e-mail proofs also need every legal-name word on the site |
| Housing co-ops managed by a company | skeiendom.no | co-ops and sameier need their own organisation number on the site |
| Template, partner and portfolio links | linkedin.com/company/wix-com, a client's Instagram | a social handle must resemble the company's name, domain or brand |
| Years, fax and foreign numbers read as phones | 20222021, +61 8 6559 6499 | Norwegian numbers only, from home/contact/about pages |
| A sister company's site at the same address | avineering.com for Avineering Solutions AS (the site is AviNeering AS's) | when the site's brand stem is the exact registered name of another active entity, the site is withheld unless it shows our number |
| "X er behandlingsansvarlig" | "Sædalen IL er behandlingsansvarlig" | operator lines are read in both word orders |
| A social handle naming a sister or a foreign maker | facebook.com/milepel for Milepel Campus AS; youtube @AiriusEuropeLtd | a handle that is another active entity's registered name, or names a foreign company form, is dropped |
| An owner's personal profile, a truncated slug | instagram of the owner of Scope Film AS; facebook.com/novatek.n | handles must share a word with the legal name or the domain; cut-off slugs are dropped |

The final audit (d1000h) also checked every customer rating (21/21 correct: the directory page states the
organisation number), 15 state-aid awards (15/15) and 10 food inspections (10/10), and all 81 e-mail
addresses it looked at (81/81).

## October 20: recall pass with ground truth, then an audit of every new website

**Ground truth.** On 300 random companies from the public universe, version 1 published 42 websites. For
80 of the 258 companies without one, two independent labelling agents each searched the web and the
register by hand (`runs/label80-truth.*.jsonl`, kept outside the repository). About 10 of the 80 have a
live site of their own; the rest have none (holding, property and dormant companies), only a parent's,
manager's or chain's site, or a dead or robots-blocked one. The website ceiling in a random batch is low,
so every rule below targets a pattern seen in those labels:

| Missed pattern | Example | New rule |
|---|---|---|
| a declared site naming the entity in full, without a number | norskartist.no | `registry_declared_name` |
| a full-name domain on a site that also states the town | nesbruklinikken.no, driftstorget.no | `name_domain_town` |
| a full-name `.no` domain whose name nobody else in the register carries | beautyhudstudio.no | `unique_name_domain` |
| street and house number without the postcode | "Torpebaugen 4" on norsktrafoservice.com | `name_street` |
| org.nr only inside a React bundle | zenergi.no | page data and same-host bundles read as pages |
| page words read as a sister company's brand | "Hjem - Driftstorget" → "HJEM AS" | page words skipped |
| a namesake in another town blocked a site printing our exact legal name | okkenhaug.no vs the Oslo sole trader "Okkenhaug" | namesakes in other municipalities ignored |
| a Wikidata country site chosen over the registered one | equinor.com.br over equinor.com | best proof first, then register before Wikidata |

**Result on the same 300:** 42 → 54 websites. **On 271 fresh companies (holdout):** 39 → 47.

**Audit.** A separate agent re-checked every one of the 20 newly published websites against the register,
roles and same-name entities: 16 correct, 1 right company on the wrong URL, **3 wrong entity**. Each became
a rule and a test, and a live re-probe of all 20 with the fixed rules publishes none of the 3 and keeps all 16:

| Wrong | Why it passed | Rule now |
|---|---|---|
| kriss-consulting.com, "Kriss Consulting Inc" (US) for a carpenter in Kristiansand | the site answered our Norwegian Accept-Language with `lang="no"` | `unique_name_domain` only on `.no`; a foreign company form (Inc, Ltd, GmbH…) in a title refuses every name proof |
| dekkhuset.no (DEKKHUSET AS, Alversund) for DEKK HUSET AS (Oppaker) | the register search used the spaced name | the name is searched both spaced and squashed; name-only proofs are refused when the site is placed in another town |
| a Wix site of the sole trader "ENK Stian Sæther" for STIAN SÆTHER AS | a company named after its owner: the owner's name proves nothing | role-holder proof off for person-named companies; free-hosting subdomains need a number, phone or e-mail |
| rorkjop.no member page for ZM RØR AS (right company) | its domain forwards to a chain's profile page | the company's own domain is published; the other site's links are not used |

**Second audit (1,000-company development set).** With all rules in place the 1,000-company run published
149 websites against 136 in the last audited version-1 run (runtime 8.6 min against 8.2). The 16 new sites that
rest on name-based or single-contact proofs went to a fresh independent audit: 13 correct, 2 acceptable (the
Norwegian operating company's brand site; NGI's site shared by the AS and its foundation), 1 uncertain, **0
wrong entity**. The uncertain one (solcellegrossisten.no, a webshop showing only a brand name and a free-mail
address, offered for sale by a private person) led to one more rule: `unique_name_domain` also needs something
on the site that ties it to this company — a registered role holder, the registered phone or e-mail, or the
registered street or postcode. Role holders now match when the site drops a middle name or writes a
hyphenated surname ("Andreas Greve-Isdahl" for Andreas Alnæs Greve-Isdahl).

Two run-time bugs were found the same way and fixed before release: a retry meant for HTTP 429 also retried
timeouts, which doubled every unreachable host's wait and pushed many sites past their 60-second budget (280
timeouts on 1,000 companies, against 14 after the fix); and script bundles are now read only for pages with almost
no HTML text, at most two per site, 1.2 MB each, six at a time across the run.

## Recall: what the withheld sites were

A separate agent labelled 70 companies whose candidate sites had been withheld as ambiguous: 6 really
had their own site (8.6%), 8 had a related company's site, 55 had a namesake or placeholder. Five rules
from that study recovered all 6 with no false accepts in the sample; after the precision audits we kept
those that survive the stricter gates (c/o address lines, role holder plus full legal name, name-prefix
domains, same-domain links).

## Refresh

Re-running the same 20 companies into the same output directory produced **0 changes** and archived the
previous envelopes. Unit tests cover new and ended roles with evidence on both sides, and facts kept
from the previous run when their source fails.
