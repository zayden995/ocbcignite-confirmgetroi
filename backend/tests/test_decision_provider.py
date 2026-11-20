import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import types

import app.llm as llm
from app import config
from app.llm.accounting import billing_categories, estimate, PRICE_TABLE
from app.main import app

client = TestClient(app)


def test_categories_and_price_intervals():
    usage = billing_categories(types.GenerateContentResponseUsageMetadata(
        prompt_token_count=1000, cached_content_token_count=200, candidates_token_count=10, thoughts_token_count=90))
    assert usage == {"input":800, "cached":200, "output":10, "thinking":90}
    assert Decimal(estimate("gemini-3.8-flash", usage, "2026-11-20", PRICE_TABLE)) == Decimal("0.000990")
    assert Decimal(estimate("gemini-3.8-flash", usage, "2027-01-01", PRICE_TABLE)) == Decimal("0.001980")
    assert estimate("unknown", usage, "2026-11-20", PRICE_TABLE) is None
    assert estimate("gemini-3.8-flash", billing_categories({"totalTokenCount": 1000}), "2026-11-20", PRICE_TABLE) is None


def test_live_unavailable_without_credentials():
    req = client.get("/api/meta").json()["assessment_fixture"]
    response = client.post("/api/v2/assess?mode=live", json=req)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


@pytest.mark.parametrize("misaligned", [True, False])
def test_live_observations_are_anchored_and_incomplete_inventory_cannot_clear(monkeypatch, misaligned):
    req = client.get("/api/meta").json()["assessment_fixture"]
    rate = req["answer"]
    req["answer"] += " This transfer exceeds the cap. The bank guarantees immediate settlement."
    monkeypatch.setenv("GEMINI_API_KEY", "simulated")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm, "_INSTANCE", None)
    prompts = []

    def respond(*, model, contents, config):
        types.GenerateContentConfig.model_validate(config)
        prompts.append(contents)
        if config["response_schema"].__name__ == "Inventory":
            json_body = {"observations": [{
                "span":{"start":0, "end":len(rate), "quote":"invented" if misaligned else rate},
                "subject":"deposit_rate", "meaning":"annual_rate", "rate_bps":999}]}
        else:
            json_body = {"results":[]}
        return SimpleNamespace(text=json.dumps(json_body))

    monkeypatch.setattr(llm.get_llm(), "_client", SimpleNamespace(models=SimpleNamespace(generate_content=respond)))
    response = client.post("/api/v2/assess?mode=live", json=req)
    attempts = json.loads(response.headers["X-Tree-Attempts"])
    assert len(attempts) == len(prompts)
    assert all(a["estimate"] is None and a["usage"] is None for a in attempts)
    assert "FD-301" not in prompts[0] and "rate_bps = 260" not in prompts[0]
    if misaligned:
        assert response.status_code == 502 and "aligned" in response.json()["detail"]
    else:
        assert response.status_code == 200
        result = response.json()
        assert result["coverage"] == {"covered":2,"required":2} and result["verdict"] == "hold"
        assert result["extras"][0]["span"]["quote"] == "The bank guarantees immediate settlement."


def test_live_intent_reads_only_employee_words_and_requests_confirmation(monkeypatch):
    req = client.get("/api/meta").json()["assessment_fixture"]
    req.update(question="My customer is considering a FAST-funded deposit. What should I tell them?",
               answer="SECRET_ASSISTANT_TEXT", history=[{"turn_id":"prior", "question":"New customer", "answer":"PRIVATE_HISTORY"}])
    monkeypatch.setenv("GEMINI_API_KEY", "simulated")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm, "_INSTANCE", None)

    def respond(*, model, contents, config):
        assert req["answer"] not in contents and "PRIVATE_HISTORY" not in contents
        assert config["response_schema"].__name__ == "IntentReading"
        quote = "What should I tell them?"
        return SimpleNamespace(text=json.dumps({"choice":"rate_only","evidence":[{
            "start":req["question"].index(quote), "end":len(req["question"]), "quote":quote
        }]}))

    monkeypatch.setattr(llm.get_llm(), "_client", SimpleNamespace(models=SimpleNamespace(generate_content=respond)))
    response = client.post("/api/v2/assess?mode=live", json=req)
    assert response.status_code == 200
    assert response.json()["task_id"] is None and response.json()["next"]["kind"] == "clarify_intent"
    assert len(json.loads(response.headers["X-Tree-Attempts"])) == 1
