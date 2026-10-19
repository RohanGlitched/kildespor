"""Debug the careers source for one organisation number without the NAV index.

python eval/debug_careers.py 913961471
Prints every recruitment target found on the verified site, every posting read, and why each was kept or skipped.
"""
import asyncio
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from kildespor.agent import Context, research  # noqa: E402
from kildespor.claims import Profile  # noqa: E402
from kildespor.discovery import Resolver  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.sources import careers as cs  # noqa: E402


async def main(orgnr: str) -> None:
    c = Client(16)
    ctx = Context(c, Resolver(), [])
    p = Profile(orgnr)
    await research(ctx, orgnr, p, {})
    ent, subunits, exact, _, _ = p.notes.pop("late_args")
    print(ent.get("navn"), "sites:", [s.home.final_url for s in exact])
    for s in exact:
        print("  pages:", [pg.final_url for pg in s.pages])
    src = cs.Careers()
    who = cs.Who(ent, subunits, orgnr)
    found: list = []
    orig_read = src._read

    async def read(ctx_, t, found_):
        print("TARGET", t.platform, t.url[:120], "via", t.via.get("url"))
        await orig_read(ctx_, t, found_)
    src._read = read
    await src._collect(ctx, who, exact, found)
    for post, via, f in found:
        name = post.employer or post.extra.get("account")
        print(f"  {'MATCH' if who.match(name) or (post.orgnr in who.own) else 'skip '} {post.platform:10} {name!r:40} "
              f"{post.title[:60]!r} {post.published} due {post.deadline} {post.country} {post.url[:90]}")
    src._publish(p, who, found)
    print(src.report())
    await c.close()


asyncio.run(main(sys.argv[1]))
