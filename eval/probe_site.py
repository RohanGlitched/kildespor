"""Debug: crawl one domain for one orgnr and show what identity signals the pages carry."""
import asyncio
import json
import sys
import urllib.request

sys.path.insert(0, ".")
from kildespor import siteparse as sp  # noqa: E402
from kildespor.discovery import Candidate  # noqa: E402
from kildespor.http import Client  # noqa: E402
from kildespor.site import crawl, verify  # noqa: E402
from kildespor.util import fold  # noqa: E402


async def main(orgnr: str, domain: str) -> None:
    ent = json.loads(urllib.request.urlopen(f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}").read())
    print(ent["navn"], ent.get("forretningsadresse"), ent.get("telefon"), ent.get("mobil"), ent.get("epostadresse"))
    c = Client(8)
    res = await crawl(c, Candidate(domain, "name_derived"))
    res = verify(res, ent, [], orgnr)
    print("STATUS", res.status, res.reason)
    for p in res.pages:
        print("--", p.final_url, "|", p.title[:80], "| site_name:", p.site_name, "| words", len(p.text.split()))
        print("   orgnrs", sp.orgnr_mentions(p.text)[:3])
        print("   phones", sp.phones(p)[:4])
        print("   emails", sp.emails(p)[:4])
        name = fold(ent["navn"])
        print("   legal name present:", name in fold(p.text), "| municipality present:", fold(ent["forretningsadresse"]["kommune"]) in fold(p.text))
    await c.close()


asyncio.run(main(sys.argv[1], sys.argv[2]))
