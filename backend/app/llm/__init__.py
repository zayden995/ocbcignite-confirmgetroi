from __future__ import annotations

from .. import config
from .base import LLM
from .mock import MockLLM
from .provider import ProviderLLM


def get_llm() -> LLM:
    """MOCK by default; TREE_LLM_PROVIDER=<name> selects the real-provider adapter."""
    if config.LLM_PROVIDER == "mock":
        return MockLLM()
    return ProviderLLM(config.LLM_PROVIDER)
