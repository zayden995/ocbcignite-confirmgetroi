"""Freshness, applicability and per-run passage state."""
from __future__ import annotations

from datetime import date

from .models import Employee, IngestedPassage, Passage, PassageState


def is_fresh(p: Passage, today: date) -> bool:
    """effective_date <= today < expiry_date"""
    return p.effective_date <= today < p.expiry_date


def is_applicable(p: Passage, role: str, region: str) -> bool:
    return region in p.region and role in p.role_scope


def passage_state(rec: IngestedPassage, employee: Employee, today: date) -> PassageState:
    """First failing gate wins: whitelist, integrity, freshness/status, scope."""
    if not rec.approved:
        return "filtered_not_approved"
    if not rec.hash_ok:
        return "filtered_hash_mismatch"
    if rec.passage.status != "active" or not is_fresh(rec.passage, today):
        return "filtered_expired"
    if not is_applicable(rec.passage, employee.role, employee.region):
        return "filtered_inapplicable"
    return "active"
