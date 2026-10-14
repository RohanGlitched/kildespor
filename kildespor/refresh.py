"""Refresh as a diff against the previous envelope.

- claims are matched on their stable key; values are compared without retrieval metadata
- a family whose sources failed or were blocked this run keeps its previous claims (carried forward,
  marked as such) instead of reporting them as removed
- re-running on the same source snapshot produces no events (idempotent)
- every event carries the evidence for both sides
"""
from __future__ import annotations

import json
from typing import Any

from .util import utc_now

TYPED = {
    ("people", "added"): "new_role", ("people", "removed"): "ended_role",
    ("jobs", "added"): "new_job", ("jobs", "removed"): "closed_job",
    ("locations", "added"): "new_location", ("locations", "removed"): "closed_location",
    ("financials", "added"): "new_filing", ("financials", "changed"): "restated_figure",
    ("website", "added"): "new_website", ("website", "removed"): "website_lost", ("website", "changed"): "changed_website",
    ("social", "added"): "new_profile", ("social", "removed"): "removed_profile",
    ("activity", "added"): "new_activity",
    ("description", "changed"): "changed_description", ("description", "added"): "new_description",
    ("identity", "changed"): "changed_identity", ("contact", "changed"): "changed_contact",
}
MATERIAL = {"people": "high", "financials": "high", "website": "high", "identity": "high", "locations": "medium",
            "jobs": "medium", "social": "low", "activity": "low", "description": "low", "contact": "low"}
VOLATILE_FAMILIES = {"activity"}  # old news falling off a feed is not a removal


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def load_previous(path: str | None) -> dict[str, dict]:
    if not path:
        return {}
    prev: dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                env = json.loads(line)
                prev[env["organisation_number"]] = env
    return prev


def diff(current: dict, previous: dict | None) -> dict:
    """Mutates current: carries forward claims for failed families and stamps first/last observed."""
    now = current["run"]["completed_at"]
    if not previous:
        for c in current["claims"]:
            c["first_observed"] = now
            c["last_observed"] = now
        return {"previous_run_id": None, "compared_at": utc_now(), "events": [], "carried_forward": 0}
    prev_claims = {c["key"]: c for c in previous.get("claims", [])}
    prev_ev = {e["id"]: e for e in previous.get("evidence", [])}
    cur_ev = {e["id"]: e for e in current["evidence"]}
    failed_fams = {s["family"] for s in current["field_states"] if s["state"] in ("failed", "blocked")}
    events: list[dict] = []
    seen = set()
    for c in current["claims"]:
        seen.add(c["key"])
        old = prev_claims.get(c["key"])
        if old is None:
            c["first_observed"] = now
            c["last_observed"] = now
            ev_type = TYPED.get((c["family"], "added"), "added")
            if previous.get("claims") is not None:
                events.append({"type": ev_type, "change": "added", "family": c["family"], "field": c["field"], "key": c["key"],
                               "materiality": MATERIAL.get(c["family"], "low"), "current": c["value"],
                               "current_evidence": [cur_ev[i] for i in c["evidence_ids"] if i in cur_ev]})
            continue
        c["first_observed"] = old.get("first_observed") or previous["run"]["completed_at"]
        c["last_observed"] = now
        if _canon(old["value"]) != _canon(c["value"]):
            events.append({"type": TYPED.get((c["family"], "changed"), "changed"), "change": "changed", "family": c["family"],
                           "field": c["field"], "key": c["key"], "materiality": MATERIAL.get(c["family"], "low"),
                           "previous": old["value"], "current": c["value"],
                           "previous_evidence": [prev_ev[i] for i in old.get("evidence_ids", []) if i in prev_ev],
                           "current_evidence": [cur_ev[i] for i in c["evidence_ids"] if i in cur_ev]})
    carried = 0
    for key, old in prev_claims.items():
        if key in seen:
            continue
        if old["family"] in failed_fams or old.get("family") in VOLATILE_FAMILIES:
            # keep the last supported value and say why
            kept = dict(old)
            kept["carried_forward"] = True
            kept["carried_reason"] = ("source failed or was blocked this run" if old["family"] in failed_fams
                                      else "older dated item no longer listed by the source")
            current["claims"].append(kept)
            for i in old.get("evidence_ids", []):
                if i in prev_ev and i not in cur_ev:
                    current["evidence"].append(prev_ev[i])
                    cur_ev[i] = prev_ev[i]
            carried += 1
            continue
        events.append({"type": TYPED.get((old["family"], "removed"), "removed"), "change": "removed", "family": old["family"],
                       "field": old["field"], "key": key, "materiality": MATERIAL.get(old["family"], "low"),
                       "previous": old["value"], "last_observed": old.get("last_observed"),
                       "previous_evidence": [prev_ev[i] for i in old.get("evidence_ids", []) if i in prev_ev]})
    return {"previous_run_id": previous["run"]["run_id"], "previous_completed_at": previous["run"]["completed_at"],
            "compared_at": utc_now(), "events": events, "carried_forward": carried}
