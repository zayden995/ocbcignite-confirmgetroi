"""All five scenarios, the Malaysia and input-supplied variants, and baseline-vs-TREE."""
import pytest
from fastapi.testclient import TestClient

from app.config import DEMO_DATE
from app.corpus import load_corpus
from app.llm.mock import MockLLM
from app.main import app
from app.pipeline import run_tree
from app.scenarios import get_scenario, load_scenarios
from app.summary import SUMMARY_LABEL, run_summary

client = TestClient(app)
IDS = [s["id"] for s in load_scenarios()]


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def run(corpus, sid, role="RM", region="SG", params=None):
    return run_tree(get_scenario(sid), role, region, params or {}, llm=MockLLM(), corpus=corpus, today=DEMO_DATE)


def claim(tree, cid):
    return next(c for c in tree.claims if c.id == cid)


# --- every scenario ---------------------------------------------------------

def test_there_are_five_scenarios():
    assert len(IDS) == 5


@pytest.mark.parametrize("sid", IDS)
def test_overall_matches_the_expected_verdict(corpus, sid):
    tree = run(corpus, sid)
    assert tree.overall.status == get_scenario(sid)["expected_overall"]


@pytest.mark.parametrize("sid", IDS)
def test_baseline_passes_every_scenario_because_citations_exist_and_entail(corpus, sid):
    assert run(corpus, sid).baseline.status == "Verified"


@pytest.mark.parametrize("sid", IDS)
def test_every_citation_pair_is_scripted(corpus, sid):
    llm = MockLLM()
    s = get_scenario(sid)
    for c in llm.extract(s["question"], s["ai_answer"]).claims:
        for pid in c.cited_passage_ids:
            assert llm.is_scripted(c, corpus.records[pid].passage), (c.id, pid)


@pytest.mark.parametrize("sid", IDS)
def test_non_verified_claims_carry_a_correction_and_verified_ones_do_not(corpus, sid):
    for c in run(corpus, sid).claims:
        assert (c.proposed_correction is not None) == (c.status != "Verified"), (c.id, c.status)


@pytest.mark.parametrize("sid", IDS)
def test_every_claim_links_to_passages_that_are_roots(corpus, sid):
    tree = run(corpus, sid)
    root_ids = {r.id for r in tree.roots}
    for c in tree.claims:
        assert {e.passage_id for e in c.evidence} <= root_ids
        assert set(c.cited_passage_ids) <= root_ids


# --- 2. conflicting documents ---------------------------------------------

def test_s2_equal_authority_conflict_is_unresolved_not_refuted(corpus):
    tree = run(corpus, "s2_conflicting_documents")
    c1 = claim(tree, "s2.c1")
    assert [c.status for c in tree.claims] == ["Unresolved", "Verified"]
    assert c1.sc == 0.0 and c1.se == 0.93  # the conflicting document is a flag, not SC
    assert c1.trace.verify.conflict is True
    assert c1.failure_types == ["conflicting_documents"]
    assert next(e for e in c1.evidence if e.passage_id == "FD-201#p1").effect == "conflict"
    assert c1.proposed_correction.passage_id == "FD-201#p1"


# --- 3. outdated or inapplicable ------------------------------------------

def test_s3_cited_policy_is_expired_and_superseded(corpus):
    tree = run(corpus, "s3_outdated_or_inapplicable")
    roots = {r.id: r for r in tree.roots}
    assert roots["FD-300#p1"].state == "filtered_expired"
    assert roots["FD-301#p1"].state == "active"
    c1 = claim(tree, "s3.c1")
    assert c1.status == "Refuted" and c1.se == 0.0 and c1.sc == 0.92
    assert c1.failure_types == ["outdated_or_inapplicable"]
    assert c1.proposed_correction.passage_id == "FD-301#p1" and "100,000" in c1.proposed_correction.text
    assert any(e.kind == "supersedes" and e.source == "FD-301#p1" and e.target == "FD-300#p1" for e in tree.edges)
    assert claim(tree, "s3.c2").status == "Verified"  # the per-transaction part is supported by the current policy


