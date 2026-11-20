from __future__ import annotations

import os
from typing import Literal
from pydantic import BaseModel

from .accounting import generate
from ..corpus import load_corpus
from ..models import Claim, Extraction, NLIResult, Passage

#: Earlier turns of one conversation as (question, answer) pairs, oldest first. Sent by the client with each request.
History = list[tuple[str, str]]


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
        # One instance serves every request, so it must hold nothing that belongs to a single
        # conversation. Chat history arrives with each request instead (see History).
        self._nli_cache: dict[tuple[str, str], NLIResult] = {}
        if self.provider != "gemini":
            self._client = None
            return
        from google import genai
        self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self._model = os.environ.get("TREE_GEMINI_MODEL", "gemini-3.8-flash")

    def _not_implemented(self, what: str) -> NotImplementedError:
        return NotImplementedError(
            f"LLM provider '{self.provider}' is selected but {what}() is not implemented. "
            "Implement it in backend/app/llm/provider.py or unset TREE_LLM_PROVIDER to use the mock."
        )

    @staticmethod
    def _format_history(history: History | None) -> str:
        if not history:
            return "None (start of conversation)."
        return "\n".join(
            f"Turn {i + 1} Employee: {q}\nTurn {i + 1} Assistant: {a}"
            for i, (q, a) in enumerate(history[-4:])
        )

    def generate_answer(
        self,
        question: str,
        passages: list[Passage],
        role: str = "RM",
        region: str = "SG",
        history: History | None = None,
    ) -> str:
        if self._client is None:
            raise self._not_implemented("generate_answer")
        context = "\n".join(
            f"[{p.passage_id}] ({p.title}, status={p.status}, region={p.region}, roles={p.role_scope}): {p.text}"
            for p in passages
        )
        history_block = self._format_history(history)
        prompt = (
            f"You are an internal banking AI assistant helping an employee (Role: {role}, Region: {region}). "
            "Use the Prior Conversation History to resolve follow-up questions (such as 'what if they use FAST?' "
            "or 'what if the amount is $5,000?'). Answer in 1-2 concise sentences using only the policy passages "
            "that apply to the employee's question, and cite the passage IDs in brackets like [Sources: FD-101#p1].\n\n"
            f"Prior Conversation History:\n{history_block}\n\n"
            f"Policy Passages:\n{context}\n\n"
            f"Current Employee Question: {question}"
        )
        resp = generate(self._client,
            model=self._model,
            contents=prompt,
            config={"thinking_config": {"thinking_level": "low"}},
        )
        return resp.text.strip()

    def structured(self, prompt: str, schema: type[BaseModel]):
        if self._client is None:
            raise self._not_implemented("structured")
        response = generate(self._client, model=self._model, contents=prompt, config={
            "response_mime_type": "application/json", "response_schema": schema,
            "thinking_config": {"thinking_level": "low"},
        })
        return schema.model_validate_json(response.text)

    def extract(self, question: str, answer: str, history: History | None = None) -> Extraction:
        if self._client is None:
            raise self._not_implemented("extract")
        history_block = self._format_history(history)
        prompt = (
            f"Prior Conversation History:\n{history_block}\n\n"
            f"Current Question: {question}\nAI Answer: {answer}"
        )
        parsed = self.structured(f"{SYSTEM_EXTRACT}\n\n{prompt}", _GeminiExtraction)
        clean_params = {k: v for k, v in parsed.params.model_dump().items() if v is not None}

        # the previous turn's question plus this one, so "what if they use FAST?" still carries over
        combined_text = (" ".join(q for q, _ in (history or [])[-1:]) + " " + question).upper()
        if "channel" not in clean_params:
            for ch in ("FAST", "GIRO", "CHEQUE", "COUNTER"):
                if ch in combined_text:
                    clean_params["channel"] = ch
                    break

        corpus_obj = load_corpus()
        valid_pids = sorted(corpus_obj.records.keys())
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
        labels = self.label_evidence(claim, all_passages)
        self._nli_cache.update(((claim.text, pid), label) for pid, label in labels.items())
        return self._nli_cache[cache_key]

    def label_evidence(self, claim: Claim, passages: list[Passage]) -> dict[str, NLIResult]:
        passages_block = "\n".join(f"- {p.passage_id}: {p.text}" for p in passages)
        prompt = f"{SYSTEM_BATCH_NLI}\n\nClaim: {claim.text}\n\nPassages:\n{passages_block}"
        batch = self.structured(prompt, _BatchNLIResponse)
        labels = {p.passage_id: NLIResult(label="neutral", score=0.0) for p in passages}
        for hit in batch.results:
            if hit.passage_id in labels and hit.label in ("entails", "contradicts"):
                labels[hit.passage_id] = NLIResult(label=hit.label, score=max(0, min(1, hit.score)))
        return labels
