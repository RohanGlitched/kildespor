# Kildespor

**Norwegian company research where every fact is tied to the exact organisation number.**
*Kildespor* is Norwegian for "source trail": every fact keeps the trail back to the record or page it came from.

**See the results: https://rohanglitched.github.io/kildespor/** (hosted viewer of a real run: search,
filter, compare companies side by side, open the source behind every fact; desktop and phone).
After your own run, **open `out/index.html`** in any browser: the same viewer, straight from disk, no server.

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
| **`out/index.html`** | **the results viewer: open it in a browser** (double-click; works from disk, no server, no network) |
| `out/README.txt` | what each file is, and "open index.html" |
| `out/envelopes.jsonl` | one terminal envelope per input, in input order ([schema](DATA_SCHEMA.md)) |
| `out/run-report.json` | counts, coverage by field family, validation checks, requests, p50/p95, cost; `viewer.open` is the viewer's path |
| `out/viewer/` | the viewer's files and one small data file per company (loaded on demand, so 1,000+ companies stay fast) |
| `out/snapshots.zip` | every response behind a published fact, one entry per SHA-256 |
| `out/history/` | the previous run's envelopes after a refresh |
| `out/.kildespor-cache/` | declared cache: NAV ad id → employer organisation number (an ad's employer never changes), so a refresh fetches only new ads |

### Viewing results

Every verifiable thing in the viewer carries a red **T**, like the painted marks on Norwegian hiking trails.
Select it and the fact's *source trail* opens beside the page: the fact, the exact words it rests on, the fetched
document (URL, retrieval time, HTTP status, SHA-256 of the bytes) and the source it came from, joined by a drawn line.

- **Find**: one search box for name, organisation number, website, place or industry; filters for website, hiring,
  company news, social profiles and changes; place shortcuts; sort by revenue, result, employees, latest news or open jobs.
- **Compare**: tick two to four companies, open *Compare* for suggested pairs, or use *Side by side with* on any
  profile: summary, accounts, size, website, social profiles, open jobs, news and unknowns in columns. The link can be shared.
- **Verify**: a profile opens with the summary headline and brief, each sentence with its trail, then key figures,
  company news, open jobs and social profiles, and what could not be confirmed and why.
- Phones get the same views with tabs at the bottom and the trail as a sheet. Keyboard: `/` to search, arrows to move,
  `c` to add to compare, `Esc` to close a trail. Light and dark themes; motion is off when the system asks for less.

To rebuild the viewer from an envelopes file: `python -m kildespor view --envelopes out/envelopes.jsonl --out out/viewer`.

Running the same command again with the same output directory is a **refresh**: every fact is
matched to the previous run by a stable key, changes are reported with evidence for both sides,
and facts whose source failed this time are kept, marked as carried forward.

## Results

**Live viewer: https://rohanglitched.github.io/kildespor/**
(search, filter, compare, open the source behind every fact; works on phones).

The smoke test is the public universe sampled with Builderr's own `select_entry_batch.py` at its default
seed, so anyone can reproduce the batch. Everything it produced is in [`smoke/run/`](smoke/run):
envelopes, run report, the evidence archive and the `verify` report.

| | Smoke test (100) | Development run (1,000) |
|---|---:|---:|
| Envelopes / validation | 100 / passed | 1000 / passed |
| Facts | 6,504 | 63,157 |
| Evidence records, hash found in archive | 6,455, all | 62,838, all |
| Quoted page spans found in the archived page | 105 of 105 | 1,759 of 1,799 ¹ |
| Runtime from a fresh clone (home connection, includes installing) | 5.9 min | 8.1 min ² |
| Third-party cost | $0 | $0 |

¹ The rest are contact lines on pages drawn by JavaScript, whose text order differs from the raw HTML.
² NAV's job index (every readable active ad of the last 180 days, about 10,000) builds in parallel with the research.

Companies with at least one verified fact, by field family (a fresh clone of the submitted commit):

| Family | Smoke test | 1,000 run |
|---|---:|---:|
| Legal identity and brand | 100 / 100 | 1000 / 1,000 |
| Annual accounts and history | 100 / 100 | 999 / 1,000 |
| Leadership and board | 100 / 100 | 995 / 1,000 |
| Workplaces and addresses | 100 / 100 | 997 / 1,000 |
| Verified official website | 11 / 100 | 151 / 1,000 |
| Company-published contact details | 37 / 100 | 445 / 1,000 |
| Company-owned profiles | 3 / 100 | 73 / 1,000 |
| Hiring (open postings or a real careers page) | 0 / 100 | 15 / 1,000 |
| Dated company news from the company's own site | 2 / 100 | 32 / 1,000 |
| Dated public activity (register events, awards, news) | 100 / 100 | 1000 / 1,000 |
| Customer ratings | 0 / 100 | 21 / 1,000 |
| What the company does | 100 / 100 | 996 / 1,000 |

A random company from the register is usually a small holding or property company with no website,
so the share with a website or profiles reflects the population, not a crawl limit. In a hand-labelled
sample of 80 random companies for which no website was published, two independent searches found only
about 10 with a live site of their own ([eval/website-truth-80.jsonl](eval/website-truth-80.jsonl)).

**Precision.** Independent audits re-fetched every website not proven by its organisation number:
wrong-company websites went from 16 to 10 to 3 to **0 of 70** across the version-1 audits, and every site
proven by its own organisation number was correct in every audit. The October 20 rules were audited the same
way (36 newly published sites): the 3 wrong matches the first audit found became rules and tests, and the
second audit found **0 wrong**. For revision 2 (14 November), two more independent audit rounds re-checked
561 published website, profile, contact, news and job claims on 649 companies, including a register search for
a better-matching entity behind every profile handle; every wrong or mislabelled claim they found (a sister
company's profile or site, a group site's contacts, default posts, list pages, import-stamped dates) became a
rule and a regression test. What each audit found and the rule it produced: [EVAL.md](EVAL.md).

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
4. **Read the proven site** for company-owned profiles, contact details, addresses and careers pages.
   A profile is published only when its handle is the company's own name or site name (optionally with
   its own name words, its town, a legal form or a generic suffix), and no other active entity in the
   register carries that name: `rogeraamodteiendom` on ROGER AAMODT BYGG AS's site is a sister company's.
5. **Company news.** Real, dated articles from the proven site: its WordPress API, its RSS/Atom feed or
   its article pages, using the publish date (never an "updated" date) and checking that the article page
   shows readers that date. Default "Hello world" posts, product, project, contact, category and tag pages,
   and template feeds that give every item one date are rejected.
6. **Hiring.** Every readable active ad in NAV's job feed (180 days back) is indexed by its employer
   organisation number; an ad is published when that number is the company's or one of its registered
   workplaces', the ad page names that employer, and the ad is still open. Postings on the proven site's
   careers pages and on the recruitment platforms it links (Teamtailor, Recman, ReachMee, Jobylon,
   Jobbnorge, Easycruit, Webcruiter, …) are published only when the page is an open posting for this
   company: open applications, service pages, closed ads and a sister company's ads are rejected.
7. **Summarise for a buyer.** The summary opens with the one fact a buyer would want first (a risk flag,
   open positions, a large revenue swing, a turn to profit or loss, recent news, a leadership change, or
   size and margin), with its source in brackets. A short brief follows: what the company does, how it is
   doing (with the formula behind each figure), what changed in the last 12 months, and what was checked
   but not found and why. Every sentence names its source and lists the facts it rests on.

Sources and their terms: [SOURCES.md](SOURCES.md).

## Tests

```bash
.venv/bin/pip install pytest==8.3.5 && .venv/bin/python -m pytest -q
```
