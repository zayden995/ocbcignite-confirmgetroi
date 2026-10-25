"""Orchestrates INVESTIGATE -> CHALLENGE -> VERIFY into a Proof Tree."""
from __future__ import annotations

from datetime import date
from typing import Any

from . import config
from .baseline import run_baseline
from .challenge import challenge_claim, classify_failures
from .context import RunContext
from .corpus import Corpus
from .corrections import propose_correction
from .investigate import investigate_claim
from .llm.base import LLM
from .models import ClaimNode, Employee, Overall, ProofTree, Status, Trunk
from .scenarios import load_slot_defs
from .tree import build_edges, build_missing_inputs, build_roots
from .verify import ScoredEvidence, overall_status, score_evidence, verify_claim

MOCK_BADGE = "MOCK LLM (scripted outputs)"


def _actions(status: Status, missing: list[str]) -> list[str]:
    # stub actions for the demo: they are labels, not integrations
    if status == "Verified":
        return ["Mark as reviewed"]
    if status == "Refuted":
        return ["Apply proposed correction", "Add exception note", "Escalate to policy owner"]
    chips = ["Add caveat to answer", "Request policy owner review"]
    return (["Report missing input"] + chips) if missing else chips


def run_tree(
    scenario: dict,
    role: str,
    region: str,
    supplied_params: dict[str, Any],
    *,
    llm: LLM,
    corpus: Corpus,
    today: date = config.DEMO_DATE,
) -> ProofTree:
    extraction = llm.extract(scenario["question"], scenario["ai_answer"])
    supplied = {k: v for k, v in supplied_params.items() if v is not None and str(v).strip() != ""}
    employee = Employee(role=role, region=region, params={**extraction.params, **supplied})
    ctx = RunContext(corpus=corpus, llm=llm, employee=employee, today=today)

    nodes: list[ClaimNode] = []
    for claim in extraction.claims:
        inv = investigate_claim(claim, ctx)                      # 1. INVESTIGATE
        needed = challenge_claim(inv, ctx)                       # 2. CHALLENGE
        missing = list(dict.fromkeys(inv.missing_slots + needed))

        # 3. VERIFY: exceptions that are not triggered, or can't be judged yet, don't score
        scored = [
            ScoredEvidence(e, corpus.records[e.passage_id].passage)
            for e in inv.evidence
            if e.effect not in ("not_triggered", "needs_input")
        ]
        scores = score_evidence(scored)
        for e in inv.evidence:
            e.effect = e.effect or scores.effects.get(e.passage_id)
        decision = verify_claim(scores.se, scores.sc, inv.conditions, missing, scores.conflict)

        nodes.append(
            ClaimNode(
                id=claim.id, text=claim.text, status=decision.status, reason=decision.reason,
                se=scores.se, sc=scores.sc,
                failure_types=classify_failures(
                    decision.status, claim.cited_passage_ids, inv.evidence, inv.conditions, missing, scores.conflict, ctx
                ),
                cited_passage_ids=claim.cited_passage_ids,
                evidence=inv.evidence, conditions=inv.conditions, missing_slots=missing,
                proposed_correction=propose_correction(decision.status, inv, inv.evidence, missing, ctx),
                actions=_actions(decision.status, missing),
            )
        )

    overall = overall_status([n.status for n in nodes])
    bad = [n for n in nodes if n.status != "Verified"]
    reason = (
        "All claims verified."
        if not bad
        else f"{len(bad)} of {len(nodes)} claims not verified: " + "; ".join(f"{n.id} {n.status}" for n in bad) + "."
    )
    roots = build_roots(nodes, ctx)
    return ProofTree(
        scenario_id=scenario["id"], title=scenario["title"], demo_date=today,
        llm_mode="mock" if llm.is_mock else config.LLM_PROVIDER,
        llm_badge=MOCK_BADGE if llm.is_mock else None,
        data_label=config.DATA_LABEL,
        employee=employee, question=scenario["question"], answer=scenario["ai_answer"],
        overall=Overall(status=overall, reason=reason),
        baseline=run_baseline(extraction.claims, ctx),
        roots=roots, trunk=Trunk(text=extraction.conclusion, status=overall),
        claims=nodes, edges=build_edges(nodes, roots),
        missing_inputs=build_missing_inputs(nodes, load_slot_defs()),
    )
