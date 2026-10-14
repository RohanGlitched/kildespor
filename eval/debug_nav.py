import asyncio
import json
import sys

sys.path.insert(0, ".")
from kildespor.agent import Context  # noqa: E402
from kildespor.discovery import Resolver  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.sources.nav_jobs import NavJobs, _sig  # noqa: E402


async def main():
    c = Client(16)
    ctx = Context(c, Resolver())
    nav = NavJobs(window_days=6)
    await nav.prepare(ctx, [])
    print(nav.report())
    act = [u for u, e in nav.ads.items() if e.get("status") == "ACTIVE"][:5]
    for u in act:
        d, f = await nav._detail(ctx, u)
        ad = (d or {}).get("ad_content") or {}
        print(nav.ads[u].get("businessName"), "|", json.dumps(ad.get("employer"), ensure_ascii=False)[:300])
    # company names in the feed vs legal names
    names = [e.get("businessName") for e in nav.ads.values()][:30]
    print(names)
    await c.close()

asyncio.run(main())
