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

    # the challenging passage that actually drove this outcome (counts toward SC, or raised a conflict)
    drivers = [e for e in evidence if e.role == "challenges" and e.effect in ("counts", "conflict")]
    top = max(drivers, key=lambda e: e.score) if drivers else None

    scripted_fn = getattr(ctx.llm, "scripted_correction", None)
    if ctx.llm.is_mock and scripted_fn is not None:
        s = scripted_fn(claim.id, status, top.passage_id if top else "")
        if s:
            return Correction(text=s["text"], passage_id=s["passage_id"], source="scripted")

    if top is not None:
        p = ctx.corpus.records[top.passage_id].passage
        return Correction(text=f"Per {p.doc_id} v{p.version}: {p.text}", passage_id=p.passage_id, source="derived")
    if missing_slots and inv.best_support is not None:
        return Correction(
            text=f"Confirm {', '.join(missing_slots)} before relying on this claim.",
            passage_id=inv.best_support.passage_id,
            source="derived",
        )
    return None
