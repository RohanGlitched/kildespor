"""Website candidates for one legal entity.

Candidates come from what the entity itself declared to the register (website field, e-mail
domain, subunit websites and e-mails) and from domains derived from the legal name. A candidate
is never evidence: the site must prove it belongs to this entity (identity.py).
"""
from __future__ import annotations

import asyncio
import itertools
import socket
import re
from dataclasses import dataclass

import dns.asyncresolver
import dns.exception
import dns.resolver

from .util import fold, name_tokens

FREEMAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.no", "outlook.com", "outlook.no", "live.com", "live.no",
    "msn.com", "yahoo.com", "yahoo.no", "icloud.com", "me.com", "mac.com", "online.no", "frisurf.no", "start.no",
    "c2i.net", "broadpark.no", "getmail.no", "altibox.no", "lyse.net", "tele2.no", "chello.no", "ebnett.no",
    "eunet.no", "netcom.no", "telia.no", "telenor.no", "mail.com", "protonmail.com", "proton.me", "aol.com",
    "sensewave.com", "bluezone.no", "nextgentel.com", "tdcadsl.no", "loqal.no", "haugnett.no", "enivest.net",
    "gmx.com", "gmx.net", "email.com", "inbox.com", "yandex.com", "abc.no", "kvinesdal.net", "vikenfiber.no",
    "outlook.dk", "hotmail.se", "hotmail.dk", "live.se", "yahoo.se", "tussa.com", "svorka.net", "mimer.no",
    "neasonline.no", "trollfjordbredband.no", "nordnet.no", "online.net", "privat.no", "epost.no", "post.com",
}
# words that rarely form part of a brand domain on their own
GENERIC = {"og", "and", "the", "holding", "holdings", "invest", "investering", "eiendom", "eiendommer", "norge", "norway",
           "group", "gruppen", "konsern", "drift", "service", "services", "consulting", "as", "asa", "i", "pa", "av", "for",
           "til", "med", "nordic", "norden", "international", "company", "firma"}
DEV_DOMAINS = re.compile(r"(wixsite\.com|wordpress\.com|blogspot\.|squarespace\.com|webflow\.io|godaddysites\.com|one\.com$)")


@dataclass(frozen=True)
class Candidate:
    domain: str
    origin: str  # registry_website | registry_email | subunit_website | subunit_email | name_derived
    detail: str = ""

    @property
    def declared(self) -> bool:
        return self.origin != "name_derived"


def domain_of(value: str) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    if "@" in v:
        v = v.split("@")[-1]
    v = v.strip(". ")
    if v.startswith("www."):
        v = v[4:]
    return v if re.fullmatch(r"[a-z0-9æøå.-]+\.[a-z]{2,}", v) else ""


HOSTED = ("weebly.com", "wixsite.com", "wordpress.com", "blogspot.com", "squarespace.com", "webflow.io", "github.io",
          "netlify.app", "vercel.app", "business.site", "mystrikingly.com", "jimdofree.com", "jimdosite.com", "one.com",
          "teamtailor.com", "shopify.com", "myshopify.com", "carrd.co", "simplesite.com", "123hjemmeside.no", "hjemmeside.no")
SHARED_MAIL = {"styrerommet.no", "vibbo.no", "obos.no", "boligbygg.no", "usbl.no", "nordbohus.no", "bate.no", "bori.no",
               "tobb.no", "ibo.no", "boligpartner.no", "regnskapshuset.no", "azets.com", "visma.com", "eika.no"}


