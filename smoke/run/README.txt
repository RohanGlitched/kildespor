Kildespor run output
====================

OPEN index.html IN A BROWSER (double-click it). It is the results viewer: search and filter every company,
compare two to four side by side, and open the source behind every fact (URL, retrieval time, SHA-256, quoted text).
It works straight from disk: no server, no network, no install. Phones work too.

  index.html          the viewer (100 companies); same viewer also at viewer/index.html
  envelopes.jsonl     one JSON envelope per input organisation number, in input order
  run-report.json     counts, coverage by field family, validation checks, requests, runtime, cost
  snapshots.zip       every fetched response behind a published fact, by SHA-256

Check the evidence: python -m kildespor verify --envelopes envelopes.jsonl
Hosted example of the same viewer: https://rohanglitched.github.io/kildespor/
