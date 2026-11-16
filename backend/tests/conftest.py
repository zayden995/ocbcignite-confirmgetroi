import pytest

from app import config


@pytest.fixture(autouse=True)
def scripted_llm_by_default(monkeypatch):
    """Tests run on the scripted MOCK LLM even when a developer's backend/.env holds a Gemini key.

    A test that needs another provider sets config.LLM_PROVIDER itself.
    """
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
