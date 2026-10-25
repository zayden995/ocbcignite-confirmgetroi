class ScenarioNotFound(LookupError):
    """Unknown scenario id (maps to HTTP 404)."""


class NoScriptedFixture(LookupError):
    """MOCK LLM was asked about input it has no scripted output for (maps to HTTP 422)."""
