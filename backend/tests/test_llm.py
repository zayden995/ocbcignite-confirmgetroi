import json

import pytest

from app import config
from app.corpus import load_corpus
from app.llm import get_llm
from app.llm.mock import MockLLM
from app.llm.provider import ProviderLLM
from app.models import Claim

S1 = json.loads((config.DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))["scenarios"][0]


def test_default_provider_is_mock():
    assert isinstance(get_llm(), MockLLM)
    assert get_llm().is_mock is True


def test_mock_extract_returns_scripted_claims_for_the_scenario():
    ex = MockLLM().extract(S1["question"], S1["ai_answer"])
    assert [c.id for c in ex.claims] == ["s1.c1", "s1.c2", "s1.c3"]
    assert ex.params["channel"] == "FAST"
    assert ex.claims[2].required_slots == ["channel"]


def test_mock_extract_unknown_text_raises_instead_of_inventing():
    with pytest.raises(LookupError):
        MockLLM().extract("an unscripted question", "an unscripted answer")


def test_mock_nli_scripted_and_unscripted():
    llm = MockLLM()
    corpus = load_corpus()
    claim = Claim(id="s1.c3", text="x")
    hit = llm.nli(claim, corpus.records["FD-102#p1"].passage)
    assert (hit.label, hit.score) == ("contradicts", 0.93)
    # an unscripted pair is "no relation", never a made-up score
    miss = llm.nli(claim, corpus.records["FD-601#p1"].passage)
    assert (miss.label, miss.score) == ("neutral", 0.0)


def test_every_hero_citation_pair_is_scripted():
    llm = MockLLM()
    corpus = load_corpus()
    for claim in llm.extract(S1["question"], S1["ai_answer"]).claims:
        for pid in claim.cited_passage_ids:
            assert llm.is_scripted(claim, corpus.records[pid].passage), (claim.id, pid)


def test_unknown_provider_selects_stub_that_fails_loudly(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "somevendor")
    llm = get_llm()
    assert isinstance(llm, ProviderLLM) and llm.is_mock is False
    with pytest.raises(NotImplementedError, match="somevendor"):
        llm.extract("q", "a")
    with pytest.raises(NotImplementedError, match="somevendor"):
        llm.nli(Claim(id="c", text="t"), load_corpus().records["FD-101#p1"].passage)
