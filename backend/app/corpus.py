"""Ingestion: approved-source whitelist and SHA-256 integrity check.

Every passage is recorded (so rejected ones can be shown in the UI), but only
passages that are approved AND hash-verified are searchable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import DATA_DIR
from .models import IngestedPassage, Passage


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_raw_passages(data_dir: Path = DATA_DIR) -> list[dict]:
    with open(data_dir / "passages.json", encoding="utf-8") as f:
        return json.load(f)["passages"]


def load_approved_sources(data_dir: Path = DATA_DIR) -> list[dict]:
    with open(data_dir / "approved_sources.json", encoding="utf-8") as f:
        return json.load(f)["approved"]


def is_approved(source: dict, approved: list[dict]) -> bool:
    """Source is approved if its hub is listed and its path is under an approved path."""
    return any(
        source["hub"] == entry["hub"] and any(source["path"].startswith(p) for p in entry["paths"])
        for entry in approved
    )


class Corpus:
    def __init__(self, records: dict[str, IngestedPassage]):
        self.records = records

    def get(self, passage_id: str) -> IngestedPassage | None:
        return self.records.get(passage_id)

    def searchable(self) -> list[IngestedPassage]:
        """Only approved, hash-verified passages may be retrieved."""
        return [r for r in self.records.values() if r.approved and r.hash_ok]

    def by_doc(self, doc_id: str) -> list[IngestedPassage]:
        return [r for r in self.records.values() if r.passage.doc_id == doc_id]


def ingest(raw_passages: list[dict], approved: list[dict]) -> Corpus:
    records: dict[str, IngestedPassage] = {}
    for raw in raw_passages:
        passage = Passage.model_validate(raw)
        computed = compute_hash(passage.text)
        records[passage.passage_id] = IngestedPassage(
            passage=passage,
            approved=is_approved(raw["source"], approved),
            # a missing manifest hash is a failure, not a pass
            hash_ok=passage.hash is not None and passage.hash == computed,
            computed_hash=computed,
        )
    return Corpus(records)


def load_corpus(data_dir: Path = DATA_DIR) -> Corpus:
    return ingest(load_raw_passages(data_dir), load_approved_sources(data_dir))
