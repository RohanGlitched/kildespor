"""Buyer brief: the one fact a buyer would want first, then a short paragraph that says what the company does, how it
is doing, what changed and what is still unknown, each sentence naming its source.

Nothing here is new information: every sentence is computed from claims already in the profile, and lists them.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .claims import Claim, Profile
from .synthesis import _amt, _fin, _pct, explained_unknowns, financial_conclusions, fold_name, nok, profile_line

SERIOUS = ("bankrupt", "wound up", "dissolution", "liquidat", "konkurs", "avvikling", "tvangsoppl")
CHANGE_FIELDS = ("roles_changed", "renamed", "articles_changed", "share_capital_changed", "public_contract_award", "state_aid_award",
                 "food_inspection", "company_news")


def source_label(e) -> str:
    u = e.source_url or ""
    host = (u.split("/")[2] if "//" in u else u).removeprefix("www.")
    if "regnskapsregisteret" in u:
        return "Brønnøysund annual accounts"
    if "enhetsregisteret" in u:
        return "Brønnøysund register"
    if "arbeidsplassen" in u or host.endswith("nav.no") or e.source_class == "public_job_board":
        return "NAV job board"
    if e.source_class == "company_owned":
        return host
    return e.source_name or host


def sources_for(p: Profile, keys: list[str], limit: int = 3) -> list[dict[str, str]]:
    by_key = {c.key: c for c in p.claims}
    out: dict[str, dict[str, str]] = {}
    for k in keys:
        c = by_key.get(k)
        if not c or not c.evidence:
            continue
        e = c.evidence[0]
        name = source_label(e)
        out.setdefault(name, {"name": name, "url": e.source_url})
        if len(out) >= limit:
            break
    return list(out.values())


def _src(p: Profile, keys: list[str]) -> str:
    names = [s["name"] for s in sources_for(p, keys, 2)]
    return f" ({'; '.join(names)})" if names else ""


def _days_ago(d: str | None, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(str(d)[:10])).days
    except ValueError:
        return None


ROLE_EN = {"daglig leder": "general manager", "styre": "board", "regnskapsfører": "accountant", "revisor": "auditor",
           "kontaktperson": "contact person", "innehaver": "owner", "deltakere": "partners", "komplementar": "general partner",
           "norsk representant for utenlandsk enhet": "Norwegian representative", "bestyrende reder": "managing owner",
           "forretningsfører": "business manager", "prokura": "power of procuration", "signatur": "signing authority",
           "varamedlem": "deputy board member", "styreleder": "chair of the board"}


def _title(c: Claim) -> str:
    t = str((c.value or {}).get("title") if isinstance(c.value, dict) else c.label)
    if c.field == "share_capital_changed":
        m = re.search(r"([\d.]+)\s*([A-Z]{3})?", t.split(":", 1)[-1])
        if m:
            try:
                return f"share capital registered: {m.group(2) or 'NOK'} {float(m.group(1)):,.0f}"
            except ValueError:
                pass
    if c.field == "articles_changed":
        return "articles of association updated"
    if c.field == "roles_changed":
        m = re.match(r"(.+?) registered$", t)
        if m and m.group(1).lower() in ROLE_EN:
            return f"new {ROLE_EN[m.group(1).lower()]} registered"
    return t


def buyer_facts(p: Profile, today: date | None = None) -> list[tuple[int, str, list[str]]]:
    """Candidate lead facts, highest priority first: (priority, sentence without final stop, claim keys)."""
    today = today or date.today()
    out: list[tuple[int, str, list[str]]] = []
    flags = next((c for c in p.family_claims("identity") if c.field == "registry_flags"), None)
    if flags and isinstance(flags.value, list):
        serious = [x for x in flags.value if any(w in str(x).lower() for w in SERIOUS)]
        if serious:
            out.append((100, f"Risk: the register flags {', '.join(map(str, serious))}", [flags.key]))
    jobs = [c for c in p.family_claims("jobs") if c.field == "job_posting" and (c.value or {}).get("status", "open") != "closed"]
    if jobs:
        jobs.sort(key=lambda c: c.effective_date or "", reverse=True)
        titles = [str((c.value or {}).get("title") or "") for c in jobs][:2]
        t = f"Hiring now: {len(jobs)} open position{'s' if len(jobs) != 1 else ''}"
        if any(titles):
            t += " (" + "; ".join(f"“{x}”" for x in titles if x) + ")"
        if jobs[0].effective_date:
            t += f", latest posted {jobs[0].effective_date}"
        out.append((90, t, [c.key for c in jobs[:4]]))
    f = _fin(p)
    years = sorted({y for (_, y) in f}, key=int)
    if years:
        y = years[-1]
        py = str(int(y) - 1)
        eq = f.get(("equity", y))
        if eq and _amt(eq) is not None and _amt(eq) < 0:
            big = abs(_amt(eq)) >= max(500_000, 0.05 * (_amt(f.get(("revenue", y))) or 0))
            out.append((85 if big else 45, f"Negative equity of {nok(_amt(eq))} at the end of {y}, so liabilities exceed assets", [eq.key]))
        rev, prev = f.get(("revenue", y)), f.get(("revenue", py))
        a, b = _amt(rev), _amt(prev)
        if a is not None and b and b > 0 and max(a, b) >= 1e6 and abs(a / b - 1) >= 0.25:
            word = "up" if a > b else "down"
            out.append((80, f"Revenue {word} {abs(a / b - 1) * 100:.0f}% to {nok(a)} in {y}, from {nok(b)} in {py}", [rev.key, prev.key]))
        res, pres = f.get(("annual_result", y)), f.get(("annual_result", py))
        if res and pres and (_amt(res) >= 0) != (_amt(pres) >= 0) and max(abs(_amt(res)), abs(_amt(pres))) >= 1e5:
            turn = "a profit" if _amt(res) >= 0 else "a loss"
            out.append((75, f"Turned to {turn} in {y}: annual result {nok(_amt(res))} after {nok(_amt(pres))} in {py}", [res.key, pres.key]))
    news = sorted([c for c in p.family_claims("activity") if c.field == "company_news" and c.effective_date],
                  key=lambda c: c.effective_date, reverse=True)
    if news:
        age = _days_ago(news[0].effective_date, today)
        if age is not None and 0 <= age <= 180:
            out.append((70, f"Latest news on its own website ({news[0].effective_date}): “{_title(news[0])}”", [news[0].key]))
    for c in sorted(p.family_claims("activity"), key=lambda c: c.effective_date or "", reverse=True):
        age = _days_ago(c.effective_date, today)
        if age is None or age < 0 or age > 365:
            continue
        title = _title(c)
        if c.field == "public_contract_award":
            out.append((68, f"Won a public contract ({c.effective_date}): {title.replace('Public contract award: ', '')}", [c.key]))
            break
        if c.field == "roles_changed" and re.search(r"general manager|owner|chair", title, re.I):
            out.append((66, f"Leadership change: {title} on {c.effective_date}", [c.key]))
            break
        if c.field == "roles_changed" and re.search(r"board", title, re.I):
            out.append((38, f"Board change: {title} on {c.effective_date}", [c.key]))
            break
        if c.field == "renamed":
            out.append((65, f"{title} on {c.effective_date}", [c.key]))
            break
    if years:
        y = years[-1]
        rev, op, assets = f.get(("revenue", y)), f.get(("operating_result", y)), f.get(("total_assets", y))
        if rev and _amt(rev):
            t, keys = f"{nok(_amt(rev))} revenue in {y}", [rev.key]
            if op:
                t += f" at an operating margin of {_pct(_amt(op) / _amt(rev))}"
                keys.append(op.key)
            out.append((40, t, keys))
        elif assets and _amt(assets):
            out.append((35, f"No revenue filed for {y} and total assets of {nok(_amt(assets))}, so it reads as a holding or "
                             "asset-owning company", [assets.key]))
    else:
        founded = next((c for c in p.family_claims("identity") if c.field == "founded"), None)
        t = "No annual accounts found in the register"
        if founded:
            t += f" (founded {str(founded.value)[:10]})"
        out.append((30, t, [founded.key] if founded else []))
    out.sort(key=lambda x: -x[0])
    return out


def what_changed(p: Profile, changes: list[dict] | None, today: date | None = None,
                 used: set[str] | None = None) -> tuple[str, list[str]]:
    today = today or date.today()
    used = used or set()
    if changes:
        kinds = sorted({str(ch.get("type") or ch.get("field") or "change").replace("_", " ") for ch in changes if isinstance(ch, dict)})
        return (f"Since the previous run, {len(changes)} material change{'s were' if len(changes) != 1 else ' was'} detected"
                + (f" ({', '.join(kinds[:4])})" if kinds else "") + ".", [])
    recent = [c for c in p.family_claims("activity") if c.field in CHANGE_FIELDS
              and (lambda a: a is not None and 0 <= a <= 365)(_days_ago(c.effective_date, today))]
    if not recent:
        return "No register changes, public awards or dated company news in the last 12 months.", []
    rest = [c for c in recent if c.key not in used]
    if not rest:
        return "Nothing else changed in the register in the last 12 months.", []
    recent = rest
    recent.sort(key=lambda c: c.effective_date, reverse=True)
    groups: dict[str, list[Claim]] = {}
    for c in recent:
        title = "state aid or a tax exemption received" if c.field == "state_aid_award" else _title(c)
        groups.setdefault(title, []).append(c)
    bits = [f"{t} ({cs[0].effective_date})" if len(cs) == 1 else f"{t} ×{len(cs)}, latest {cs[0].effective_date}"
            for t, cs in list(groups.items())[:3]]
    return "In the last 12 months: " + "; ".join(bits) + ".", [cs[0].key for cs in list(groups.values())[:3]]


FUNCTION_WORDS = {"og", "er", "vi", "til", "for", "med", "i", "på", "av", "som", "en", "et", "har", "den", "det", "fra", "innen",
                  "and", "we", "the", "is", "of", "to", "in", "with", "our", "for", "a", "an"}
NAV_WORDS = re.compile(r"\b(hjem|meny|kontakt oss|om oss|logg inn|bestill time|handlekurv|aktuelt|forside|cookies?)\b", re.I)


def prose(text: str) -> bool:
    """A self-description worth quoting reads like a sentence, not a menu or a list of keywords."""
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < 6:
        return False
    if sum(w in FUNCTION_WORDS for w in words) < 2:
        return False
    return len(NAV_WORDS.findall(text)) < 2


def what_it_does(p: Profile) -> tuple[str, list[str]]:
    prof = profile_line(p)
    base = prof["text"].removeprefix("In plain terms: ").rstrip(".") if prof else ""
    keys = list(prof["claim_keys"]) if prof else []
    if base:
        base = base[0].upper() + base[1:] + "."
    desc = next((c for c in p.family_claims("description") if c.field in ("site_description", "about_page") and prose(str(c.value))), None)
    if desc:
        q = " ".join(str(desc.value).split())
        if len(q) > 200:
            q = q[:200].rsplit(" ", 1)[0] + "…"
        site = source_label(desc.evidence[0]) if desc.evidence else "its website"
        return (base + " " if base else "") + f"Its own website ({site}) says: “{q}”", keys + [desc.key]
    purpose = next((c for c in p.family_claims("description") if c.field == "registered_purpose"), None)
    if purpose:
        q = " ".join(str(purpose.value).split())
        if len(q) > 160:
            q = q[:160].rsplit(" ", 1)[0] + "…"
        return (base + " " if base else "") + f"Its registered purpose (Brønnøysund register): “{q}”", keys + [purpose.key]
    return base, keys


def health(p: Profile, skip_margin: bool = False, used: set[str] | None = None) -> tuple[str, list[str]]:
    used = used or set()
    concl = [x for x in financial_conclusions(p) if x["topic"] == "assessment"
             and not (skip_margin and x["text"].startswith("Operating margin"))
             and not (set(x["claim_keys"]) <= used or len(set(x["claim_keys"]) & used) >= 2)]
    picked = concl[:2]
    return " ".join(x["text"].rstrip(".") + "." for x in picked), [k for x in picked for k in x["claim_keys"]]


UNKNOWN_NAMES = {"website": "a website tied to this exact company", "social": "company-owned social profiles",
                 "jobs": "open job postings", "activity": "dated news", "financials": "filed annual accounts",
                 "reviews": "customer ratings"}


def unknowns_line(p: Profile) -> str:
    miss = [x for x in explained_unknowns(p) if x["family"] in UNKNOWN_NAMES]
    if not miss:
        return ""
    unsure = [UNKNOWN_NAMES[x["family"]] for x in miss if x["state"] in ("blocked", "ambiguous", "failed")]
    absent = [UNKNOWN_NAMES[x["family"]] for x in miss if x["state"] not in ("blocked", "ambiguous", "failed")]
    bits = []
    if absent:
        bits.append("Checked but not found: " + ", ".join(absent) + ".")
    if unsure:
        bits.append("Unknown because the source was blocked or the match was not certain: " + ", ".join(unsure) + ".")
    return " ".join(bits)


def _sentence(text: str, src: str) -> str:
    text = text.strip()
    if text.endswith("”"):
        return text + src + "."
    return text.rstrip(".") + src + "."


def brief(p: Profile, changes: list[dict] | None = None, today: date | None = None) -> dict[str, Any]:
    facts = buyer_facts(p, today)
    lead = facts[0] if facts else None
    parts: list[str] = []
    headline = fold_name(p).upper() or p.orgnr
    used: set[str] = set()
    if lead:
        headline = _sentence(lead[1], _src(p, lead[2]))
        parts.append(headline)
        used |= set(lead[2])
        second = next((x for x in facts[1:] if x[0] >= 65 and not set(x[2]) & used), None)
        if second:
            parts.append(_sentence(second[1], _src(p, second[2])))
            used |= set(second[2])
    wid, wkeys = what_it_does(p)
    if wid:
        parts.append(wid if wid.endswith(".") else _sentence(wid, ""))
    h, hkeys = health(p, skip_margin=bool(lead and lead[0] == 40), used=used)
    if h:
        parts.append(_sentence(h, _src(p, hkeys)))
    ch, ckeys = what_changed(p, changes, today, used)
    parts.append(_sentence(ch, _src(p, ckeys)) if ckeys else ch)
    unk = unknowns_line(p)
    if unk:
        parts.append(unk)
    return {"headline": headline, "text": " ".join(parts), "what_it_does": wid, "what_changed": ch,
            "lead_fact": {"text": lead[1], "claim_keys": lead[2], "sources": sources_for(p, lead[2])} if lead else None}
