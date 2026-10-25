"""The deterministic verification matrix. No model calls, no randomness.

Per claim, with SE/SC in [0, 1]:
  1. Refuted    if SC >= 0.50, or any mandatory condition explicitly fails
  2. Unresolved if required slots are missing, or active sources of equal
                authority conflict
  3. Verified   if SE > 0.85 and SC < 0.15 and all mandatory conditions pass
  4. Unresolved otherwise (e.g. SE 0.90 / SC 0.30)
Overall: any Refuted -> Refuted; else any Unresolved -> Unresolved; else Verified.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ConditionResult, Evidence, Passage, Status

SC_REFUTE = 0.50
SE_VERIFY = 0.85
SC_VERIFY = 0.15


@dataclass
class Decision:
    status: Status
    reason: str


def verify_claim(
    se: float,
    sc: float,
    conditions: list[ConditionResult],
    missing_slots: list[str],
    conflict: bool,
) -> Decision:
    failed = [c for c in conditions if c.result == "fail"]
    if sc >= SC_REFUTE:
        return Decision("Refuted", f"Challenging evidence is strong (SC {sc:.2f} >= {SC_REFUTE:.2f}).")
    if failed:
        names = ", ".join(f"{c.field} {c.op} {c.expected}" for c in failed)
        return Decision("Refuted", f"Mandatory condition failed: {names}.")

    missing = list(missing_slots) + [c.field for c in conditions if c.result == "missing"]
    if missing:
        uniq = ", ".join(dict.fromkeys(missing))
        return Decision("Unresolved", f"Required input missing: {uniq}.")
    if conflict:
        return Decision("Unresolved", "Active sources of equal authority conflict.")

    if se > SE_VERIFY and sc < SC_VERIFY:  # all conditions passed (none failed or missing)
        return Decision("Verified", f"Strong support (SE {se:.2f}), little challenge (SC {sc:.2f}).")
    return Decision(
        "Unresolved",
        f"Evidence is not decisive (SE {se:.2f} must be > {SE_VERIFY:.2f} and SC {sc:.2f} < {SC_VERIFY:.2f}).",
    )


def overall_status(statuses: list[Status]) -> Status:
    if "Refuted" in statuses:
        return "Refuted"
    if not statuses or "Unresolved" in statuses:  # nothing checked is not Verified
        return "Unresolved"
    return "Verified"


@dataclass
class ScoredEvidence:
    evidence: Evidence
    passage: Passage


@dataclass
class Scores:
    se: float = 0.0
    sc: float = 0.0
    conflict: bool = False
    effects: dict[str, str] = field(default_factory=dict)


def _overrides(challenger: Passage, supporter: Passage) -> bool:
    """An amendment or a superseding document overrides the document it changes."""
    return challenger.parent_doc_id == supporter.doc_id or challenger.supersedes == supporter.doc_id


def score_evidence(items: list[ScoredEvidence]) -> Scores:
    """SE = strongest entailing evidence. SC = strongest contradicting evidence that
    overrides the best support (amendment/supersession or higher authority).
    An equal-authority contradiction with no override relationship is a conflict
    flag, not SC. A lower-authority contradiction is ignored (and recorded)."""
    scores = Scores()
    supports = [i for i in items if i.evidence.label == "entails"]
    best = max(supports, key=lambda i: i.evidence.score, default=None)
    if best is not None:
        scores.se = best.evidence.score
        scores.effects[best.evidence.passage_id] = "counts"

    for item in items:
        if item.evidence.label != "contradicts":
            continue
        pid = item.evidence.passage_id
        if best is None or _overrides(item.passage, best.passage) or item.passage.authority > best.passage.authority:
            scores.sc = max(scores.sc, item.evidence.score)
            scores.effects[pid] = "counts"
        elif item.passage.authority == best.passage.authority:
            scores.conflict = True
            scores.effects[pid] = "conflict"
        else:
            scores.effects[pid] = "ignored_lower_authority"
    return scores
