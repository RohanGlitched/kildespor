"""Decision-useful conclusions drawn only from claims already in the profile.

Every conclusion lists the claim keys it rests on and, for a computed figure, the formula. Nothing is
inferred that the cited claims do not show; thresholds are stated in the text so a reader can disagree.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from .claims import FAMILIES, Claim, Profile

FIN_FIELDS = ("revenue", "operating_result", "annual_result", "profit_before_tax", "payroll_cost", "total_assets",
              "equity", "total_debt", "cash")
UNKNOWN_TEXT = {
    "website": "no website could be tied to this exact company",
    "social": "no company-owned social profile was found",
    "contact": "no public contact details beyond the register",
    "jobs": "no open job postings were found",
    "reviews": "no customer rating was found",
    "activity": "no dated public activity was found",
    "description": "no description of the business was found",
    "people": "no registered roles were found",
    "locations": "no registered workplaces were found",
    "financials": "no filed annual accounts were found",
}


def nok(v: float | int | None) -> str:
    if v is None:
        return "—"
    v = float(v)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e9:
        return f"{sign}NOK {v / 1e9:.1f} bn"
    if v >= 1e6:
        return f"{sign}NOK {v / 1e6:.1f} m"
    if v >= 1e3:
        return f"{sign}NOK {v / 1e3:.0f} k"
    return f"{sign}NOK {v:.0f}"


def _fin(p: Profile) -> dict[tuple[str, str], Claim]:
    out: dict[tuple[str, str], Claim] = {}
    for c in p.family_claims("financials"):
        if c.field in FIN_FIELDS and isinstance(c.value, dict) and c.value.get("amount") is not None and c.value.get("year"):
            out.setdefault((c.field, str(c.value["year"])), c)
    return out


def _amt(c: Claim | None) -> float | None:
    return float(c.value["amount"]) if c else None


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def financial_conclusions(p: Profile) -> list[dict[str, Any]]:
    f = _fin(p)
    years = sorted({y for (_, y) in f}, key=int)
    if not years:
        return []
    out: list[dict[str, Any]] = []
    y = years[-1]
    get = lambda field, yr=y: f.get((field, yr))  # noqa: E731

    # trend over every filed year we hold
    revs = [(yr, f[("revenue", yr)]) for yr in years if ("revenue", yr) in f]
    if len(revs) >= 2:
        (y0, c0), (y1, c1) = revs[0], revs[-1]
        a0, a1 = _amt(c0), _amt(c1)
        n = int(y1) - int(y0)
        if a0 and a0 > 0 and a1 is not None and a1 >= 0 and n >= 1:
            cagr = (a1 / a0) ** (1 / n) - 1
            if abs(a1 / a0 - 1) < 0.02 * n:
                text = f"Revenue was roughly flat at about {nok(a1)} from {y0} to {y1}."
            else:
                direction = "grew" if a1 > a0 else "fell"
                text = f"Revenue {direction} from {nok(a0)} ({y0}) to {nok(a1)} ({y1})"
                text += f", {cagr * 100:+.0f}% a year." if n > 1 else f" ({(a1 / a0 - 1) * 100:+.0f}%)."
            out.append({"topic": "assessment", "text": text, "claim_keys": [c.key for _, c in revs],
                        "method": "compound annual growth = (last / first) ^ (1 / years) − 1" if n > 1 else "change = last / first − 1"})

    # profitability, latest year, and whether it turned
    rev, op, res = get("revenue"), get("operating_result"), get("annual_result")
    if rev and op and _amt(rev):
        margin = _amt(op) / _amt(rev)
        word = "loss-making" if margin < 0 else "thin" if margin < 0.03 else "healthy" if margin >= 0.08 else "modest"
        text = f"Operating margin {_pct(margin)} in {y} ({word}: operating result {nok(_amt(op))} on revenue {nok(_amt(rev))})."
        out.append({"topic": "assessment", "text": text, "claim_keys": [op.key, rev.key],
                    "method": "operating margin = operating result / revenue; thin < 3%, healthy ≥ 8%"})
    res_years = [(yr, f[("annual_result", yr)]) for yr in years if ("annual_result", yr) in f]
    if len(res_years) >= 2:
        signs = ["profit" if _amt(c) >= 0 else "loss" for _, c in res_years]
        if signs[-1] != signs[-2]:
            out.append({"topic": "assessment",
                        "text": f"The annual result turned from a {signs[-2]} in {res_years[-2][0]} to a {signs[-1]} in {res_years[-1][0]} "
                                f"({nok(_amt(res_years[-2][1]))} → {nok(_amt(res_years[-1][1]))}).",
                        "claim_keys": [res_years[-2][1].key, res_years[-1][1].key]})
        elif len(signs) >= 3 and all(s == "loss" for s in signs[-3:]):
            out.append({"topic": "assessment", "text": f"Losses in each of the last three filed years ({', '.join(yr for yr, _ in res_years[-3:])}).",
                        "claim_keys": [c.key for _, c in res_years[-3:]]})

    # balance sheet
    eq, assets, debt, cash = get("equity"), get("total_assets"), get("total_debt"), get("cash")
    if eq and assets and _amt(assets):
        ratio = _amt(eq) / _amt(assets)
        if _amt(eq) < 0:
            word = "negative equity: liabilities exceed assets"
        elif ratio < 0.1:
            word = "thin buffer"
        elif ratio >= 0.4:
            word = "solid"
        else:
            word = "moderate"
        out.append({"topic": "assessment", "text": f"Equity ratio {_pct(ratio)} at the end of {y} ({word}; equity {nok(_amt(eq))} of total assets {nok(_amt(assets))}).",
                    "claim_keys": [eq.key, assets.key], "method": "equity ratio = equity / total assets; thin < 10%, solid ≥ 40%"})
    if cash and debt and _amt(debt) and _amt(cash) is not None and _amt(cash) >= _amt(debt):
        out.append({"topic": "assessment", "text": f"Cash ({nok(_amt(cash))}) covered all debt ({nok(_amt(debt))}) at the end of {y}.",
                    "claim_keys": [cash.key, debt.key]})
    pay = get("payroll_cost")
    if pay and rev and _amt(rev) and _amt(pay) and _amt(pay) / _amt(rev) >= 0.5:
        out.append({"topic": "assessment", "text": f"Labour-intensive: payroll was {_pct(_amt(pay) / _amt(rev))} of revenue in {y}.",
                    "claim_keys": [pay.key, rev.key], "method": "payroll cost / revenue"})
    if not _amt(rev) and assets and _amt(assets) and not any(c.field == "job_posting" for c in p.family_claims("jobs")):
        out.append({"topic": "assessment", "text": f"No revenue was filed for {y}; with total assets of {nok(_amt(assets))} this reads as a holding or "
                                                   "asset-owning company rather than an operating business.",
                    "claim_keys": [assets.key]})
    return out


def change_conclusions(p: Profile, today: date | None = None) -> list[dict[str, Any]]:
    """Material register events in the last 12 months (the refresh diff covers changes between runs)."""
    today = today or date.today()
    cutoff = date(today.year - 1, today.month, min(today.day, 28)).isoformat()
    picked = []
    for c in p.family_claims("activity"):
        if c.field in ("roles_changed", "renamed", "articles_changed", "share_capital_changed", "public_contract_award", "state_aid_award",
                       "food_inspection") and (c.effective_date or "") >= cutoff:
            picked.append(c)
    if not picked:
        return []
    picked.sort(key=lambda c: c.effective_date or "", reverse=True)
    groups: dict[str, list[Claim]] = {}
    for c in picked:  # repeated events (monthly tax exemptions) are one line with a count
        title = c.value.get("title") if isinstance(c.value, dict) else c.label
        groups.setdefault(str(title), []).append(c)
    bits, keys = [], []
    for title, cs in list(groups.items())[:4]:
        bits.append(f"{title} ({cs[0].effective_date})" if len(cs) == 1 else f"{title} ×{len(cs)}, latest {cs[0].effective_date}")
        keys += [c.key for c in cs[:3]]
    return [{"topic": "recent_changes", "text": "In the last 12 months: " + "; ".join(bits) + ".", "claim_keys": keys}]


def flag_conclusions(p: Profile) -> list[dict[str, Any]]:
    flags = next((c for c in p.family_claims("identity") if c.field == "registry_flags"), None)
    if not flags or not isinstance(flags.value, list):
        return []
    serious = [x for x in flags.value if any(w in x.lower() for w in ("bankrupt", "wound up", "dissolution"))]
    if serious:
        return [{"topic": "risk", "text": "The register flags: " + ", ".join(serious) + ".", "claim_keys": [flags.key]}]
    return []


def explained_unknowns(p: Profile) -> list[dict[str, str]]:
    out = []
    for fam in FAMILIES:
        if p.family_claims(fam):
            continue
        st = p.states.get(fam)
        out.append({"family": fam, "state": st.state if st else "not_available",
                    "text": (st.note if st and st.note else UNKNOWN_TEXT.get(fam, "nothing was found"))})
    return out


INDUSTRY_EN: dict[str, str] = {}


async def load_industry_names(client) -> None:
    """English names of Norwegian industry codes (SSB Klass, classification 6, NLOD): one request per run."""
    url = f"https://data.ssb.no/api/klass/v1/classifications/6/codes?from={date.today().isoformat()}&language=en"
    f = await client.get("ssb_klass", url, headers={"Accept": "application/json"}, check_robots=False, retries=1)
    if not f.ok:
        return
    try:
        for c in json.loads(f.body).get("codes", []):
            INDUSTRY_EN[str(c.get("code"))] = str(c.get("name") or "")
    except ValueError:
        return


def industry_en(industry_value: str) -> str:
    code = str(industry_value or "").split(" ", 1)[0]
    return INDUSTRY_EN.get(code, "")


def profile_line(p: Profile) -> dict[str, Any] | None:
    """What kind of company this is, in plain English, from registered facts only."""
    ident = p.family_claims("identity")
    ind = next((c for c in ident if c.field == "industry"), None)
    form = next((c for c in ident if c.field == "legal_form"), None)
    emp = next((c for c in ident if c.field == "registered_employees"), None)
    f = _fin(p)
    years = sorted({y for (_, y) in f}, key=int)
    y = years[-1] if years else None
    rev = f.get(("revenue", y)) if y else None
    pay = f.get(("payroll_cost", y)) if y else None
    assets = f.get(("total_assets", y)) if y else None
    subs = [c for c in p.family_claims("locations") if c.field == "registered_subunit"]
    code = str(ind.value).split(" ", 1)[0] if ind else ""
    name_en = industry_en(ind.value) if ind else ""
    keys = [c.key for c in (ind, form, emp, rev, pay, assets) if c]
    revenue = _amt(rev) or 0
    staff = int(emp.value) if emp and isinstance(emp.value, (int, float)) else 0
    if code.startswith("64.2") or ("holding" in fold_name(p) and revenue < 1e6):
        kind = "a holding company"
    elif code.startswith(("97.0", "68.32")) or any(w in fold_name(p) for w in ("borettslag", "boliglag", "sameie")) or             (form and str(form.value).upper().startswith(("BRL", "ESEK"))):
        kind = "a housing co-operative or owners' association"
    elif code.startswith("68."):
        kind = "a property company"
    elif revenue == 0 and not staff and not pay:
        kind = "a company with no filed revenue or staff" + (f" in {y}" if y else "")
    else:
        size = "a micro" if revenue < 2e6 else "a small" if revenue < 50e6 else "a mid-sized" if revenue < 500e6 else "a large"
        kind = f"{size} operating business"
    bits = [kind]
    if name_en:
        bits.append(f"in {name_en.lower()} (industry {code})")
    if staff:
        bits.append(f"with {staff:,} registered employee{'s' if staff != 1 else ''}")
    if len(subs) > 1:
        bits.append(f"and {len(subs)} registered workplaces")
    if not ind and not keys:
        return None
    text = "In plain terms: " + " ".join(bits) + "."
    return {"topic": "profile", "text": text, "claim_keys": keys + [c.key for c in subs[:3]],
            "method": "size bands by filed revenue: micro < NOK 2 m, small < 50 m, mid-sized < 500 m; industry names from SSB"}


def fold_name(p: Profile) -> str:
    name = next((c for c in p.family_claims("identity") if c.field == "legal_name"), None)
    return str(name.value).lower() if name else ""


def conclusions(p: Profile) -> list[dict[str, Any]]:
    return flag_conclusions(p) + financial_conclusions(p) + change_conclusions(p)
