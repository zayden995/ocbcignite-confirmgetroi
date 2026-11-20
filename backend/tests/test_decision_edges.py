from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v2/assess"


def request():
    return deepcopy(client.get("/api/meta").json()["assessment_fixture"])


def test_assistant_amount_cannot_fill_employee_fact():
    req = request()
    req["facts"] = [f for f in req["facts"] if f["key"] != "transfer_cents"]
    req["question"] = "What rate applies and can one FAST transfer fit? I do not know its amount."
    req["history"] = [{"turn_id": "prior", "question": "What is FAST?", "answer": "One FAST transfer of S$150,000."}]
    req["answer"] += " A single S$150,000 FAST transfer exceeds the S$100,000 per-transfer limit."
    result = client.post(URL, json=req).json()
    assert result["next"]["fields"] == ["transfer_cents"]
    req["facts"].append({"key": "transfer_cents", "value": 15_000_000, "origin": {"kind": "form", "ref": "Single transfer"}})
    req["input_revision"] += 1
    assert client.post(URL, json=req).json()["verdict"] == "ready"
    req["facts"][-1]["value"] = 10_000_000
    req["facts"] = [f for f in req["facts"] if f["key"] != "deposit_cents"]
    req["input_revision"] += 1
    assert client.post(URL, json=req).json()["branches"][1]["status"] == "wrong"


def test_employee_text_must_establish_value_and_subject():
    req = request()
    f = req["facts"][-1]
    req["history"] = [{"turn_id": "earlier", "question": "One FAST transfer of S$150,000.", "answer": ""}]
    text = req["history"][0]["question"]
    start = text.index("S$")
    f["origin"] = {"kind": "employee_text", "ref": "earlier", "span": {"start": start, "end": start+9, "quote": "S$150,000"}}
    assert client.post(URL, json=req).status_code == 200
    req["history"][0]["question"] = text.replace("One FAST transfer", "My entire deposit")
    assert client.post(URL, json=req).status_code == 422
    req["history"][0]["question"] = text + " An assistant guessed this."
    f["origin"]["span"]["end"] -= 1
    assert client.post(URL, json=req).status_code == 422


@pytest.mark.parametrize("change,code", [
    ({"as_of": "2026-02-30"}, 422), ({"confirmation": {"input_revision": 2, "choice": "rate_only"}}, 422),
    ({"question": "  "}, 422), ({"bundle_id": "absent"}, 404),
    ({"history": [{"turn_id":"hero", "question":"x", "answer":""}]}, 422),
])
def test_invalid_request(change, code):
    assert client.post(URL, json={**request(), **change}).status_code == code


def test_conflict_and_partial_intent_hold():
    req = request()
    req["facts"].append({"key":"currency", "value":"USD", "origin":{"kind":"form", "ref":"employee"}})
    assert client.post(URL, json=req).json()["next"]["fields"] == ["currency"]
    req["question"] += " Also quote the withdrawal fee."
    result = client.post(URL, json=req).json()
    assert result["reasons"] == ["unsupported_task"] and "withdrawal" in result["next"]["prompt"]


@pytest.mark.parametrize("wording,status", [
    ("This transfer exceeds the cap.", "covered"), ("It might fit.", "uncertain_text"),
    ("Someone told me it fits, but that is incorrect.", "uncertain_text"),
    ("S$100,000 per day.", "omitted"), ("This transfer is within the cap.", "wrong"),
    ("A single S$90,000 FAST transfer exceeds the S$100,000 per-transfer limit.", "wrong"),
    ("A single S$150,000 FAST transfer exceeds the S$110,000 per-transfer limit.", "wrong"),
])
def test_assertion_semantics(wording, status):
    req = request()
    req["answer"] += " " + wording
    result = client.post(URL, json=req).json()
    assert result["branches"][1]["status"] == status


def test_fourth_sentence_offsets_and_repeat_with_another_turn_id():
    req = request()
    req["answer"] += " This transfer exceeds the cap. 🙂. Settlement is guaranteed."
    first = client.post(URL, json=req).json()
    assert first["coverage"] == {"covered":2, "required":2} and first["verdict"] == "hold"
    span = first["extras"][-1]["span"]
    assert req["answer"][span["start"]:span["end"]] == span["quote"] == "Settlement is guaranteed."
    req["turn_id"] = "different"
    again = client.post(URL, json=req).json()
    assert again["branches"] == first["branches"] and again["extras"] == first["extras"]


def test_explicit_whole_transfer_links_amount_but_generic_placement_does_not():
    req = request()
    req["facts"] = [f for f in req["facts"] if not f["key"].endswith("_cents")]
    result = client.post(URL, json=req).json()
    assert result["branches"][1]["expected"]["within_cap"] is False
    assert "Employee turn hero" in result["branches"][1]["explanation"]
    req["question"] = "My customer has a S$150,000 deposit. What rate applies and can one FAST transfer fit?"
    result = client.post(URL, json=req).json()
    assert result["next"]["fields"] == ["transfer_cents"]


def test_conditional_rate_and_mixed_use():
    req = request()
    req["facts"] = [f for f in req["facts"] if f["key"] != "deposit_cents"]
    req["question"] = "Quote the standard rate for a qualifying placement."
    assert client.post(URL, json=req).json()["verdict"] == "ready"
    req["question"] = "Quote the standard rate for my actual deposit."
    assert client.post(URL, json=req).json()["next"]["fields"] == ["deposit_cents"]
    req["question"] += " Also recommend an investment."
    assert client.post(URL, json=req).json()["reasons"] == ["unsupported_task"]


def test_amounts_and_fixture_refs_are_strict():
    req = request()
    for value in (0, -1, True, "15000000", 15.5, 2**53):
        req["facts"][-1]["value"] = value
        assert client.post(URL, json=req).status_code == 422
    req["facts"][-1]["value"] = 99
    assert client.post(URL, json=req).status_code == 422
