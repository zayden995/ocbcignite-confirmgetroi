"""Citation-only BASELINE: passes if the cited passage exists and entails the claim.

Deliberately naive. It applies no whitelist, freshness or scope filters and never
searches for counter-evidence. That is the behaviour TREE is compared against.
"""
from __future__ import annotations

from .context import RunContext
from .models import Baseline, BaselineCheck, Claim


def run_baseline(claims: list[Claim], ctx: RunContext) -> Baseline:
    checks: list[BaselineCheck] = []
    all_pass = True
    for claim in claims:
        claim_ok = False
        for pid in claim.cited_passage_ids:
            rec = ctx.corpus.get(pid)
            if rec is None:
                checks.append(BaselineCheck(claim_id=claim.id, passage_id=pid, exists=False, entails=False, score=0.0))
                continue
            r = ctx.nli(claim, rec.passage)
            entails = r.label == "entails"
            claim_ok = claim_ok or entails
            checks.append(BaselineCheck(claim_id=claim.id, passage_id=pid, exists=True, entails=entails, score=r.score))
        all_pass = all_pass and claim_ok
    # never Refuted: the baseline cannot disprove anything. If it cannot confirm, it is Unresolved.
    return Baseline(status="Verified" if all_pass and claims else "Unresolved", checks=checks)
