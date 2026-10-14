"""How does data.brreg.no respond under parallel load? (status counts and latency)"""
import asyncio
import collections
import json
import sys
import time

import httpx


async def main(conc: int, n: int) -> None:
    orgs = [json.loads(l)["organisation_number"] for l in open("eval/dev-1000.jsonl", encoding="utf-8")][:n]
    sem = asyncio.Semaphore(conc)
    stats = collections.Counter()
    lat = []
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "KildesporBot/1.0"}) as c:
        async def one(o: str) -> None:
            async with sem:
                t = time.monotonic()
                r = await c.get(f"https://data.brreg.no/enhetsregisteret/api/enheter/{o}/roller")
                lat.append(time.monotonic() - t)
                stats[r.status_code] += 1
                if r.status_code == 429:
                    stats["retry-after=" + str(r.headers.get("retry-after") or r.headers.get("x-rate-limit-retry-after-seconds"))] += 1
        t0 = time.monotonic()
        await asyncio.gather(*(one(o) for o in orgs))
    lat.sort()
    print(f"conc={conc} n={n} wall={time.monotonic() - t0:.1f}s p50={lat[len(lat) // 2]:.2f}s p95={lat[int(len(lat) * .95)]:.2f}s", dict(stats))


asyncio.run(main(int(sys.argv[1]), int(sys.argv[2])))
