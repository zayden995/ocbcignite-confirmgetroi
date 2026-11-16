from __future__ import annotations

import os
from typing import Literal
from pydantic import BaseModel

from ..corpus import load_corpus
from ..models import Claim, Extraction, NLIResult, Passage
from ..scenarios import load_slot_defs

class _ExtractedParams(BaseModel):
    deposit_amount: float | None = None
    tenor_months: int | None = None
    channel: str | None = None


class _GeminiExtraction(BaseModel):
    product: str | None = None
    params: _ExtractedParams
    conclusion: str
    claims: list[Claim]


class _PassageNLI(BaseModel):
    passage_id: str
    label: Literal["entails", "contradicts", "neutral"]
    score: float


class _BatchNLIResponse(BaseModel):
    results: list[_PassageNLI]


SYSTEM_EXTRACT = """You are the claim extraction engine for OCBC TREE.
Given the recent conversation history, the employee's current question, and the AI assistant's answer:
1. Extract case parameters into `params` when stated in the current turn OR carried over from recent conversation history:
   - `deposit_amount` (number, e.g. 20000)
   - `tenor_months` (integer, e.g. 12)
   - `channel` ("GIRO", "FAST", "CHEQUE", or "COUNTER")
2. Summarize the central recommendation in `conclusion` (1 short sentence).
3. Split the AI answer into 1 to 3 atomic verifiable `claims`:
   - `id`: "c1", "c2", etc.
   - `cited_passage_ids`: exact passage IDs cited or relied upon (from: FD-100#p1, FD-101#p1, FD-101#p2, FD-102#p1, FD-200#p1, FD-201#p1, FD-300#p1, FD-301#p1, FD-302#p1, FD-320#p1, FD-321#p1, FD-400#p1, FD-500#p1, FD-600#p1, FD-601#p1, FD-603#p1).
   - `required_slots`: list any of ["deposit_amount", "tenor_months", "channel"] that the claim assumes."""

SYSTEM_BATCH_NLI = """You are the Natural Language Inference (NLI) verifier for OCBC TREE.
Given a single `Claim` and a list of policy `Passages`, evaluate each passage against the claim:
- "entails": The passage directly supports or confirms the claim (score 0.88 to 0.98).
- "contradicts": The passage conflicts with, refutes, or states an exception/supersession that invalidates the claim (score 0.85 to 0.98).
- "neutral": Unrelated or insufficient evidence (score 0.0).
Only include passages in `results` that are "entails" or "contradicts" (omit "neutral" passages to save tokens)."""


