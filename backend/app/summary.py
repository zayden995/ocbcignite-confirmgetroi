"""Baseline vs TREE across the scripted scenarios.

This is a small hand-built demo set: the scenarios were written to contain the failures TREE looks
for, and the model outputs are scripted in mock mode. The numbers illustrate the pipeline; they are
not a benchmark and must never be presented as measured accuracy.
"""
from __future__ import annotations

from datetime import date

from . import config
from .corpus import Corpus
from .llm.base import LLM
from .pipeline import MOCK_BADGE, run_tree
from .scenarios import load_scenarios

SUMMARY_LABEL = "Scripted demo set, not a benchmark"


def run_summary(corpus: Corpus, llm: LLM, today: date = config.DEMO_DATE) -> dict:
    rows = []
    for s in load_scenarios():
        emp = s["employee"]
        tree = run_tree(s, emp["role"], emp["region"], {}, llm=llm, corpus=corpus, today=today)
        expected = s["expected_overall"]
        rows.append(
            {
                "id": s["id"],
                "title": s["title"],
                "expected": expected,
                "baseline": tree.baseline.status,
                "tree": tree.overall.status,
                "baseline_correct": tree.baseline.status == expected,
                "tree_correct": tree.overall.status == expected,
            }
        )
    return {
        "label": SUMMARY_LABEL,
        "llm_badge": MOCK_BADGE if llm.is_mock else None,
        "total": len(rows),
        "baseline_correct": sum(r["baseline_correct"] for r in rows),
        "tree_correct": sum(r["tree_correct"] for r in rows),
        "scenarios": rows,
    }
