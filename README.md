# Kildespor

**Norwegian company research where every fact is tied to the exact organisation number.**
*Kildespor* is Norwegian for "source trail": every fact keeps the trail back to the record or page it came from.

Give it a batch of organisation numbers. For each one it returns a profile built from the official
registers (Brønnøysund entity, roles, workplaces, accounts, update log, state aid), the company's own
verified website, NAV's job feed, Mattilsynet inspections, EU procurement awards, Finanstilsynet and
Arbeidstilsynet registers, customer ratings and Wikidata, with the source URL,
retrieval time, content hash and exact text span behind every fact, an honest state for every
field family it could not fill, and a diff against the previous run.

```bash
./run.sh batch.jsonl out          # creates .venv, installs pinned deps, researches every company
```

That writes:

| File | What it is |
|---|---|
| `out/envelopes.jsonl` | one terminal envelope per input, in input order ([schema](DATA_SCHEMA.md)) |
| `out/run-report.json` | counts, coverage by field family, validation checks, requests, p50/p95, cost |
| `out/viewer/index.html` | a static viewer: search, filter, compare, open every source (works from disk) |
| `out/snapshots.zip` | every response behind a published fact, one entry per SHA-256 |
| `out/history/` | the previous run's envelopes after a refresh |
| `out/.kildespor-cache/` | declared cache: NAV ad id → employer organisation number (an ad's employer never changes), so a refresh fetches only new ads |

Running the same command again with the same output directory is a **refresh**: every fact is
matched to the previous run by a stable key, changes are reported with evidence for both sides,
and facts whose source failed this time are kept, marked as carried forward.

## Results

**Live viewer of the 100-company smoke test: https://rohanglitched.github.io/kildespor/**
(search, filter, compare, open the source behind every fact; works on phones).

The smoke test is the public universe sampled with Builderr's own `select_entry_batch.py` at its default
seed, so anyone can reproduce the batch. Everything it produced is in [`smoke/run/`](smoke/run):
envelopes, run report, the evidence archive and the `verify` report.

| | Smoke test (100) | Development run (1,000) |
|---|---:|---:|
| Envelopes / validation | 100 / passed | 1000 / passed |
| Facts | 6,575 | 63,654 |
| Evidence records, hash found in archive | 6,557, all | 63,291 |
| Quoted page spans found in the archived page | 148 of 148 | |
| Runtime from a cold start (home connection) | 5.2 min | 8.6 min ¹ |
| Third-party cost | $0 | $0 |

¹ NAV's job index builds in parallel with the research and is capped at 7 minutes; on a home connection it indexes
about 5,400 of NAV's ~9,400 active ads in that time.

Companies with at least one verified fact, by field family:

| Family | Smoke test | 1,000 run |
|---|---:|---:|
| Legal identity and brand | 100 / 100 | 1000 / 1,000 |
| Annual accounts and history | 100 / 100 | 999 / 1,000 |
| Leadership and board | 100 / 100 | 999 / 1,000 |
| Workplaces and addresses | 100 / 100 | 1000 / 1,000 |
| Verified official website | 13 / 100 | 149 / 1,000 |
| Company-published contact details | 39 / 100 | 445 / 1,000 |
| Company-owned profiles | 4 / 100 | 89 / 1,000 |
| Hiring | 1 / 100 | 27 / 1,000 |
| Dated public activity | 100 / 100 | 1000 / 1,000 |
| Customer ratings | 0 / 100 | 21 / 1,000 |
| What the company does | 100 / 100 | 1000 / 1,000 |

A random company from the register is usually a small holding or property company with no website,
so the share with a website or profiles reflects the population, not a crawl limit. In a hand-labelled
sample of 80 random companies for which no website was published, two independent searches found only
about 10 with a live site of their own ([eval/website-truth-80.jsonl](eval/website-truth-80.jsonl)).

**Precision.** Independent audits re-fetched every website not proven by its organisation number:
wrong-company websites went from 16 to 10 to 3 to **0 of 70** across the version-1 audits, and every site
proven by its own organisation number was correct in every audit. The October 20 rules were audited the same
way (36 newly published sites): the 3 wrong matches the first audit found became rules and tests, and the
second audit found **0 wrong**. What each audit found and the rule it produced: [EVAL.md](EVAL.md).

## Check the evidence yourself

```bash
.venv/bin/python -m kildespor verify --envelopes out/envelopes.jsonl
```

Every evidence record carries the SHA-256 of the bytes we fetched. `verify` opens `snapshots.zip`,
confirms each hash is there, and checks that each quoted span from a web page really occurs in the
archived page.

## Requirements

Python 3.11+ and outbound HTTPS. No API keys, no accounts, no paid services. Third-party cost: $0.

Without `run.sh`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m kildespor run --organisations batch.jsonl --output out/envelopes.jsonl --html out/viewer
```

The input may be JSONL (`{"organisation_number": "…"}` per line), a JSON array, CSV or plain text.

## How it decides what to publish

1. **Anchor.** Brønnøysundregistrene gives identity, registered contact fields, every active role,
   every registered workplace and every filed year of accounts.
2. **Find the website.** Candidates come from what the entity itself registered (website, e-mail
   domain, its workplaces' websites and e-mails), Wikidata's P856 on the item carrying the
   organisation number, the employer homepage in its own NAV ads, and domains derived from the
   legal name that resolve in DNS.
3. **Prove it.** A site is published only when it shows the organisation number, the registered
   phone or e-mail, the legal name with the registered street address, the exact legal name with its
   legal form and the registered town, or a current role holder together with the full legal name.
   Narrower name proofs cover the rest: a site the entity declared that names it in full on its home
   page; a domain spelling the whole name with the registered town on the site; a `.no` domain spelling
   a name that no other entity in the register carries. A site that prints a different organisation number,
   whose copyright or data-controller line names another company, that is placed in another town, or whose
   brand is the registered name of a sister company is rejected. Sites drawn in JavaScript are read from
   their page data and script bundles. Details: [IDENTITY_RESOLUTION.md](IDENTITY_RESOLUTION.md).
4. **Read the proven site** for company-owned profiles, contact details, addresses, careers pages,
   recruitment platforms, JobPosting data and dated news (RSS/Atom, JSON-LD, news listings).
5. **Hiring.** Every active ad in NAV's job feed is indexed by its employer organisation number;
   an ad is published when that number is the company's or one of its registered workplaces'. The
   recruitment platforms the proven site links (Teamtailor, Recman, ReachMee, Jobylon, Jobbnorge,
   Easycruit, or the site's own careers page) add postings whose employer is the company itself.
6. **Summarise** what kind of company it is in plain English, then sourced conclusions with their
   formula (revenue trend, operating margin, equity ratio, cash against debt, a turn to profit or loss,
   register warnings, register events in the last 12 months), and why each unknown is unknown. Every
   sentence cites the facts it rests on.

Sources and their terms: [SOURCES.md](SOURCES.md).

## Tests

```bash
.venv/bin/pip install pytest==8.3.5 && .venv/bin/python -m pytest -q
```
