"""Hero scenario (overlooked exception) end to end, plus retrieval and baseline."""
import pytest

from app.config import DEMO_DATE
from app.corpus import load_corpus
from app.llm.mock import MockLLM
from app.models import Employee
from app.pipeline import run_tree
from app.retrieval import retrieve
from app.scenarios import get_scenario


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(scope="module")
def tree(corpus):
    return run_tree(get_scenario("s1_overlooked_exception"), "RM", "SG", {}, llm=MockLLM(), corpus=corpus, today=DEMO_DATE)


def claim(tree, cid):
    return next(c for c in tree.claims if c.id == cid)


# --- retrieval --------------------------------------------------------------

def test_retrieval_only_returns_active_approved_passages(corpus):
    emp = Employee(role="RM", region="SG")
    ids = [h.passage.passage_id for h in retrieve(corpus, "FAST transfer limit per transaction retail", emp, DEMO_DATE, k=10)]
    assert "FD-301#p1" in ids
    assert "FD-300#p1" not in ids  # expired
    assert "FD-500#p1" not in ids  # not approved


def test_retrieval_respects_region(corpus):
    q = "relationship bonus rate Priority customers"
    sg = [h.passage.passage_id for h in retrieve(corpus, q, Employee(role="RM", region="SG"), DEMO_DATE)]
    my = [h.passage.passage_id for h in retrieve(corpus, q, Employee(role="RM", region="MY"), DEMO_DATE)]
    assert "FD-320#p1" in sg and "FD-320#p1" not in my


def test_retrieval_ranks_the_exception_first_for_a_counter_query(corpus):
    emp = Employee(role="RM", region="SG")
    hits = retrieve(corpus, "exception for The board rate applies to FAST deposits.", emp, DEMO_DATE)
    assert hits[0].passage.passage_id == "FD-102#p1"


# --- hero verdicts ---------------------------------------------------------------

def test_overall_is_refuted_while_baseline_passes(tree):
    assert tree.overall.status == "Refuted"
    assert tree.baseline.status == "Verified"


def test_claim_statuses(tree):
    assert [c.status for c in tree.claims] == ["Verified", "Refuted"]


def test_exception_claim_details(tree):
    c2 = claim(tree, "s1.c2")
    assert c2.se == 0.88 and c2.sc == 0.93
    assert c2.failure_types == ["overlooked_exception"]
    challenger = next(e for e in c2.evidence if e.role == "challenges")
    assert challenger.passage_id == "FD-102#p1"
    assert challenger.counter_query  # found by a counter-query template
    assert challenger.effect == "counts"
    assert c2.proposed_correction.passage_id == "FD-102#p1"
    assert "2.60%" in c2.proposed_correction.text


def test_verified_claim_has_no_failure_or_correction(tree):
    c = claim(tree, "s1.c1")
    assert c.failure_types == [] and c.proposed_correction is None


def test_conditions_are_evaluated_for_the_supported_claim(tree):
    # the rule behind the FAST claim carries a minimum deposit and a tenor; both pass for this case
    c2 = claim(tree, "s1.c2")
    assert {(r.field, r.result) for r in c2.conditions} == {("deposit_amount", "pass"), ("tenor_months", "pass")}


def test_roots_show_state_hash_and_whitelist_rejection(tree):
    roots = {r.id: r for r in tree.roots}
    assert roots["FD-500#p1"].state == "filtered_not_approved"
    assert roots["FD-500#p1"].state_label == "Filtered: not approved"
    assert roots["FD-102#p1"].state == "active" and roots["FD-102#p1"].hash_ok
    assert len(roots["FD-102#p1"].hash) == 64


def test_non_approved_source_gives_no_support_to_tree_but_fools_baseline(tree):
    c2 = claim(tree, "s1.c2")
    assert "FD-500#p1" not in {e.passage_id for e in c2.evidence}
    assert {(c.claim_id, c.passage_id) for c in tree.baseline.checks if c.entails} >= {("s1.c2", "FD-500#p1")}


def test_amendment_edge_points_at_the_passage_actually_amended(tree):
    # FD-101 has two passages in the tree; the exception amends the one that supports the claim, not just "the first"
    assert any(e.kind == "parent" and e.source == "FD-102#p1" and e.target == "FD-101#p2" for e in tree.edges)


def test_claim_to_passage_links_and_trunk(tree):
    kinds = {(e.source, e.target, e.kind) for e in tree.edges}
    assert ("FD-102#p1", "s1.c2", "challenges") in kinds
    assert ("FD-101#p2", "s1.c2", "supports") in kinds
    assert ("s1.c2", "conclusion", "claim_of") in kinds
    assert tree.trunk.status == "Refuted"


def test_payload_labels_mock_mode(tree):
    assert tree.llm_mode == "mock"
    assert tree.llm_badge == "MOCK LLM (scripted outputs)"
    assert tree.data_label == "Synthetic - not real OCBC policy"
    assert str(tree.demo_date) == "2026-10-28"
