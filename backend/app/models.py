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


Status = Literal["Verified", "Refuted", "Unresolved"]

FailureType = Literal[
    "overlooked_exception",
    "conflicting_documents",
    "outdated_or_inapplicable",
    "unsupported_assumption",
]


class ConditionResult(BaseModel):
    field: str
    op: str
    expected: Any
    actual: Any = None
    result: Literal["pass", "fail", "missing"]
    passage_id: str | None = None


class Evidence(BaseModel):
    """A claim<->passage link: the NLI verdict plus how it was used."""

    passage_id: str
    role: Literal["supports", "challenges"]
    label: Literal["entails", "contradicts", "neutral"]
    score: float
    counter_query: str | None = None
    # how scoring treated it: counts | conflict | ignored_lower_authority
    # | not_triggered | needs_input
    effect: str | None = None
    # for exceptions: the conditions that decide whether it applies to this case
    trigger_conditions: list[ConditionResult] = Field(default_factory=list)


class Claim(BaseModel):
    """One atomic claim from the AI answer."""

    id: str
    text: str
    cited_passage_ids: list[str] = Field(default_factory=list)
    # parameters the claim presupposes (checked by slot coverage)
    required_slots: list[str] = Field(default_factory=list)


class Extraction(BaseModel):
    """Output of llm.extract(): entities, case parameters and atomic claims."""

    entities: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    conclusion: str
    claims: list[Claim]


class NLIResult(BaseModel):
    label: Literal["entails", "contradicts", "neutral"]
    score: float = Field(ge=0.0, le=1.0)


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


# --- Proof Tree payload ------------------------------------------------------


class Correction(BaseModel):
    text: str
    passage_id: str
    source: Literal["scripted", "derived"]


class BaselineCheck(BaseModel):
    claim_id: str
    passage_id: str
    exists: bool
    entails: bool
    score: float


class Baseline(BaseModel):
    """Citation-only check: cited passage exists and entails. Never looks for counter-evidence."""

    status: Status
    checks: list[BaselineCheck]


class RootNode(BaseModel):
    id: str
    doc_id: str
    title: str
    version: str
    effective_date: date
    expiry_date: date
    doc_status: str
    authority: int
    source: SourceRef
    supersedes: str | None
    parent_doc_id: str | None
    hash: str
    hash_ok: bool
    state: PassageState
    state_label: str
    state_detail: str
    snippet: str
    conditions: list[Condition]
    roles: list[str]  # cited | supports | challenges


class ClaimNode(BaseModel):
    id: str
    text: str
    status: Status
    reason: str
    se: float
    sc: float
    failure_types: list[FailureType]
    cited_passage_ids: list[str]
    evidence: list[Evidence]
    conditions: list[ConditionResult]
    missing_slots: list[str]
    proposed_correction: Correction | None
    actions: list[str]


class Trunk(BaseModel):
    id: str = "conclusion"
    text: str
    status: Status


class Edge(BaseModel):
    source: str
    target: str
    # "cites": the AI cited it, but it gave the claim no usable evidence (e.g. filtered out)
    kind: Literal["supports", "challenges", "cites", "claim_of", "parent", "supersedes"]


class MissingInput(BaseModel):
    field: str
    label: str
    type: str
    options: list[str] = Field(default_factory=list)


class Overall(BaseModel):
    status: Status
    reason: str


class ProofTree(BaseModel):
    scenario_id: str
    title: str
    demo_date: date
    llm_mode: str
    llm_badge: str | None
    data_label: str
    employee: Employee
    question: str
    answer: str
    overall: Overall
    baseline: Baseline
    roots: list[RootNode]
    trunk: Trunk
    claims: list[ClaimNode]
    edges: list[Edge]
    missing_inputs: list[MissingInput]
