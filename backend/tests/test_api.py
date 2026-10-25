from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_meta_reports_mock_mode_and_options():
    m = client.get("/api/meta").json()
    assert m["llm_badge"] == "MOCK LLM (scripted outputs)"
    assert m["demo_date"] == "2026-10-28"
    assert {r["code"] for r in m["roles"]} == {"RM", "BM", "CC"}
    assert m["scenarios"][0]["id"] == "s1_overlooked_exception"
    assert all(s["question"] for s in m["scenarios"])  # the chat box matches typed text against these


def test_verify_hero_over_http():
    r = client.post("/api/verify", json={"scenario_id": "s1_overlooked_exception", "role": "RM", "region": "SG"})
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["status"] == "Refuted"
    assert body["baseline"]["status"] == "Verified"


def test_unknown_scenario_is_404_and_bad_role_is_422():
    assert client.post("/api/verify", json={"scenario_id": "nope", "role": "RM", "region": "SG"}).status_code == 404
    assert client.post("/api/verify", json={"scenario_id": "s1_overlooked_exception", "role": "X", "region": "SG"}).status_code == 422


def test_real_provider_stub_fails_loudly_as_501(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "somevendor")
    r = client.post("/api/verify", json={"scenario_id": "s1_overlooked_exception", "role": "RM", "region": "SG"})
    assert r.status_code == 501 and "somevendor" in r.json()["detail"]
