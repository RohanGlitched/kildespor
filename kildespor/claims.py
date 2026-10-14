"""Claims and evidence.

A claim is one fact about the exact legal entity. It always points to at least one evidence
record: the URL it came from, when we fetched it, the hash of what we fetched, the exact text
span or field path that supports it, and how it was extracted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .util import clip, stable_id

# Field families, in the order the profile presents them.
FAMILIES = {
    "identity": "Legal identity and public brand",
    "financials": "Latest annual accounts and history",
    "people": "Leadership and board",
    "locations": "Registered workplaces and addresses",
    "website": "Verified official website",
    "contact": "Company-published contact details",
    "social": "Company-owned profiles",
    "jobs": "Hiring",
    "activity": "Dated public activity",
    "description": "What the company says it does",
}

STATES = ("available", "not_available", "blocked", "not_applicable", "ambiguous", "failed")


@dataclass
class Evidence:
    source_url: str
    source_class: str  # official_registry | company_owned | public_job_board | open_knowledge_base | platform_feed
    retrieved_at: str
    content_sha256: str
    claim_span: str
    extraction_method: str
    final_url: str = ""
    http_status: int | None = None
    source_name: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        self.claim_span = clip(self.claim_span, 400)
        if not self.id:
            self.id = stable_id(self.source_url, self.content_sha256, self.claim_span, prefix="ev-")

    def as_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "source_class": self.source_class,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "claim_span": self.claim_span,
            "extraction_method": self.extraction_method,
        }
        if self.final_url and self.final_url != self.source_url:
            d["final_url"] = self.final_url
        if self.http_status is not None:
            d["http_status"] = self.http_status
        return d


@dataclass
class Claim:
    family: str
    field: str
    value: Any
    evidence: list[Evidence]
    label: str = ""
    effective_date: str | None = None  # date the fact refers to (posting date, event date, board role date)
    reporting_period: str | None = None  # accounting year for financial values
    confidence: float = 0.99
    relationship: str = "exact"  # exact | registered_subunit | group_member
    attributes: dict[str, Any] = field(default_factory=dict)
    key: str = ""

    def __post_init__(self) -> None:
        assert self.family in FAMILIES, self.family
        if not self.key:
            self.key = stable_id(self.family, self.field, self.identity_value(), prefix=f"{self.family}:{self.field}:")

    def identity_value(self) -> Any:
        """The part of the value that identifies the fact (for refresh diffs)."""
        v = self.value
        if isinstance(v, dict):
            for k in ("id", "url", "uuid", "name", "title"):
                if k in v:
                    return (k, str(v[k]).lower())
        if isinstance(v, str):
            return v.lower().rstrip("/")
        return v

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "family": self.family,
            "field": self.field,
            "label": self.label or self.field.replace("_", " "),
            "value": self.value,
            "availability": "available",
            "confidence": round(self.confidence, 3),
            "relationship": self.relationship,
            "evidence_ids": [e.id for e in self.evidence],
        }
        if self.effective_date:
            d["effective_date"] = self.effective_date
        if self.reporting_period:
            d["reporting_period"] = self.reporting_period
        if self.attributes:
            d["attributes"] = self.attributes
        return d


@dataclass
class FieldState:
    family: str
    state: str
    note: str
    checked: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        assert self.state in STATES, self.state
        return {"family": self.family, "label": FAMILIES[self.family], "state": self.state, "note": self.note,
                "checked_sources": self.checked}


class Profile:
    """Accumulates claims for one organisation number."""

    def __init__(self, orgnr: str) -> None:
        self.orgnr = orgnr
        self.claims: list[Claim] = []
        self._keys: set[str] = set()
        self.states: dict[str, FieldState] = {}
        self.checked: dict[str, list[str]] = {f: [] for f in FAMILIES}
        self.errors: list[dict[str, Any]] = []
        self.notes: dict[str, Any] = {}

    def add(self, claim: Claim) -> bool:
        if claim.key in self._keys:
            # merge evidence into the existing claim
            for c in self.claims:
                if c.key == claim.key:
                    have = {e.id for e in c.evidence}
                    c.evidence.extend(e for e in claim.evidence if e.id not in have)
            return False
        self._keys.add(claim.key)
        self.claims.append(claim)
        return True

    def checked_source(self, family: str, source: str) -> None:
        if source not in self.checked[family]:
            self.checked[family].append(source)

    def mark(self, family: str, state: str, note: str) -> None:
        """Record why a family has no claims. The first non-failure explanation wins."""
        cur = self.states.get(family)
        if cur and cur.state not in ("failed",) and state == "failed":
            return
        if cur and cur.state == "blocked" and state == "not_available":
            return
        self.states[family] = FieldState(family, state, note)

    def error(self, source: str, message: str) -> None:
        self.errors.append({"source": source, "message": clip(message, 300)})

    def family_claims(self, family: str) -> list[Claim]:
        return [c for c in self.claims if c.family == family]