def registrable(domain: str) -> str:
    domain = (domain or "").lower().strip(".")
    for h in HOSTED:
        if domain.endswith("." + h):
            sub = domain[: -len(h) - 1].split(".")[-1]
            return f"{sub}.{h}"
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "priv") and parts[-1] in ("no", "uk", "se"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def idna(label: str) -> str:
    try:
        return label.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def name_domains(name: str, limit: int = 14) -> list[str]:
    """Plausible .no/.com domains for a legal name, most likely first."""
    raw = (name or "").lower().replace("&", " og ")
    raw_tokens = re.findall(r"[a-z0-9æøå]+", raw)
    while raw_tokens and fold(raw_tokens[-1]) in {"as", "asa", "ans", "da", "sa", "ba", "nuf", "sti", "ks", "sp"}:
        raw_tokens.pop()
    toks = name_tokens(name)
    if not toks:
        return []
    core = [t for t in toks if t not in GENERIC] or toks
    labels: list[str] = []

    def add(label: str) -> None:
        label = label.strip("-")
        if 2 <= len(label) <= 63 and label not in labels and not label.isdigit():
            labels.append(label)

    add("".join(toks))
    add("-".join(toks))
    if core != toks:
        add("".join(core))
        add("-".join(core))
    if "og" in toks:
        add("".join(t for t in toks if t != "og"))
        add("-".join(t for t in toks if t != "og"))
    # oe/aa spellings
    alt = [fold(t).replace("o", "o") for t in toks]
    add("".join(t.replace("ae", "ae") for t in alt))
    oe = [re.sub("ø", "oe", re.sub("å", "aa", t)) for t in raw_tokens]
    add("".join(fold(t) for t in oe))
    # native IDN
    native = "".join(raw_tokens)
    if re.search("[æøå]", native):
        puny = idna(native)
        if puny:
            add(puny)
    if len(core) >= 2:
        add("".join(core[:2]))
        add("-".join(core[:2]))
    if len(core) >= 1 and len(core[0]) >= 5:
        add(core[0])
    out = [lab + ".no" for lab in labels]
    out += [lab + ".com" for lab in labels[:3]]
    return out[:limit]


def candidates(ent: dict, subunits: list[dict]) -> list[Candidate]:
    found: dict[str, Candidate] = {}

    def put(domain: str, origin: str, detail: str) -> None:
        if not domain or DEV_DOMAINS.search(domain):
            return
        reg = registrable(domain)
        if reg in FREEMAIL or domain in FREEMAIL or (reg in SHARED_MAIL and origin.endswith("email")):
            return
        key = domain if origin == "registry_website" else reg
        if key not in found:
            found[key] = Candidate(key, origin, detail)

    if ent.get("hjemmeside"):
        put(domain_of(ent["hjemmeside"]), "registry_website", ent["hjemmeside"])
    if ent.get("epostadresse"):
        put(domain_of(ent["epostadresse"]), "registry_email", ent["epostadresse"])
    for u in subunits:
        if u.get("hjemmeside"):
            put(domain_of(u["hjemmeside"]), "subunit_website", u["hjemmeside"])
        if u.get("epost"):
            put(domain_of(u["epost"]), "subunit_email", u["epost"])
    for d in name_domains(ent.get("navn", "")):
        put(d, "name_derived", ent.get("navn", ""))
    return list(found.values())


PUBLIC_DNS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]


class Resolver:
    """DNS existence checks. Configured nameservers that do not answer are dropped at start-up
    (stale adapters are common) and public resolvers are kept as a fallback; if dnspython cannot
    answer at all, the operating system's resolver is used."""

    def __init__(self, concurrency: int = 64) -> None:
        self.r = dns.asyncresolver.Resolver()
        self.r.lifetime = 3.0
        self.r.timeout = 1.5
        self.sem = asyncio.Semaphore(concurrency)
        self.cache: dict[str, bool] = {}
        self.ready = False
        self.lock = asyncio.Lock()
        self.system_fallback = False

    async def _init(self) -> None:
        async with self.lock:
            if self.ready:
                return
            async def probe(ns: str) -> str | None:
                r = dns.asyncresolver.Resolver(configure=False)
                r.nameservers = [ns]
                try:
                    await r.resolve("brreg.no", "A", lifetime=2.0)
                    return ns
                except dns.exception.DNSException:
                    return None
            servers = list(dict.fromkeys(list(self.r.nameservers) + PUBLIC_DNS))
            good = [ns for ns in await asyncio.gather(*(probe(ns) for ns in servers)) if ns]
            if good:
                self.r.nameservers = good
            else:
                self.system_fallback = True
            self.ready = True

    async def exists(self, domain: str) -> bool:
        if not self.ready:
            await self._init()
        if domain in self.cache:
            return self.cache[domain]
        ok = False
        async with self.sem:
            if self.system_fallback:
                for host in (domain, "www." + domain):
                    try:
                        await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, host, 443), 4)
                        ok = True
                        break
                    except (OSError, asyncio.TimeoutError):
                        continue
            else:
                for host, rtype in itertools.product((domain, "www." + domain), ("A", "AAAA")):
                    try:
                        await self.r.resolve(host, rtype)
                        ok = True
                        break
                    except dns.resolver.NXDOMAIN:
                        if rtype == "A":
                            break  # the name does not exist: no point asking for AAAA
                    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout,
                            dns.name.LabelTooLong, dns.name.EmptyLabel, ValueError):
                        continue
                    except dns.exception.DNSException:
                        continue
        self.cache[domain] = ok
        return ok
