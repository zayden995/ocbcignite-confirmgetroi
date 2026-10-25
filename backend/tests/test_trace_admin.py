"""Pipeline trace (for the admin view) and the read-only admin endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.config import DEMO_DATE
from app.corpus import load_corpus
from app.llm.mock import MockLLM
from app.main import app
from app.pipeline import run_tree
from app.scenarios import get_scenario

client = TestClient(app)


@pytest.fixture(scope="module")
def tree():
    return run_tree(get_scenario("s1_overlooked_exception"), "RM", "SG", {}, llm=MockLLM(), corpus=load_corpus(), today=DEMO_DATE)


def c3(tree):
    return next(c for c in tree.claims if c.id == "s1.c3")


def test_investigate_trace_shows_usable_and_unusable_citations(tree):
    cands = {x.passage_id: x for x in c3(tree).trace.investigate}
    assert cands["FD-101#p2"].via == "cited" and cands["FD-101#p2"].outcome == "supports"
    assert cands["FD-101#p2"].nli_label == "entails"
    # the unapproved wiki is cited but never reaches NLI
    assert cands["FD-500#p1"].state == "filtered_not_approved"
    assert cands["FD-500#p1"].outcome == "not_usable" and cands["FD-500#p1"].nli_label is None


def test_challenge_trace_runs_every_template_and_records_what_it_found(tree):
    queries = c3(tree).trace.challenge
    assert [q.template for q in queries] == ["unless {c}", "exception for {c}", "superseded by {c}", "does not apply when {c}", "only if {c}"]
    found = [h for q in queries for h in q.hits if h.passage_id == "FD-102#p1" and h.outcome == "challenge"]
    assert len(found) == 1 and found[0].nli_label == "contradicts"
    # the evidence record names the same query that surfaced it
    ev = next(e for e in c3(tree).evidence if e.passage_id == "FD-102#p1")
    assert any(q.query == ev.counter_query and any(h.passage_id == "FD-102#p1" for h in q.hits) for q in queries)


def test_verify_trace_matches_the_decision(tree):
    v = c3(tree).trace.verify
    assert (v.se, v.sc, v.status, v.reason) == (0.88, 0.93, "Refuted", c3(tree).reason)


def test_admin_corpus_lists_every_passage_with_state_for_the_employee():
    r = client.get("/api/admin/corpus", params={"role": "RM", "region": "SG"}).json()
    rows = {p["passage_id"]: p for p in r["passages"]}
    assert len(rows) == 16
    assert rows["FD-500#p1"]["approved"] is False and rows["FD-500#p1"]["state"] == "filtered_not_approved"
    assert rows["FD-300#p1"]["state"] == "filtered_expired"
    assert rows["FD-102#p1"]["state"] == "active" and len(rows["FD-102#p1"]["hash"]) == 64
    assert r["approved_sources"][0]["hub"] == "synthetic-policy-hub"


def test_admin_corpus_state_depends_on_employee_region():
    my = {p["passage_id"]: p for p in client.get("/api/admin/corpus", params={"role": "RM", "region": "MY"}).json()["passages"]}
    assert my["FD-320#p1"]["state"] == "filtered_inapplicable"


def test_admin_config_exposes_the_matrix_and_mode():
    c = client.get("/api/admin/config").json()
    assert c["thresholds"] == {"refute_sc": 0.5, "verify_se": 0.85, "verify_sc": 0.15}
    assert len(c["counter_templates"]) == 5
    assert c["demo_date"] == "2026-10-28" and c["llm_mode"] == "mock"
    assert c["passage_count"] == 16
