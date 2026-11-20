"""Per-request receipts travel with success and error responses. Nothing is stored across visitors."""
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from ..config import DATA_DIR

PRICE_TABLE = json.loads(Path(os.getenv("TREE_MODEL_PRICES", DATA_DIR / "model_prices.json")).read_text(encoding="utf-8"))
_current = ContextVar("provider_receipt", default=None)


def billing_categories(metadata):
    if metadata is None:
        return None
    data = metadata if isinstance(metadata, dict) else metadata.model_dump(exclude_none=True)
    # This application submits only text. Cached tokens are already included in prompt_token_count.
    def count(key, camel):
        return data.get(key, data.get(camel))

    prompt = count("prompt_token_count", "promptTokenCount")
    output = count("candidates_token_count", "candidatesTokenCount")
    cached = count("cached_content_token_count", "cachedContentTokenCount") or 0
    thinking = count("thoughts_token_count", "thoughtsTokenCount") or 0
    categories = {"input": prompt - cached if prompt is not None else None, "cached": cached,
            "output": output, "thinking": thinking}
    tool_tokens = count("tool_use_prompt_token_count", "toolUsePromptTokenCount")
    if tool_tokens:
        categories["tool_input"] = tool_tokens
    return categories


def estimate(model, usage, when, prices):
    rate = next((r for r in prices["models"].get(model, [])
                 if r["from"] <= when < r.get("until", "9999-12-31")), None)
    if rate is None or not usage or any(v is None or v < 0 or (v and k not in rate) for k, v in usage.items()):
        return None
    return str(sum(Decimal(str(rate[k])) * v for k, v in usage.items() if v) / prices["tokens_per_unit"])


@contextmanager
def recording(turn_id, revision, purpose, response):
    attempts = []
    token = _current.set((turn_id, revision, purpose, attempts))
    try:
        yield
    finally:
        _current.reset(token)
        response.headers["X-Tree-Attempts"] = json.dumps(attempts, separators=(",", ":"))


def generate(client, *, model, contents, config):
    context = _current.get()
    if context is None:
        return client.models.generate_content(model=model, contents=contents, config=config)
    # One SDK invocation is exactly one attempt. Employee retries receive fresh receipts.
    config = {**config, "http_options": {"retry_options": {"attempts": 1}}}
    turn_id, revision, purpose, attempts = context
    start = perf_counter()
    when = datetime.now(timezone.utc).date().isoformat()
    usage, succeeded = None, False
    try:
        result = client.models.generate_content(model=model, contents=contents, config=config)
        usage = billing_categories(getattr(result, "usage_metadata", None))
        succeeded = True
        return result
    except Exception as exc:
        body = getattr(exc, "details", {}) or {}
        details = body.get("error", {}) if isinstance(body, dict) else {}
        metadata = getattr(exc, "usage_metadata", None) or details.get("usageMetadata")
        if metadata is None and isinstance(body, dict):
            metadata = body.get("usageMetadata")
        usage = billing_categories(metadata)
        raise
    finally:
        attempts.append({
            "id": uuid4().hex, "turn_id": turn_id, "revision": revision, "purpose": purpose,
            "model": model, "usage": usage, "elapsed_ms": round((perf_counter() - start) * 1000),
            "success": succeeded, "estimate": estimate(model, usage, when, PRICE_TABLE),
            "currency": PRICE_TABLE["currency"], "pricing_date": PRICE_TABLE["pricing_date"],
        })
