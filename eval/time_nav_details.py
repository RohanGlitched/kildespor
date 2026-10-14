import asyncio
import sys
import time

sys.path.insert(0, ".")
from kildespor.agent import Context  # noqa: E402
from kildespor.discovery import Resolver  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.sources.nav_jobs import NavJobs  # noqa: E402


async def main(conc: int, n: int):
    c = Client(64)
    ctx = Context(c, Resolver())
    nav = NavJobs(window_days=3)
    t = time.time()
    await nav.prepare(ctx, [])
    print("prepare", round(time.time() - t, 1), nav.report())
    nav.sem = asyncio.Semaphore(conc)
    act = [u for u, e in nav.ads.items() if e.get("status") == "ACTIVE"][:n]
    t = time.time()
    res = await asyncio.gather(*(nav._detail(ctx, u) for u in act))
    dt = time.time() - t
    ok = sum(1 for d, f in res if d)
    print(f"{len(act)} details, {ok} ok, {dt:.1f}s, {len(act) / dt:.1f}/s at concurrency {conc}")
    await c.close()

asyncio.run(main(int(sys.argv[1]), int(sys.argv[2])))
