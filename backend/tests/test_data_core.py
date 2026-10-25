"""Step 1: ingestion (whitelist + hash), freshness and applicability filters."""
from datetime import date

import pytest

from app import corpus as corpus_mod
from app.config import DEMO_DATE
from app.filters import is_applicable, is_fresh, passage_state
from app.models import Employee


@pytest.fixture(scope="module")
def corpus():
    return corpus_mod.load_corpus()


def emp(role="RM", region="SG", **params):
    return Employee(role=role, region=region, params=params)


# --- hash verification -----------------------------------------------------

def test_compute_hash_is_sha256_hex():
    assert corpus_mod.compute_hash("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sealed_data_all_hashes_verify(corpus):
    assert corpus.records, "corpus is empty"
    assert all(r.hash_ok for r in corpus.records.values())


def test_tampered_passage_fails_hash_check_and_is_not_searchable():
    raw = corpus_mod.load_raw_passages()
    approved = corpus_mod.load_approved_sources()
    raw[1]["text"] = raw[1]["text"] + " (tampered)"
    c = corpus_mod.ingest(raw, approved)
    rec = c.records[raw[1]["passage_id"]]
    assert rec.hash_ok is False
    assert rec.passage.passage_id not in {r.passage.passage_id for r in c.searchable()}


def test_missing_hash_is_a_failure_not_a_pass():
    raw = corpus_mod.load_raw_passages()
    raw[0]["hash"] = None
    c = corpus_mod.ingest(raw, corpus_mod.load_approved_sources())
    assert c.records[raw[0]["passage_id"]].hash_ok is False


# --- approved-sources whitelist -------------------------------------------

def test_non_approved_passage_is_ingested_but_rejected(corpus):
    rec = corpus.records["FD-500#p1"]
    assert rec.approved is False
    assert "FD-500#p1" not in {r.passage.passage_id for r in corpus.searchable()}


def test_approved_passages_are_searchable(corpus):
    ids = {r.passage.passage_id for r in corpus.searchable()}
    assert "FD-101#p2" in ids and "FD-102#p1" in ids


def test_path_must_match_an_approved_prefix():
    approved = corpus_mod.load_approved_sources()
    assert corpus_mod.is_approved({"hub": "synthetic-policy-hub", "path": "/deposits/x"}, approved)
    assert not corpus_mod.is_approved({"hub": "synthetic-policy-hub", "path": "/secret/x"}, approved)
    assert not corpus_mod.is_approved({"hub": "other-hub", "path": "/deposits/x"}, approved)


def test_passage_state_reports_not_approved(corpus):
    assert passage_state(corpus.records["FD-500#p1"], emp(), DEMO_DATE) == "filtered_not_approved"


# --- freshness: effective_date <= today < expiry_date ----------------------

def test_is_fresh_boundaries(corpus):
    p = corpus.records["FD-101#p1"].passage  # 2026-01-01 .. 2026-12-31
    assert is_fresh(p, date(2026, 1, 1))            # effective day included
    assert is_fresh(p, date(2026, 12, 30))
    assert not is_fresh(p, date(2026, 12, 31))      # expiry day excluded
    assert not is_fresh(p, date(2025, 12, 31))      # before effective


def test_superseded_expired_passage_is_filtered_expired(corpus):
    assert not is_fresh(corpus.records["FD-300#p1"].passage, DEMO_DATE)
    assert passage_state(corpus.records["FD-300#p1"], emp(), DEMO_DATE) == "filtered_expired"


def test_current_replacement_is_active(corpus):
    assert passage_state(corpus.records["FD-301#p1"], emp(), DEMO_DATE) == "active"


def test_non_active_status_is_filtered_even_inside_date_window(corpus):
    rec = corpus.records["FD-101#p1"]
    rec2 = rec.model_copy(update={"passage": rec.passage.model_copy(update={"status": "draft"})})
    assert passage_state(rec2, emp(), DEMO_DATE) == "filtered_expired"


# --- applicability: region and role scope ---------------------------------

def test_region_restricted_policy(corpus):
    p = corpus.records["FD-320#p1"].passage  # SG only, RM/BM only
    assert is_applicable(p, "RM", "SG")
    assert not is_applicable(p, "RM", "MY")


def test_role_restricted_policy(corpus):
    p = corpus.records["FD-320#p1"].passage
    assert is_applicable(p, "BM", "SG")
    assert not is_applicable(p, "CC", "SG")


def test_passage_state_reports_inapplicable(corpus):
    assert passage_state(corpus.records["FD-320#p1"], emp(region="MY"), DEMO_DATE) == "filtered_inapplicable"
    assert passage_state(corpus.records["FD-320#p1"], emp(region="SG"), DEMO_DATE) == "active"


# --- relationships --------------------------------------------------------

def test_amendment_chain_is_traceable(corpus):
    assert corpus.records["FD-102#p1"].passage.parent_doc_id == "FD-101"
    assert corpus.records["FD-101#p1"].passage.supersedes == "FD-100"
    assert corpus.records["FD-301#p1"].passage.supersedes == "FD-300"
