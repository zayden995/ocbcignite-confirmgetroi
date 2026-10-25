"""Retrieval behind ONE function.

retrieve() is the swap point: a hybrid/semantic implementation can replace the
keyword-overlap scoring below without any other module changing. Whatever the
scoring, the contract is: only approved, hash-verified, fresh, applicable
passages are ever returned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .corpus import Corpus
from .filters import passage_state
from .models import Employee, Passage

# "not"/"no" are deliberately NOT stopwords: counter-queries ("does not apply when ...") rely on them.
_STOPWORDS = frozenset(
    "a an and are as at be by can for from has have if in is it its of on or that the this to was "
    "when which with will your you my what should do does".split()
)


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS}


@dataclass
class Hit:
    passage: Passage
    score: float


def retrieve(
    corpus: Corpus,
    query: str,
    employee: Employee,
    today: date,
    k: int = 5,
    min_score: float = 0.2,
) -> list[Hit]:
    q = _tokens(query)
    if not q:
        return []
    hits: list[Hit] = []
    for rec in corpus.searchable():
        if passage_state(rec, employee, today) != "active":
            continue
        p = rec.passage
        overlap = len(q & _tokens(p.title + " " + p.text))
        score = overlap / len(q)
        if score >= min_score:
            hits.append(Hit(p, score))
    hits.sort(key=lambda h: (-h.score, h.passage.passage_id))
    return hits[:k]
