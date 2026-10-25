"""The deterministic verification matrix, boundaries included."""
import pytest

from app.models import ConditionResult, Evidence, Passage
from app.verify import ScoredEvidence, overall_status, score_evidence, verify_claim


def cond(result):
    return ConditionResult(field="x", op=">=", expected=1, actual=None, result=result)


# --- verify_claim: matrix order Refuted > Unresolved > Verified -------------

@pytest.mark.parametrize(
    "se,sc,expected",
    [
        (0.90, 0.30, "Unresolved"),   # the spec's example: do not leave gaps
        (0.90, 0.05, "Verified"),
        (0.851, 0.149, "Verified"),
        (0.85, 0.05, "Unresolved"),   # SE must be strictly > 0.85
        (0.90, 0.15, "Unresolved"),   # SC must be strictly < 0.15
        (0.90, 0.499, "Unresolved"),
        (0.90, 0.50, "Refuted"),      # SC >= 0.50 is inclusive
        (0.00, 0.50, "Refuted"),
        (0.00, 0.00, "Unresolved"),   # no evidence either way
        (0.99, 0.99, "Refuted"),
    ],
)
def test_threshold_boundaries(se, sc, expected):
    assert verify_claim(se, sc, [], [], False).status == expected


def test_failed_mandatory_condition_forces_refuted_even_with_perfect_evidence():
    d = verify_claim(0.99, 0.0, [cond("fail")], [], False)
    assert d.status == "Refuted"


def test_missing_slots_are_unresolved_even_with_perfect_evidence():
    d = verify_claim(0.99, 0.0, [cond("missing")], ["deposit_amount"], False)
    assert d.status == "Unresolved"


def test_refuted_takes_precedence_over_missing_slots_and_conflict():
    assert verify_claim(0.2, 0.7, [], ["deposit_amount"], True).status == "Refuted"
    assert verify_claim(0.99, 0.0, [cond("fail"), cond("missing")], ["a"], True).status == "Refuted"


def test_conflict_is_unresolved_even_with_perfect_evidence():
    assert verify_claim(0.99, 0.0, [], [], True).status == "Unresolved"


def test_all_conditions_pass_allows_verified():
    assert verify_claim(0.95, 0.02, [cond("pass"), cond("pass")], [], False).status == "Verified"


def test_every_decision_carries_a_reason():
    assert verify_claim(0.9, 0.3, [], [], False).reason


# --- overall rollup ---------------------------------------------------------

def test_overall_rollup():
    assert overall_status(["Verified", "Verified"]) == "Verified"
    assert overall_status(["Verified", "Unresolved"]) == "Unresolved"
    assert overall_status(["Unresolved", "Refuted", "Verified"]) == "Refuted"
    assert overall_status([]) == "Unresolved"  # nothing verified -> not Verified


# --- evidence scoring: authority, amendments, and the equal-authority conflict ---

def passage(pid, doc, authority, **kw):
    base = dict(
        passage_id=pid, doc_id=doc, title=doc, version="1", effective_date="2026-01-01",
        expiry_date="2026-12-31", status="active", region=["SG"], role_scope=["RM"],
        product="P", authority=authority, source={"hub": "h", "path": "/p"}, text=pid,
    )
    base.update(kw)
    return Passage.model_validate(base)


def se_item(pid, doc, authority, score=0.9, **kw):
    return ScoredEvidence(
        Evidence(passage_id=pid, role="supports", label="entails", score=score),
        passage(pid, doc, authority, **kw),
    )


def sc_item(pid, doc, authority, score=0.8, **kw):
    return ScoredEvidence(
        Evidence(passage_id=pid, role="challenges", label="contradicts", score=score),
        passage(pid, doc, authority, **kw),
    )


def test_se_is_max_entailment_and_sc_max_contradiction():
    s = score_evidence([se_item("a", "A", 2, 0.7), se_item("b", "B", 2, 0.9), sc_item("c", "C", 3, 0.4)])
    assert s.se == 0.9 and s.sc == 0.4 and not s.conflict


def test_neutral_evidence_counts_for_nothing():
    n = ScoredEvidence(Evidence(passage_id="n", role="supports", label="neutral", score=0.99), passage("n", "N", 2))
    s = score_evidence([n])
    assert (s.se, s.sc, s.conflict) == (0.0, 0.0, False)


def test_equal_authority_contradiction_is_a_conflict_flag_not_sc():
    s = score_evidence([se_item("a", "A", 2), sc_item("b", "B", 2, 0.85)])
    assert s.conflict is True
    assert s.sc == 0.0
    assert s.effects["b"] == "conflict"
    # ...so the matrix lands on Unresolved, never Refuted
    assert verify_claim(s.se, s.sc, [], [], s.conflict).status == "Unresolved"


def test_higher_authority_contradiction_counts_toward_sc():
    s = score_evidence([se_item("a", "A", 2), sc_item("b", "B", 3, 0.85)])
    assert s.sc == 0.85 and not s.conflict and s.effects["b"] == "counts"


def test_lower_authority_contradiction_is_ignored_but_recorded():
    s = score_evidence([se_item("a", "A", 3), sc_item("b", "B", 1, 0.95)])
    assert s.sc == 0.0 and not s.conflict and s.effects["b"] == "ignored_lower_authority"


def test_amendment_overrides_its_parent_despite_equal_authority():
    s = score_evidence([se_item("FD-101#p2", "FD-101", 3), sc_item("FD-102#p1", "FD-102", 3, 0.9, parent_doc_id="FD-101")])
    assert s.sc == 0.9 and not s.conflict and s.effects["FD-102#p1"] == "counts"


def test_superseding_document_overrides_the_old_one():
    s = score_evidence([se_item("FD-300#p1", "FD-300", 3), sc_item("FD-301#p1", "FD-301", 3, 0.9, supersedes="FD-300")])
    assert s.sc == 0.9 and not s.conflict


def test_no_supporting_evidence_means_any_contradiction_counts():
    s = score_evidence([sc_item("b", "B", 1, 0.7)])
    assert s.sc == 0.7 and not s.conflict
