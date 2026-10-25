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

    scripted_fn = getattr(ctx.llm, "scripted_correction", None)
    if ctx.llm.is_mock and scripted_fn is not None:
        s = scripted_fn(claim.id, status)
        if s:
            return Correction(text=s["text"], passage_id=s["passage_id"], source="scripted")

    counted = [e for e in evidence if e.role == "challenges" and e.effect in ("counts", "conflict")]
    if counted:
        best = max(counted, key=lambda e: e.score)
        p = ctx.corpus.records[best.passage_id].passage
        return Correction(text=f"Per {p.doc_id} v{p.version}: {p.text}", passage_id=p.passage_id, source="derived")
    if missing_slots and inv.best_support is not None:
        return Correction(
            text=f"Confirm {', '.join(missing_slots)} before relying on this claim.",
            passage_id=inv.best_support.passage_id,
            source="derived",
        )
    return None
