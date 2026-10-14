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
| d1000d | see below | | | | |

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
