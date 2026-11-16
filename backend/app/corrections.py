"""Proposed corrected statement for a Refuted/Unresolved claim, with the justifying passage.

Mock mode uses scripted text. Otherwise (and when no script exists for the current
outcome) the correction is derived deterministically from the evidence.
"""
from __future__ import annotations

from .context import RunContext
from .investigate import Investigation
from .models import Correction, Evidence, Status


def propose_correction(
    status: Status, inv: Investigation, evidence: list[Evidence], missing_slots: list[str], ctx: RunContext
) -> Correction | None:
    if status == "Verified":
        return None
    claim = inv.claim

    # The challenging passage that actually drove this outcome (counts toward SC, or raised a conflict)
    drivers = [e for e in evidence if e.role == "challenges" and e.effect in ("counts", "conflict")]
    top = max(drivers, key=lambda e: e.score) if drivers else None

    scripted_fn = getattr(ctx.llm, "scripted_correction", None)
    if ctx.llm.is_mock and scripted_fn is not None:
        s = scripted_fn(claim.id, status, top.passage_id if top else "")
        if s:
            return Correction(text=s["text"], passage_id=s["passage_id"], source="scripted")

    # 1. Equal-authority conflict between two active policies
    if top is not None and top.effect == "conflict":
        p = ctx.corpus.records[top.passage_id].passage
        sup = inv.best_support.doc_id if inv.best_support else "the cited policy"
        return Correction(
            text=(
                f"Do not quote this yet—{sup} and {p.doc_id} ({p.title}) conflict. "
                f"{p.doc_id} states: \"{p.text}\" Escalate to the policy owner to confirm which applies."
            ),
            passage_id=p.passage_id,
            source="derived",
        )

    # 2. Refuted by an active exception, amendment, or superseding policy
    if top is not None:
        p = ctx.corpus.records[top.passage_id].passage
        return Correction(
            text=f"Correct this before replying—per {p.doc_id} ({p.title}): {p.text}",
            passage_id=p.passage_id,
            source="derived",
        )

    # 3. Failed a mandatory numerical/categorical condition (e.g. deposit_amount < 10000)
    failed = [c for c in inv.conditions if c.result == "fail"]
    if failed and inv.best_support is not None:
        p = inv.best_support
        cond_str = ", ".join(
            f"{c.field.replace('_', ' ')} is {c.actual} (must be {c.op} {c.expected})" for c in failed
        )
        return Correction(
            text=(
                f"Tell the customer they do not qualify under {p.doc_id}: {cond_str}. "
                f"Policy requirement: {p.text}"
            ),
            passage_id=p.passage_id,
            source="derived",
        )

    # 4. Missing required customer inputs
    if missing_slots:
        pid = inv.best_support.passage_id if inv.best_support else (claim.cited_passage_ids[0] if claim.cited_passage_ids else "")
        pretty = ", ".join(s.replace("_", " ") for s in missing_slots)
        return Correction(
            text=f"Ask the customer to confirm their {pretty} before quoting this answer.",
            passage_id=pid,
            source="derived",
        )

    # 5. Cited policy was filtered out (inapplicable to role/region, expired, or unapproved wiki)
    for pid in claim.cited_passage_ids:
        rec = ctx.corpus.records.get(pid)
        if rec is None:
            continue
        state = ctx.state_of(pid)
        p = rec.passage
        if state == "filtered_inapplicable":
            return Correction(
                text=(
                    f"Remove the point from {p.doc_id} ({p.title}) before replying—that policy only applies "
                    f"to roles {'/'.join(p.role_scope)} in {'/'.join(p.region)}, not to your profile "
                    f"({ctx.employee.role} in {ctx.employee.region})."
                ),
                passage_id=pid,
                source="derived",
            )
        if state == "filtered_expired":
            return Correction(
                text=f"Do not cite {p.doc_id} ({p.title})—it expired on {p.expiry_date}. Use the current active policy instead.",
                passage_id=pid,
                source="derived",
            )
        if state == "filtered_not_approved":
            return Correction(
                text=f"Remove this claim—{p.doc_id} ({p.title}) is from an unapproved source ({p.source.hub}) and cannot be quoted.",
                passage_id=pid,
                source="derived",
            )

    # 6. Fallback when no approved policy supports the claim at all
    fallback_pid = claim.cited_passage_ids[0] if claim.cited_passage_ids else ""
    return Correction(
        text=(
            f"Remove this statement before replying—no active approved policy for "
            f"{ctx.employee.role} in {ctx.employee.region} supports \"{claim.text}\"."
        ),
        passage_id=fallback_pid,
        source="derived",
    )