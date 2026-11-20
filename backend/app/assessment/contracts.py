"""Wire types for a single, immutable assessment revision."""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Short = Annotated[str, Field(min_length=1)]
Positive = Annotated[int, Field(strict=True, gt=0, le=2**53 - 1)]
FactKey = Literal["product", "currency", "booking_region", "segment", "channel", "tenor_months", "deposit_cents", "transfer_cents"]
Task = Literal["rate_only", "plan_and_rate"]
Decision = Literal["deposit_rate", "single_transfer"]


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Span(Wire):
    start: Annotated[int, Field(ge=0, strict=True)]
    end: Positive
    quote: Short

    def matches(self, text: str) -> bool:
        return self.start < self.end <= len(text) and text[self.start:self.end] == self.quote


class Origin(Wire):
    kind: Literal["form", "employee_text", "fixture"]
    ref: Short
    span: Span | None = None


class Fact(Wire):
    key: FactKey
    value: Short | Positive
    origin: Origin

    @model_validator(mode="after")
    def check_units(self):
        numeric = self.key in {"tenor_months", "deposit_cents", "transfer_cents"}
        if numeric != isinstance(self.value, int) or not str(self.value).strip():
            raise ValueError(f"Invalid value for {self.key}")
        return self


class Turn(Wire):
    turn_id: Short
    question: Short
    answer: str

    @field_validator("question", "turn_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Expected nonblank text")
        return value


class Confirmation(Wire):
    choice: Literal["rate_only", "plan_and_rate", "other", "incomplete", "conflicting"]
    input_revision: Positive


class Profile(Wire):
    role: Literal["RM", "BM", "CC"]
    region: Literal["SG", "MY"]


class Request(Turn):
    schema_version: Literal["2"]
    input_revision: Positive
    bundle_id: Short
    as_of: date
    employee: Profile
    history: list[Turn]
    facts: list[Fact]
    confirmation: Confirmation | None

    @field_validator("as_of", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if not isinstance(value, str) or len(value) != 10 or date.fromisoformat(value).isoformat() != value:
            raise ValueError("Expected YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def check_identity(self):
        ids = [t.turn_id for t in [*self.history, self]]
        if len(ids) != len(set(ids)):
            raise ValueError("Turn IDs must be unique")
        if self.confirmation and self.confirmation.input_revision != self.input_revision:
            raise ValueError("Confirmation belongs to a different revision")
        return self


class Rate(Wire):
    rate_bps: int


class Transfer(Wire):
    limit_cents: int
    within_cap: bool


class Branch(Wire):
    decision_id: Decision
    status: Literal["covered", "wrong", "omitted", "need_fact", "policy_review", "uncertain_text"]
    expected: Rate | Transfer | None = None
    spans: list[Span] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    fact_keys: list[FactKey] = Field(default_factory=list)
    explanation: str


class Root(Wire):
    passage_id: str
    version: str
    text: str
    state: Literal["governing", "context", "excluded", "pending"]
    reason: str


class Extra(Wire):
    span: Span
    status: Literal["supported", "wrong", "unresolved"]
    source_ids: list[str]
    explanation: str


class Action(Wire):
    kind: Literal["use", "clarify_intent", "review_policy", "supply_fact", "review_text", "review_repair"]
    prompt: str
    fields: list[FactKey] = Field(default_factory=list)


class Repair(Wire):
    text: str
    source_ids: list[str]


class Coverage(Wire):
    covered: int
    required: int


class Result(Wire):
    schema_version: Literal["2"] = "2"
    assessment_id: str
    turn_id: str
    input_revision: Positive
    bundle_id: str
    snapshot_id: str
    mode: Literal["fixture", "live"]
    task_id: Task | None
    verdict: Literal["ready", "hold"]
    reasons: list[str]
    coverage: Coverage
    branches: list[Branch]
    extras: list[Extra]
    roots: list[Root]
    next: Action
    repair: Repair | None
