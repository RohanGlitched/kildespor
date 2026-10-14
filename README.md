# Kildespor

**Norwegian company research where every fact is tied to the exact organisation number.**
*Kildespor* is Norwegian for "source trail": every fact keeps the trail back to the record or page it came from.

Give it a batch of organisation numbers. For each one it returns a profile built from the official
registers, the company's own verified website, NAV's job feed and Wikidata, with the source URL,
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

Running the same command again with the same output directory is a **refresh**: every fact is
matched to the previous run by a stable key, changes are reported with evidence for both sides,
and facts whose source failed this time are kept, marked as carried forward.

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
