"""Public development labels are used only on this side of the HTTP interface."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from app.main import app

CONTRACTS = Path(__file__).parent / "contracts"
CASES = json.loads((CONTRACTS / "development-cases.json").read_text(encoding="utf-8"))["cases"]
client = TestClient(app)


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_public_request(case):
    req, expected = case["request"], case["expected"]
    Draft7Validator(json.loads((CONTRACTS / "assessment-request.schema.json").read_text())).validate(req)
    response = client.post("/api/v2/assess", json=req)
    assert response.status_code == 200, response.text
    result = response.json()
    Draft7Validator(json.loads((CONTRACTS / "assessment-result.schema.json").read_text())).validate(result)
    assert result["coverage"] == expected["coverage"]
    assert result["task_id"] == expected["task_id"]
    assert result["verdict"] == expected["verdict"]
    assert {b["decision_id"]: b["status"] for b in result["branches"]} == expected["branch_statuses"]
    assert result["next"]["kind"] == expected["next_kind"]
    if expected.get("extra_must_block"):
        assert any(e["status"] != "supported" for e in result["extras"])
    for branch in result["branches"]:
        for span in branch["spans"]:
            assert req["answer"][span["start"]:span["end"]] == span["quote"]
    assert response.headers["x-tree-attempts"] == "[]"
