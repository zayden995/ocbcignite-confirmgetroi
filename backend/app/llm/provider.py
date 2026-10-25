"""Real-provider adapter STUB. Provider and key are decided later.

Select with TREE_LLM_PROVIDER=<name>. No vendor is hard-coded: implement
extract() and nli() here (calling whichever SDK is chosen) and nothing else
in TREE needs to change. Until then every call fails loudly, with no silent
fallback to mock outputs.
"""
from __future__ import annotations

from ..models import Claim, Extraction, NLIResult, Passage


class ProviderLLM:
    is_mock = False

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def _not_implemented(self, what: str) -> NotImplementedError:
        return NotImplementedError(
            f"LLM provider '{self.provider}' is selected but {what}() is not implemented. "
            "Implement it in backend/app/llm/provider.py or unset TREE_LLM_PROVIDER to use the mock."
        )

    def extract(self, question: str, answer: str) -> Extraction:
        raise self._not_implemented("extract")

    def nli(self, claim: Claim, passage: Passage) -> NLIResult:
        raise self._not_implemented("nli")
