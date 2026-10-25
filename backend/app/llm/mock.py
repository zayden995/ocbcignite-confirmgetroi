"""MOCK LLM: scripted fixtures for the demo scenarios. Scores here are authored, not measured."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import DATA_DIR
from ..errors import NoScriptedFixture
from ..models import Claim, Extraction, NLIResult, Passage

_FIXTURES = Path(__file__).with_name("fixtures.json")


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class MockLLM:
    is_mock = True

    def __init__(self) -> None:
        self._fx = _load(_FIXTURES)
        scenarios = _load(DATA_DIR / "scenarios.json")["scenarios"]
        # extract(question, answer) has no scenario id, so match on the exact text pair
        self._by_text = {(s["question"].strip(), s["ai_answer"].strip()): s["id"] for s in scenarios}

    def extract(self, question: str, answer: str) -> Extraction:
        sid = self._by_text.get((question.strip(), answer.strip()))
        if sid is None or sid not in self._fx["extract"]:
            raise NoScriptedFixture("MOCK LLM has no scripted extraction for this question/answer pair")
        return Extraction.model_validate(self._fx["extract"][sid])

    def is_scripted(self, claim: Claim, passage: Passage) -> bool:
        return f"{claim.id}|{passage.passage_id}" in self._fx["nli"]

    def nli(self, claim: Claim, passage: Passage) -> NLIResult:
        entry = self._fx["nli"].get(f"{claim.id}|{passage.passage_id}")
        if entry is None:
            # unscripted pair == "no relation"; never an invented score
            return NLIResult(label="neutral", score=0.0)
        return NLIResult.model_validate(entry)

    def scripted_correction(self, claim_id: str, status: str, driver: str = "") -> dict | None:
        """Scripted corrected statement. Keyed by claim, outcome and the passage that drove the outcome
        ('' if none): the outcome and its cause change when the employee or inputs change, so must the script."""
        table = self._fx.get("corrections", {})
        return table.get(f"{claim_id}|{status}|{driver}") or table.get(f"{claim_id}|{status}")
