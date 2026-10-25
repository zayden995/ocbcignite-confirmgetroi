from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

PassageState = Literal[
    "active",
    "filtered_expired",
    "filtered_inapplicable",
    "filtered_not_approved",
    "filtered_hash_mismatch",
]


class SourceRef(BaseModel):
    hub: str
    path: str


class Condition(BaseModel):
    """Machine-readable mandatory condition, e.g. deposit_amount >= 10000."""

    field: str
    op: Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
    value: Any


class Passage(BaseModel):
    passage_id: str
    doc_id: str
    title: str
    version: str
    effective_date: date
    expiry_date: date
    status: str
    region: list[str]
    role_scope: list[str]
    product: str
    authority: int
    source: SourceRef
    supersedes: str | None = None
    parent_doc_id: str | None = None
    conditions: list[Condition] = Field(default_factory=list)
    text: str
    hash: str | None = None


class IngestedPassage(BaseModel):
    """A passage plus the result of ingestion-time checks."""

    passage: Passage
    approved: bool
    hash_ok: bool
    computed_hash: str


class Employee(BaseModel):
    """Simulated employee context (no real SSO). params are case parameters."""

    role: str
    region: str
    params: dict[str, Any] = Field(default_factory=dict)
