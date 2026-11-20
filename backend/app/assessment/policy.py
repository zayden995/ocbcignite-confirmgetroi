"""Resolve reviewed decision rows against a pinned source family, with the answer withheld."""
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from graphlib import TopologicalSorter
from typing import Literal

from pydantic import Field, TypeAdapter, model_validator

from ..conditions import evaluate_conditions
from ..config import DATA_DIR
from ..corpus import compute_hash, ingest, load_approved_sources, load_raw_passages
from ..filters import passage_state
from ..models import Employee
from .contracts import Branch, Decision, Positive, Profile, Rate, Root, Transfer, Wire


class Row(Wire):
    row_id: str
    source_ids: list[str] = Field(min_length=1)
    governing: str
    effective_from: date
    effective_until_exclusive: date

    @model_validator(mode="after")
    def check_bounds(self):
        if self.effective_from >= self.effective_until_exclusive or self.governing not in self.source_ids:
            raise ValueError("Invalid row interval or governing source")
        return self


class RateRow(Row):
    minimum_placement_if_known_cents: Positive
    rate_bps: int = Field(ge=0, strict=True)


class TransferRow(Row):
    historical_predecessor: str
    comparison: Literal["less_than_or_equal"]
    amount_key: Literal["transfer_cents"]
    limit_cents: Positive


