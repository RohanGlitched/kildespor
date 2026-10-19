"""Hand-check helper: open every non-NAV job posting in an envelopes file and show who the ad page says the employer is.

python eval/check_postings.py out/run/envelopes.jsonl
For each posting: the legal name, the posting title, the ad page's JSON-LD hiringOrganization (if any), its <title>,
and whether every legal-name word appears on the ad page. Robots.txt is obeyed (the project's client).
"""
import asyncio
import json
import re
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from kildespor import siteparse as sp  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.util import fold, name_tokens  # noqa: E402


async def main(path: str) -> None:
    rows = []
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        for c in e["claims"]:
            if c["field"] == "job_posting" and not c["key"].startswith("jobs:job_posting:nav") and c["value"].get("platform"):
                rows.append((e["legal_name"], c["value"]))
    client = Client(16)

    async def one(name, v):
        f = await client.get("check", v["url"], timeout=15)
        if not f.ok:
            return name, v, f"HTTP {f.status or f.error or f.blocked}", "", None
        pg = sp.parse(f.text(), v["url"], f.final_url)
        orgs = [str((n.get("hiringOrganization") or {}).get("name")) for n in pg.jsonld
                if n.get("@type") == "JobPosting" and isinstance(n.get("hiringOrganization"), dict)]
        words = set(re.findall(r"[a-z0-9]+", fold(pg.text + " " + pg.title)))
        named = set(name_tokens(name)) <= words
        return name, v, "; ".join(orgs) or "-", pg.title[:70], named
    for name, v, org, title, named in await asyncio.gather(*(one(n, v) for n, v in rows)):
        print(f"{name[:28]:28} | {v['platform']:10} | {v['title'][:50]:50} | jsonld={org[:40]:40} | name_on_page={named} | {title}")
    await client.close()


asyncio.run(main(sys.argv[1]))
