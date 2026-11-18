from __future__ import annotations

from .. import config
from .base import LLM
from .mock import MockLLM
from .provider import ProviderLLM

_INSTANCE: LLM | None = None
_PROVIDER_NAME: str | None = None


def get_llm() -> LLM:
    """MOCK by default; TREE_LLM_PROVIDER=<name> selects the real-provider adapter."""
    global _INSTANCE, _PROVIDER_NAME
    if config.LLM_PROVIDER == "mock":
        return MockLLM()
    if _INSTANCE is None or _PROVIDER_NAME != config.LLM_PROVIDER:
        _INSTANCE = ProviderLLM(config.LLM_PROVIDER)
        _PROVIDER_NAME = config.LLM_PROVIDER
    return _INSTANCE


def get_scenario_llm() -> LLM:
    """The model for the four scripted demo scenarios: always the scripted fixtures.

    Even with a Gemini key the scenarios keep their designed verdicts and answer instantly; Gemini
    answers only the questions people type (/api/ask and /api/verify-custom use get_llm()).
    """
    return MockLLM()