def metadata_digest(raw: dict) -> str:
    metadata = {k: v for k, v in raw.items() if k not in {"text", "hash"}}
    return compute_hash(json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def money(cents: int) -> str:
    whole, fraction = divmod(cents, 100)
    return f"S${whole:,}" + (f".{fraction:02}" if fraction else "")


@dataclass
class Calculation:
    branch: Branch
    roots: list[Root]
    missing: list[str]
    sentence: str = ""


class Policy:
    def __init__(self, bundle: dict, raw: list[dict], approved: list[dict]):
        if not bundle.get("policy_owner") or not bundle.get("independent_reviewer") or bundle["policy_owner"] == bundle["independent_reviewer"]:
            raise ValueError("A policy owner and an independent reviewer must approve this bundle")
        self.bundle_id = bundle["bundle_id"]
        self.snapshot_id = bundle["snapshot_id"]
        self.scope = dict(bundle["common_scope"])
        self.region = self.scope.pop("employee_region")
        self.roles = bundle["roles"]
        self.tasks = bundle["task_definitions"]
        self.tables = {
            "deposit_rate": TypeAdapter(list[RateRow]).validate_python(bundle["tables"]["deposit_rate"]),
            "single_transfer": TypeAdapter(list[TransferRow]).validate_python(bundle["tables"]["single_transfer"]),
        }
        self.corpus = ingest(raw, approved)
        self.seals = {s["passage_id"]: s for s in bundle["source_revisions"]}
        self.metadata = {p["passage_id"]: metadata_digest(p) for p in raw}
        if len(self.metadata) != len(raw) or len(self.seals) != len(bundle["source_revisions"]):
            raise ValueError("Duplicate passage revision")
        if self.seals.keys() - self.metadata.keys():
            raise ValueError("Missing pinned source revision")
        self.links = {}
        for rec in self.corpus.records.values():
            p = rec.passage
            if p.effective_date >= p.expiry_date:
                raise ValueError("Invalid passage interval")
            self.links.setdefault(p.doc_id, set()).update(filter(None, [p.parent_doc_id, p.supersedes]))
        for links in self.links.values():
            if links - self.links.keys():
                raise ValueError("Broken document family link")
        tuple(TopologicalSorter(self.links).static_order())
        for rows in self.tables.values():
            for row in rows:
                references = set(row.source_ids)
                if isinstance(row, TransferRow):
                    references.add(row.historical_predecessor)
                if references - self.seals.keys() or references - self.metadata.keys():
                    raise ValueError("Broken reviewed source reference")

    def root(self, pid, employee, today) -> Root:
        rec = self.corpus.records[pid]
        p = rec.passage
        seal = self.seals.get(pid)
        gate = passage_state(rec, employee, today)
        state, reason = "context", "Approved revision in employee scope."
        if gate != "active":
            state, reason = "excluded", gate.replace("filtered_", "").replace("_", " ")
        elif not seal:
            state, reason = "pending", "Effective source awaits independent review."
        elif (p.version, rec.computed_hash, self.metadata[pid]) != (seal["version"], seal["text_sha256"], seal["metadata_sha256"]):
            state, reason = "excluded", "Revision, text or metadata differs from the reviewed digest."
        return Root(passage_id=pid, version=p.version, text=p.text, state=state, reason=reason)

    def family(self, row):
        docs = {self.corpus.records[pid].passage.doc_id for pid in row.source_ids}
        while True:
            linked = set(docs)
            for doc, parents in self.links.items():
                if doc in docs or docs & parents:
                    linked.update([doc, *parents])
            if linked == docs:
                break
            docs = linked
        products = {self.corpus.records[pid].passage.product for pid in row.source_ids}
        # A newly delivered source in this product with no family assignment needs review, too.
        return [pid for pid, rec in self.corpus.records.items() if rec.passage.doc_id in docs
                or (pid not in self.seals and rec.passage.product in products and not self.links[rec.passage.doc_id])]

    def calculate(self, decision: Decision, facts: dict, profile: Profile, today: date, *, conditional_rate=False) -> Calculation:
        rows = self.tables[decision]
        active = [r for r in rows if r.effective_from <= today < r.effective_until_exclusive]
        employee = Employee(**profile.model_dump(), params=facts)
        scope_keys = list(self.scope) if decision == "deposit_rate" else ["booking_region", "segment", "currency", "channel"]
        keys = scope_keys + (["deposit_cents"] if decision == "deposit_rate" else ["transfer_cents"])
        branch = Branch(decision_id=decision, status="policy_review", fact_keys=keys,
                        explanation="No unique reviewed policy row is effective on this date.")
        roots = {}
        for row in active or rows:
            for pid in self.family(row):
                roots[pid] = self.root(pid, employee, today)
        branch.source_ids = list(roots)
        calc = Calculation(branch, list(roots.values()), [])
        if len(active) != 1:
            return calc
        row = active[0]
        governing = roots[row.governing]
        params = {**facts}
        if "deposit_cents" in facts:
            params["deposit_amount"] = Decimal(facts["deposit_cents"]) / 100
        for pid, root in roots.items():
            p = self.corpus.records[pid].passage
            if pid in row.source_ids:
                if root.state != "context":
                    branch.explanation = f"Review {pid}: {root.reason}"
                    return calc
            elif root.state == "excluded" and root.reason in {"Revision, text or metadata differs from the reviewed digest.", "hash mismatch"}:
                branch.explanation = f"Review related source {pid}: {root.reason}"
                return calc
            elif root.state in {"pending", "context"}:
                # A reviewed successor may explicitly replace an otherwise active predecessor.
                if any(p.doc_id in self.links[self.corpus.records[x].passage.doc_id] for x in row.source_ids):
                    root.state, root.reason = "excluded", "Overridden by the reviewed row."
                    continue
                checks = evaluate_conditions(p.conditions, params)
                if any(c.result == "fail" for c in checks):
                    root.state, root.reason = "excluded", "Linked clause conditions do not apply."
                    continue
                root.state, root.reason = "pending", "Applicable linked clause outside the reviewed row."
                branch.explanation = f"Policy owner must review {pid} before this decision can clear."
                return calc
        mismatch = [k for k in scope_keys if k in facts and facts[k] != self.scope[k]]
        if mismatch or profile.region != self.region or profile.role not in self.roles:
            governing.state, governing.reason = "excluded", "Outside reviewed employee or booking/product scope."
            branch.explanation = governing.reason + " " + ", ".join(mismatch)
            return calc
        missing = [k for k in scope_keys if k not in facts]
        if isinstance(row, RateRow) and "deposit_cents" not in facts and not conditional_rate:
            missing.append("deposit_cents")
        if isinstance(row, TransferRow) and (row.amount_key not in facts or (
            "deposit_cents" in facts and facts["deposit_cents"] != facts.get(row.amount_key)
        )):
            missing.append(row.amount_key)
        if missing:
            calc.missing = missing
            branch.status = "need_fact"
            branch.explanation = "Confirm the customer facts for this placement: " + ", ".join(missing)
            return calc
        checks = evaluate_conditions(self.corpus.records[row.governing].passage.conditions, params)
        if any(c.result != "pass" for c in checks):
            branch.explanation = "The governing clause's conditions are not established."
            return calc
        governing.state, governing.reason = "governing", "Applicable reviewed decision clause."
        if isinstance(row, RateRow):
            if facts.get("deposit_cents", row.minimum_placement_if_known_cents) < row.minimum_placement_if_known_cents:
                branch.explanation = f"Placement below the {money(row.minimum_placement_if_known_cents)} minimum."
                return calc
            branch.expected = Rate(rate_bps=row.rate_bps)
            rate = f"{row.rate_bps // 100}.{row.rate_bps % 100:02}%"
            calc.sentence = f"The standard rate for this FAST-funded deposit is {rate} p.a."
            branch.explanation = f"{row.governing} amends the general schedule. {row.rate_bps} annual basis points = {rate} p.a."
        else:
            amount = facts[row.amount_key]
            fits = amount <= row.limit_cents
            branch.expected = Transfer(limit_cents=row.limit_cents, within_cap=fits)
            comparison = "is within" if fits else "exceeds"
            calc.sentence = f"A single {money(amount)} FAST transfer {comparison} the {money(row.limit_cents)} per-transfer limit."
            branch.explanation = calc.sentence + f" {'Remaining capacity' if fits else 'Excess'} is {money(abs(amount - row.limit_cents))}."
        branch.status = "omitted"
        return calc


POLICY = Policy(json.loads((DATA_DIR / "decision_bundle.json").read_text(encoding="utf-8")),
                load_raw_passages(), load_approved_sources())
