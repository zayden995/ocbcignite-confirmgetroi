"""Stage 2, CHALLENGE: try to DISPROVE each claim.

Runs a small set of counter-query templates through retrieve(), classifies what
comes back against the claim, decides whether each exception actually applies
to this case, and names the failure type.
"""
from __future__ import annotations

from .conditions import evaluate_conditions
from .context import RunContext
from .investigate import Investigation
from .models import ConditionResult, Evidence, FailureType, Status, TraceHit, TraceQuery
from .retrieval import retrieve

COUNTER_TEMPLATES = [
    "unless {c}",
    "exception for {c}",
    "superseded by {c}",
    "does not apply when {c}",
    "only if {c}",
]


def challenge_claim(inv: Investigation, ctx: RunContext) -> list[str]:
    """Add challenging evidence to inv. Returns extra missing slots needed to judge exceptions."""
    claim = inv.claim
    for template in COUNTER_TEMPLATES:
        query = template.format(c=claim.text)
        trace_hits: list[TraceHit] = []
        for hit in retrieve(ctx.corpus, query, ctx.employee, ctx.today):
            pid = hit.passage.passage_id
            if pid in inv.evaluated:
                trace_hits.append(TraceHit(passage_id=pid, retrieval_score=hit.score, outcome="already_evaluated"))
                continue
            inv.evaluated.add(pid)
            r = ctx.nli(claim, hit.passage)
            contradicts = r.label == "contradicts"
            if contradicts:
                inv.evidence.append(
                    Evidence(passage_id=pid, role="challenges", label=r.label, score=r.score, counter_query=query)
                )
            trace_hits.append(
                TraceHit(
                    passage_id=pid, retrieval_score=hit.score, nli_label=r.label, nli_score=r.score,
                    outcome="challenge" if contradicts else "not_contradicting",
                )
            )
        inv.trace_challenge.append(TraceQuery(template=template, query=query, hits=trace_hits))
    return apply_triggers(inv, ctx)


def apply_triggers(inv: Investigation, ctx: RunContext) -> list[str]:
    """An exception only counts if its own trigger conditions hold for this case.

    fail    -> the exception does not apply here (kept for display, excluded from scoring)
    missing -> we cannot tell; excluded from scoring and the parameter is requested
    """
    needed: list[str] = []
    for e in inv.evidence:
        if e.role != "challenges":
            continue
        passage = ctx.corpus.records[e.passage_id].passage
        e.trigger_conditions = evaluate_conditions(passage.conditions, ctx.employee.params, e.passage_id)
        if any(c.result == "fail" for c in e.trigger_conditions):
            e.effect = "not_triggered"
        elif any(c.result == "missing" for c in e.trigger_conditions):
            e.effect = "needs_input"
            needed += [c.field for c in e.trigger_conditions if c.result == "missing"]
    return list(dict.fromkeys(needed))


def classify_failures(
    status: Status,
    claim_cited: list[str],
    evidence: list[Evidence],
    conditions: list[ConditionResult],
    missing_slots: list[str],
    conflict: bool,
    ctx: RunContext,
) -> list[FailureType]:
    if status == "Verified":
        return []
    types: list[FailureType] = []

    counted = [e for e in evidence if e.role == "challenges" and e.effect == "counts"]
    cited_docs = {ctx.corpus.records[p].passage.doc_id for p in claim_cited if p in ctx.corpus.records}
    cited_out_of_date = any(ctx.state_of(p) in ("filtered_expired", "filtered_inapplicable") for p in claim_cited)
    supersedes_cited = any(ctx.corpus.records[e.passage_id].passage.supersedes in cited_docs for e in counted)

    if conflict:
        types.append("conflicting_documents")
    if cited_out_of_date or supersedes_cited:
        types.append("outdated_or_inapplicable")
    elif counted:
        types.append("overlooked_exception")
    if missing_slots or any(c.result in ("fail", "missing") for c in conditions):
        types.append("unsupported_assumption")
    return types
