"""Stage 1, INVESTIGATE: gather supporting evidence for one claim.

Only approved, hash-verified, fresh, applicable passages can support a claim
(the cited ones plus anything retrieval adds). Also runs the condition checklist
of the best supporting passage and slot coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .conditions import evaluate_conditions
from .context import RunContext
from .models import Claim, ConditionResult, Evidence, Passage
from .retrieval import retrieve


@dataclass
class Investigation:
    claim: Claim
    evidence: list[Evidence] = field(default_factory=list)
    evaluated: set[str] = field(default_factory=set)  # passage ids already judged
    best_support: Passage | None = None
    conditions: list[ConditionResult] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)


def _missing(params: dict, name: str) -> bool:
    v = params.get(name)
    return v is None or (isinstance(v, str) and v.strip() == "")


def investigate_claim(claim: Claim, ctx: RunContext) -> Investigation:
    inv = Investigation(claim)

    cited = [
        rec.passage
        for pid in claim.cited_passage_ids
        if (rec := ctx.corpus.get(pid)) is not None and ctx.state_of(pid) == "active"
    ]
    retrieved = [h.passage for h in retrieve(ctx.corpus, claim.text, ctx.employee, ctx.today)]

    candidates: dict[str, Passage] = {p.passage_id: p for p in cited + retrieved}
    for pid, p in candidates.items():
        r = ctx.nli(claim, p)
        was_cited = pid in claim.cited_passage_ids
        if r.label == "entails":
            inv.evidence.append(Evidence(passage_id=pid, role="supports", label=r.label, score=r.score))
            inv.evaluated.add(pid)
        elif r.label == "contradicts" and was_cited:
            # the AI's own citation contradicts it
            inv.evidence.append(Evidence(passage_id=pid, role="challenges", label=r.label, score=r.score))
            inv.evaluated.add(pid)
        elif was_cited:
            inv.evaluated.add(pid)
        # a retrieved-only contradiction is left for the CHALLENGE stage to find with a counter-query

    supports = [e for e in inv.evidence if e.role == "supports"]
    if supports:
        best = max(supports, key=lambda e: e.score)
        inv.best_support = candidates[best.passage_id]
        inv.conditions = evaluate_conditions(inv.best_support.conditions, ctx.employee.params, best.passage_id)

    missing = [s for s in claim.required_slots if _missing(ctx.employee.params, s)]
    missing += [c.field for c in inv.conditions if c.result == "missing"]
    inv.missing_slots = list(dict.fromkeys(missing))
    return inv