class ProviderLLM:
    is_mock = False

    def __init__(self, provider: str) -> None:
        self.provider = provider.lower()
        self._nli_cache: dict[tuple[str, str], NLIResult] = {}
        self._chat_history: list[tuple[str, str]] = []
        if self.provider != "gemini":
            self._client = None
            return
        from google import genai
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self._model = os.environ.get("TREE_GEMINI_MODEL", "gemini-3.8-flash")

    def clear_history(self) -> None:
        self._chat_history.clear()

    def _not_implemented(self, what: str) -> NotImplementedError:
        return NotImplementedError(
            f"LLM provider '{self.provider}' is selected but {what}() is not implemented. "
            "Implement it in backend/app/llm/provider.py or unset TREE_LLM_PROVIDER to use the mock."
        )

    def _format_history(self) -> str:
        if not self._chat_history:
            return "None (start of conversation)."
        return "\n".join(
            f"Turn {i + 1} Employee: {q}\nTurn {i + 1} Assistant: {a}"
            for i, (q, a) in enumerate(self._chat_history[-4:])
        )

    def generate_answer(
        self, question: str, passages: list[Passage], role: str = "RM", region: str = "SG"
    ) -> str:
        if self._client is None:
            raise self._not_implemented("generate_answer")
        context = "\n".join(
            f"[{p.passage_id}] ({p.title}, status={p.status}, region={p.region}, roles={p.role_scope}): {p.text}"
            for p in passages
        )
        history_block = self._format_history()
        prompt = (
            f"You are an internal banking AI assistant helping an employee (Role: {role}, Region: {region}). "
            "Use the Prior Conversation History to resolve follow-up questions (such as 'what if they use FAST?' "
            "or 'what if the amount is $5,000?'). Answer in 1-2 concise sentences using only the policy passages "
            "that apply to the employee's question, and cite the passage IDs in brackets like [Sources: FD-101#p1].\n\n"
            f"Prior Conversation History:\n{history_block}\n\n"
            f"Policy Passages:\n{context}\n\n"
            f"Current Employee Question: {question}"
        )
        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config={"thinking_config": {"thinking_level": "low"}},
        )
        ans = resp.text.strip()
        self._chat_history.append((question, ans))
        return ans

    def extract(self, question: str, answer: str) -> Extraction:
        if self._client is None:
            raise self._not_implemented("extract")
        history_block = self._format_history()
        prompt = (
            f"Prior Conversation History:\n{history_block}\n\n"
            f"Current Question: {question}\nAI Answer: {answer}"
        )
        resp = self._client.models.generate_content(
            model=self._model,
            contents=f"{SYSTEM_EXTRACT}\n\n{prompt}",
            config={
                "response_mime_type": "application/json",
                "response_schema": _GeminiExtraction,
                "thinking_config": {"thinking_level": "low"},
            },
        )
        parsed = _GeminiExtraction.model_validate_json(resp.text)
        clean_params = {k: v for k, v in parsed.params.model_dump().items() if v is not None}

        combined_text = (" ".join(q for q, _ in self._chat_history[-2:]) + " " + question).upper()
        if "channel" not in clean_params:
            for ch in ("FAST", "GIRO", "CHEQUE", "COUNTER"):
                if ch in combined_text:
                    clean_params["channel"] = ch
                    break

        corpus_obj = load_corpus()
        valid_pids = sorted(corpus_obj.records.keys())
        slot_names = sorted(load_slot_defs().get("slots", {}).keys())
        dynamic_context = (
            f"Available corpus passage_ids: {', '.join(valid_pids)}\n"
            f"Available required_slots: {', '.join(slot_names)}\n"
        )
        prompt = (
            f"{dynamic_context}\n"
            f"Prior Conversation History:\n{history_block}\n\n"
            f"Current Question: {question}\nAI Answer: {answer}"
        )
        for claim in parsed.claims:
            expanded: list[str] = []
            for cid in claim.cited_passage_ids:
                if cid in valid_pids:
                    expanded.append(cid)
                else:
                    doc_prefix = cid.split("#")[0].strip()
                    expanded.extend(pid for pid in valid_pids if pid.startswith(doc_prefix + "#"))
            claim.cited_passage_ids = list(dict.fromkeys(expanded))

        return Extraction(
            entities={"product": parsed.product} if parsed.product else {},
            params=clean_params,
            conclusion=parsed.conclusion,
            claims=parsed.claims,
        )

    def nli(self, claim: Claim, passage: Passage) -> NLIResult:
        if self._client is None:
            raise self._not_implemented("nli")
        cache_key = (claim.text, passage.passage_id)
        if cache_key in self._nli_cache:
            return self._nli_cache[cache_key]

        all_passages = [rec.passage for rec in load_corpus().records.values()]
        passages_block = "\n".join(f"- {p.passage_id}: {p.text}" for p in all_passages)
        prompt = f"Claim: {claim.text}\n\nPassages:\n{passages_block}"

        resp = self._client.models.generate_content(
            model=self._model,
            contents=f"{SYSTEM_BATCH_NLI}\n\n{prompt}",
            config={
                "response_mime_type": "application/json",
                "response_schema": _BatchNLIResponse,
                "thinking_config": {"thinking_level": "low"},
            },
        )
        batch = _BatchNLIResponse.model_validate_json(resp.text)
        by_id = {item.passage_id: item for item in batch.results}

        for p in all_passages:
            hit = by_id.get(p.passage_id)
            if hit and hit.label in ("entails", "contradicts"):
                score = max(0.0, min(1.0, hit.score))
                self._nli_cache[(claim.text, p.passage_id)] = NLIResult(label=hit.label, score=score)
            else:
                self._nli_cache[(claim.text, p.passage_id)] = NLIResult(label="neutral", score=0.0)

        return self._nli_cache[cache_key]