from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .corpus import Corpus
from .filters import passage_state
from .llm.base import LLM
from .models import Claim, Employee, NLIResult, Passage, PassageState


@dataclass
class RunContext:
    corpus: Corpus
    llm: LLM
    employee: Employee  # role, region and the merged case parameters
    today: date
    _nli_cache: dict[tuple[str, str], NLIResult] = field(default_factory=dict)

    def nli(self, claim: Claim, passage: Passage) -> NLIResult:
        """Memoised so a passage seen by several stages is only judged once."""
        key = (claim.id, passage.passage_id)
        if key not in self._nli_cache:
            self._nli_cache[key] = self.llm.nli(claim, passage)
        return self._nli_cache[key]

    def state_of(self, passage_id: str) -> PassageState | None:
        rec = self.corpus.get(passage_id)
        return passage_state(rec, self.employee, self.today) if rec else None
