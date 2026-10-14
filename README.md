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
| Facts | 6,581 | 63,909 |
| Evidence records, hash found in archive | 6,543, all | 63,532 |
| Runtime from a cold start | 5.5 min | 8.2 min ¹ |
| Third-party cost | $0 | $0 |

¹ On that run NAV's feed could not be reached because of a local DNS fault (since fixed by the resolver fallback); the job index builds in parallel with the research, so it adds little when it runs.

Companies with at least one verified fact, by field family:

| Family | Smoke test | 1,000 run |
|---|---:|---:|
| Legal identity and brand | 100 / 100 | 1000 / 1,000 |
| Annual accounts and history | 100 / 100 | 999 / 1,000 |
| Leadership and board | 100 / 100 | 999 / 1,000 |
| Workplaces and addresses | 100 / 100 | 1000 / 1,000 |
| Verified official website | 9 / 100 | 139 / 1,000 |
| Company-published contact details | 36 / 100 | 437 / 1,000 |
| Company-owned profiles | 2 / 100 | 85 / 1,000 |
| Hiring | 1 / 100 | 21 / 1,000 |
| Dated public activity | 100 / 100 | 1000 / 1,000 |
| Customer ratings | 0 / 100 | 21 / 1,000 |
| What the company does | 100 / 100 | 1000 / 1,000 |

A random company from the register is usually a small holding or property company with no website,
so the share with a website or profiles reflects the population, not a crawl limit. On the
1,000-company run, websites verified by Kildespor reach **139** companies; the register lists a website for
about 9% of them.

**Precision.** Independent audits of the 1,000-company run re-fetched every website not proven
by its organisation number: wrong-company websites went from 16 to 10 to 3, and every site proven by
its own organisation number was correct in every audit. What each audit found and the rule it
produced: [EVAL.md](EVAL.md).

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
   A site that prints a different organisation number, or whose copyright or data-controller line
   names another company, is rejected. A website declared in the register is a candidate, never proof
   on its own. Details: [IDENTITY_RESOLUTION.md](IDENTITY_RESOLUTION.md).
4. **Read the proven site** for company-owned profiles, contact details, addresses, careers pages,
   recruitment platforms, JobPosting data and dated news (RSS/Atom, JSON-LD, news listings).
5. **Hiring.** Every active ad in NAV's job feed is indexed by its employer organisation number;
   an ad is published when that number is the company's or one of its registered workplaces'.
6. **Summarise** in short sentences that each cite the facts they rest on, and list what is unknown.

Sources and their terms: [SOURCES.md](SOURCES.md).

## Tests

```bash
.venv/bin/pip install pytest==8.3.5 && .venv/bin/python -m pytest -q
```
