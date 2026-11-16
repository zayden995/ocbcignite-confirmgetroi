"""The single model interface. Everything else in TREE is plain code on top of these two calls."""
from __future__ import annotations

from typing import Protocol

from ..models import Claim, Extraction, NLIResult, Passage


class LLM(Protocol):
    #: True when outputs are scripted fixtures (drives the MOCK badge in the UI)
    is_mock: bool

    def extract(self, question: str, answer: str, history: list[tuple[str, str]] | None = None) -> Extraction:
        """Entities, case parameters and atomic claims (with their citations).

        history is the conversation's earlier (question, answer) turns, for follow-up questions.
        """
        ...

    def nli(self, claim: Claim, passage: Passage) -> NLIResult:
        """Does the passage entail / contradict / say nothing about the claim?"""
        ...
