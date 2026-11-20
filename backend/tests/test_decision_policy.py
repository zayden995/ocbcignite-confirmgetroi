import copy
import json
from datetime import date
from graphlib import CycleError

import pytest

from app import config
from app.assessment.intake import FIXTURE, trusted_facts
from app.assessment.policy import Policy, metadata_digest
from app.corpus import compute_hash, load_approved_sources, load_raw_passages


def bundle():
    return json.loads((config.DATA_DIR / "decision_bundle.json").read_text())


def calculation(policy, day="2026-10-28", amount=9_000_000, decision="single_transfer", **changes):
    facts = {**trusted_facts(FIXTURE), "transfer_cents": amount, "deposit_cents": amount, **changes}
    return policy.calculate(decision, facts, FIXTURE.employee, date.fromisoformat(day))


def successor():
    raw = load_raw_passages()
    new = dict(next(p for p in raw if p["doc_id"] == "FD-301"),
               passage_id="FD-303#p1", doc_id="FD-303", version="3", supersedes="FD-301",
               effective_date="2026-11-01", expiry_date="2027-11-01",
               text="From 1 November the SG retail FAST single-transfer cap is SGD 80,000.")
    new["hash"] = compute_hash(new["text"])
    raw.append(new)
    return raw, new


def test_reviewed_amendment_rehearsal(monkeypatch):
    raw, new = successor()
    before = bundle()
    old = Policy(before, raw, load_approved_sources())
    october = calculation(old, "2026-10-31")
    assert october.branch.expected.within_cap and october.branch.expected.limit_cents == 10_000_000
    pending = calculation(old, "2026-11-01")
    assert pending.branch.status == "policy_review"
    assert any(r.passage_id == new["passage_id"] and r.state == "pending" for r in pending.roots)
    assert calculation(old, "2026-11-01", decision="deposit_rate").branch.expected.rate_bps == 260

    after = copy.deepcopy(before)
    after.update(bundle_id="sg-retail-nov", snapshot_id="synthetic-nov")
    after["source_revisions"].append(dict(passage_id=new["passage_id"], version="3",
                                          text_sha256=new["hash"], metadata_sha256=metadata_digest(new)))
    row = after["tables"]["single_transfer"][0]
    row.update(governing=new["passage_id"], source_ids=[new["passage_id"]], historical_predecessor="FD-301#p1",
               limit_cents=8_000_000, effective_from="2026-11-01", effective_until_exclusive="2027-11-01")
    current = Policy(after, raw, load_approved_sources())
    november = calculation(current, "2026-11-01")
    assert not november.branch.expected.within_cap
    assert "S$10,000" in november.branch.explanation
    assert calculation(current, "2026-11-01", 8_000_000).branch.expected.within_cap
    assert not calculation(current, "2026-11-01", 8_000_001).branch.expected.within_cap
    assert calculation(old, "2026-10-31") == october

    from fastapi.testclient import TestClient
    from app.assessment import routes
    from app.main import app
    client = TestClient(app)
    req = client.get("/api/meta").json()["assessment_fixture"]
    req.update(question="Can my customer fund the whole deposit in one FAST transfer, and what standard rate applies?",
               answer="The standard annual rate is 2.60%. This single transfer is within the published FAST cap.")
    for fact in req["facts"]:
        if fact["key"].endswith("_cents"):
            fact.update(value=9_000_000, origin={"kind":"form", "ref":fact["key"]})
    for policy, day, state in [(old, "2026-10-31", "covered"), (old, "2026-11-01", "policy_review"),
                               (current, "2026-11-01", "wrong"), (old, "2026-10-31", "covered")]:
        monkeypatch.setattr(routes, "POLICY", policy)
        result = client.post("/api/v2/assess", json={**req, "bundle_id":policy.bundle_id, "as_of":day}).json()
        assert [b["status"] for b in result["branches"]] == ["covered", state]


@pytest.mark.parametrize("mutate", [
    {"text": "Changed limit"}, {"role_scope": ["RM"]}, {"source": {"hub": "wiki", "path": "/transfers/unapproved"}},
])
def test_integrity_and_approval(mutate):
    raw = load_raw_passages()
    next(p for p in raw if p["doc_id"] == "FD-301").update(mutate)
    policy = Policy(bundle(), raw, load_approved_sources())
    c = calculation(policy)
    assert c.branch.status == "policy_review" and c.branch.expected is None
    assert any(r.state == "excluded" and r.passage_id == "FD-301#p1" for r in c.roots)
    assert calculation(policy, decision="deposit_rate").branch.expected.rate_bps == 260


def test_scope_conflicts_and_invalid_bundle():
    source = bundle()
    raw, new = successor()
    policy = Policy(source, raw, load_approved_sources())
    assert calculation(policy, booking_region="MY").branch.status == "policy_review"
    assert calculation(policy, amount=99_999, decision="deposit_rate").branch.status == "policy_review"
    new["supersedes"] = new["doc_id"]
    with pytest.raises(CycleError):
        Policy(source, raw, load_approved_sources())
    new["supersedes"] = "missing"
    with pytest.raises(ValueError, match="Broken"):
        Policy(source, raw, load_approved_sources())
    source["tables"]["single_transfer"][0]["comparison"] = "less_than"
    with pytest.raises(ValueError):
        Policy(source, load_raw_passages(), load_approved_sources())
