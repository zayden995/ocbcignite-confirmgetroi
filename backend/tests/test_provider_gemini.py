"""Gemini adapter over HTTP. Only the network call is faked: the adapter, the routes and the SDK's request types are real."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

import app.llm as llm_module
from app import config
from app.main import app

client = TestClient(app)

EXTRACTION = {
    "product": "SteadyGrowth",
    "params": {"deposit_amount": None, "tenor_months": 12, "channel": None},
    "conclusion": "Quote 3.20% p.a.",
    "claims": [
        {"id": "c1", "text": "The SteadyGrowth board rate is 3.20% p.a.", "cited_passage_ids": ["FD-101#p1"], "required_slots": []}
    ],
}


class FakeGeminiModels:
    """Stands in for client.models: records each prompt and returns a canned reply of the requested shape."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.error: Exception | None = None  # set to make every call fail the way the SDK does

    def generate_content(self, *, model, contents, config=None):
        if self.error is not None:
            raise self.error
        # The real SDK validates the request settings before sending; unknown settings are rejected here too.
        types.GenerateContentConfig.model_validate(config or {})
        self.prompts.append(contents)
        schema = getattr((config or {}).get("response_schema"), "__name__", "")
        if schema == "_GeminiExtraction":
            return SimpleNamespace(text=json.dumps(EXTRACTION))
        if schema == "_BatchNLIResponse":
            return SimpleNamespace(text=json.dumps({"results": []}))
        return SimpleNamespace(text="Quote 3.20% p.a. [Sources: FD-101#p1]")

    def extract_prompts(self) -> list[str]:
        return [p for p in self.prompts if "claim extraction engine" in p]


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm_module, "_INSTANCE", None)
    monkeypatch.setattr(llm_module, "_PROVIDER_NAME", None)
    fake = FakeGeminiModels()
    monkeypatch.setattr(llm_module.get_llm(), "_client", SimpleNamespace(models=fake))
    return fake


def _ask(question: str, history: list[dict] | None = None):
    body = {"question": question, "role": "RM", "region": "SG"}
    if history is not None:
        body["history"] = history
    return client.post("/api/ask", json=body)


def _verify_custom(question: str, history: list[dict] | None = None):
    body = {"question": question, "ai_answer": "Quote 3.20% p.a. [Sources: FD-101#p1]", "role": "RM", "region": "SG"}
    if history is not None:
        body["history"] = history
    return client.post("/api/verify-custom", json=body)


def test_gemini_requests_use_settings_the_installed_sdk_accepts(gemini):
    assert _ask("What rate can I quote on SteadyGrowth?").status_code == 200
    assert _verify_custom("What rate can I quote on SteadyGrowth?").status_code == 200


def test_ask_does_not_remember_an_earlier_request(gemini):
    _ask("First visitor asks about a cheque deposit of 77777")
    _ask("What is the SteadyGrowth board rate?")
    assert "77777" not in gemini.prompts[-1]


def test_ask_uses_the_history_sent_with_the_request(gemini):
    _ask(
        "What if they use FAST?",
        history=[{"question": "Earlier question about 55555 dollars", "ai_answer": "Earlier answer about 3.20%"}],
    )
    assert "Earlier question about 55555 dollars" in gemini.prompts[-1]
    assert "Earlier answer about 3.20%" in gemini.prompts[-1]


def test_verify_custom_does_not_reuse_an_earlier_conversation(gemini):
    _ask("First visitor asks about a cheque deposit of 77777")
    _verify_custom("What is the SteadyGrowth board rate?")
    assert "77777" not in gemini.extract_prompts()[-1]


def test_verify_custom_carries_the_channel_over_from_the_history_sent_with_the_request(gemini):
    r = _verify_custom(
        "What rate can I quote?",
        history=[{"question": "My customer will fund the deposit by FAST", "ai_answer": "Noted."}],
    )
    assert r.status_code == 200
    assert r.json()["employee"]["params"]["channel"] == "FAST"


def test_scripted_scenarios_run_on_gemini_without_the_mock_badge(gemini):
    assert client.get("/api/meta").json()["llm_badge"] is None
    r = client.post("/api/verify", json={"scenario_id": "s1_overlooked_exception", "role": "RM", "region": "SG"})
    assert r.status_code == 200
    body = r.json()
    assert (body["llm_mode"], body["llm_badge"]) == ("gemini", None)
    assert body["claims"], "the scripted answer was split into claims by the model"
    # nothing scripted leaks into Gemini mode: any proposed correction is derived from the policy text
    assert all((c["proposed_correction"] or {"source": "derived"})["source"] == "derived" for c in body["claims"])


def test_run_all_scenarios_works_on_gemini(gemini):
    s = client.get("/api/summary").json()
    assert s["llm_badge"] is None
    assert s["total"] == 5 and all(row["tree"] in ("Verified", "Unresolved", "Refuted") for row in s["scenarios"])


def test_a_gemini_failure_is_reported_clearly_instead_of_a_bare_500(gemini):
    gemini.error = errors.ClientError(
        429, {"error": {"code": 429, "message": "Quota exceeded for this model", "status": "RESOURCE_EXHAUSTED"}}
    )
    r = client.post("/api/verify", json={"scenario_id": "s1_overlooked_exception", "role": "RM", "region": "SG"})
    assert r.status_code == 502
    assert "Gemini" in r.json()["detail"] and "Quota exceeded for this model" in r.json()["detail"]


def test_typed_questions_without_a_key_say_how_to_switch_gemini_on():
    r = _ask("What rate can I quote on SteadyGrowth?")
    assert r.status_code == 400
    assert "GEMINI_API_KEY" in r.json()["detail"]
