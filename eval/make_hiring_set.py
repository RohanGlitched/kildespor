"""Build a labelled set: companies (main units) that have an active NAV ad, with the ad ids we expect to find."""
import asyncio
import json
import random
import sys

sys.path.insert(0, ".")
from kildespor.agent import Context  # noqa: E402
from kildespor.discovery import Resolver  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.sources.nav_jobs import NavJobs  # noqa: E402


async def main(n: int, out: str):
    c = Client(16)
    ctx = Context(c, Resolver())
    nav = NavJobs(window_days=10)
    await nav.prepare(ctx, [])
    act = [u for u, e in nav.ads.items() if e.get("status") == "ACTIVE"]
    random.Random(5).shuffle(act)
    labels: dict[str, set] = {}
    for u in act[: n * 4]:
        d, f = await nav._detail(ctx, u)
        emp = ((d or {}).get("ad_content") or {}).get("employer") or {}
        org = emp.get("orgnr")
        if not org:
            continue
        r = await c.get("brreg", f"https://data.brreg.no/enhetsregisteret/api/underenheter/{org}", check_robots=False)
        main_org = json.loads(r.body).get("overordnetEnhet") if r.ok else org
        r2 = await c.get("brreg", f"https://data.brreg.no/enhetsregisteret/api/enheter/{main_org}", check_robots=False)
        if not r2.ok:
            continue
        ent = json.loads(r2.body)
        if (ent.get("organisasjonsform") or {}).get("kode") not in ("AS", "ASA", "ENK", "NUF", "SA", "DA", "ANS"):
            continue  # the challenge universe is companies, not municipalities
        labels.setdefault(main_org, set()).add(u)
        if len(labels) >= n:
            break
    with open(out, "w", encoding="utf-8") as fh:
        for org, ads in labels.items():
            fh.write(json.dumps({"organisation_number": org, "expected_nav_ads": sorted(ads)}) + "\n")
    print(len(labels), "companies written")
    await c.close()

asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