def test_s3_in_malaysia_the_singapore_policy_is_inapplicable(corpus):
    tree = run(corpus, "s3_outdated_or_inapplicable", region="MY")
    c1, c2 = claim(tree, "s3.c1"), claim(tree, "s3.c2")
    assert tree.overall.status == "Refuted"
    assert "FD-301#p1" not in {r.id for r in tree.roots if r.state == "active"}  # SG-only policy is filtered
    assert c1.status == "Refuted" and c1.failure_types == ["outdated_or_inapplicable"]
    assert c1.proposed_correction.passage_id == "FD-302#p1"
    assert "DuitNow" in c1.proposed_correction.text  # scripted text follows the evidence, not the SG variant
    assert c2.status == "Unresolved" and c2.proposed_correction is not None


# --- 4. unsupported assumption --------------------------------------------

def test_s4_missing_inputs_make_it_unresolved(corpus):
    tree = run(corpus, "s4_unsupported_assumption")
    c1 = claim(tree, "s4.c1")
    assert [c.status for c in tree.claims] == ["Unresolved", "Verified"]
    assert c1.missing_slots == ["deposit_amount", "channel"]
    assert c1.failure_types == ["unsupported_assumption"]
    assert [m.field for m in tree.missing_inputs] == ["deposit_amount", "channel"]
    assert next(m for m in tree.missing_inputs if m.field == "channel").options  # a select with choices
    # the exception cannot be judged without the channel, so it must not score
    assert next(e for e in c1.evidence if e.passage_id == "FD-102#p1").effect == "needs_input"
    assert c1.sc == 0.0


@pytest.mark.parametrize(
    "params,status,failure",
    [
        ({"deposit_amount": 5000, "channel": "GIRO"}, "Refuted", ["unsupported_assumption"]),   # fails the minimum
        ({"deposit_amount": 20000, "channel": "GIRO"}, "Verified", []),                          # exception not triggered
        ({"deposit_amount": 20000, "channel": "FAST"}, "Refuted", ["overlooked_exception"]),    # exception applies
        ({"deposit_amount": 20000}, "Unresolved", ["unsupported_assumption"]),                   # still missing the channel
    ],
)
def test_s4_supplying_inputs_reruns_the_real_conditions(corpus, params, status, failure):
    c1 = claim(run(corpus, "s4_unsupported_assumption", params=params), "s4.c1")
    assert (c1.status, c1.failure_types) == (status, failure)


def test_s4_scripted_correction_follows_the_outcome(corpus):
    small = claim(run(corpus, "s4_unsupported_assumption", params={"deposit_amount": 5000, "channel": "GIRO"}), "s4.c1")
    fast = claim(run(corpus, "s4_unsupported_assumption", params={"deposit_amount": 20000, "channel": "FAST"}), "s4.c1")
    assert "minimum" in small.proposed_correction.text
    assert "FAST" in fast.proposed_correction.text and fast.proposed_correction.passage_id == "FD-102#p1"


# --- 5. clean control ---------------------------------------------------------

def test_s5_clean_control_verifies_with_no_flags(corpus):
    tree = run(corpus, "s5_clean_control")
    assert tree.overall.status == "Verified"
    for c in tree.claims:
        assert c.status == "Verified" and c.failure_types == [] and c.missing_slots == []
        assert c.sc == 0.0 and c.se > 0.85


# --- baseline vs TREE ---------------------------------------------------------

def test_baseline_vs_tree_on_the_scripted_set(corpus):
    s = run_summary(corpus, MockLLM())
    assert s["label"] == SUMMARY_LABEL == "Scripted demo set, not a benchmark"
    assert s["llm_badge"] == "MOCK LLM (scripted outputs)"
    assert s["total"] == 5
    assert s["tree_correct"] == 5
    assert s["baseline_correct"] == 1  # only the clean control: it never searches for counter-evidence
    by_id = {r["id"]: r for r in s["scenarios"]}
    assert by_id["s5_clean_control"]["baseline_correct"] is True
    assert all(not by_id[i]["baseline_correct"] for i in IDS if i != "s5_clean_control")
    assert all(r["tree"] == r["expected"] for r in s["scenarios"])


def test_summary_endpoint():
    body = client.get("/api/summary").json()
    assert body["label"] == "Scripted demo set, not a benchmark"
    assert (body["baseline_correct"], body["tree_correct"], body["total"]) == (1, 5, 5)
