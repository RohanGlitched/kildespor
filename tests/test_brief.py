from datetime import date

from kildespor import brief
from kildespor.claims import Claim, Evidence, Profile

ACC = "https://data.brreg.no/regnskapsregisteret/regnskap/123456789"
REG = "https://data.brreg.no/enhetsregisteret/api/enheter/123456789"


def ev(url: str, span: str = "x", cls: str = "official_registry") -> Evidence:
    return Evidence(url, cls, "2026-11-13T10:00:00Z", "0" * 64, span, "test", source_name="Brønnøysundregistrene")


def fin(p: Profile, field: str, year: str, amount: float) -> None:
    p.add(Claim("financials", field, {"amount": amount, "year": year, "currency": "NOK"}, [ev(ACC)], key=f"financials:{field}:{year}"))


def base() -> Profile:
    p = Profile("123456789")
    p.add(Claim("identity", "legal_name", "EKSEMPEL BYGG AS", [ev(REG)]))
    for y, r in (("2024", 10e6), ("2025", 14e6)):
        fin(p, "revenue", y, r)
        fin(p, "operating_result", y, r * 0.1)
        fin(p, "annual_result", y, r * 0.08)
    return p


def test_lead_is_a_buyer_fact_with_its_source():
    b = brief.brief(base(), today=date(2026, 11, 13))
    assert b["headline"].startswith("Revenue up 40% to NOK 14.0 m in 2025")
    assert "(Brønnøysund annual accounts)" in b["headline"]
    assert "In the last 12 months" in b["text"] or "No register changes" in b["text"]
    assert "Checked but not found" in b["text"]


def test_hiring_leads_and_nothing_repeats():
    p = base()
    p.add(Claim("jobs", "job_posting", {"title": "Tømrer", "url": "https://eksempel.no/jobb/1", "status": "open"},
                [ev("https://eksempel.no/jobb/1", "Tømrer", "company_owned")], effective_date="2026-11-01"))
    b = brief.brief(p, today=date(2026, 11, 13))
    assert b["headline"].startswith("Hiring now: 1 open position (“Tømrer”), latest posted 2026-11-01 (eksempel.no)")
    assert b["text"].count("Revenue up 40%") == 1


def test_roles_are_translated():
    p = base()
    p.add(Claim("activity", "roles_changed", {"title": "Daglig leder registered"}, [ev(REG)], effective_date="2026-10-01"))
    b = brief.brief(p, today=date(2026, 11, 13))
    assert "new general manager registered" in b["text"]
