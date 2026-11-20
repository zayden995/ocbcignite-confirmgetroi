from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from google.genai.errors import APIError
from httpx import TransportError
from httpx2 import TransportError as SDKTransportError
from pydantic import ValidationError

from ..llm import get_llm
from ..llm.accounting import recording
from .contracts import Request, Result
from .engine import assess
from .intake import resolve_facts
from .mapping import AlignmentError
from .policy import POLICY

router = APIRouter()


@router.post("/api/v2/assess", response_model=Result)
def assess_revision(req: Request, response: Response, mode: Literal["fixture", "live"] = "fixture"):
    if req.bundle_id != POLICY.bundle_id:
        raise HTTPException(404, "Unknown policy bundle")
    try:
        facts, origins = resolve_facts(req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        provider = get_llm() if mode == "live" else None
    except ValueError as exc:
        raise HTTPException(503, "Check unavailable. Check the Gemini configuration.") from exc
    if provider and provider.is_mock:
        raise HTTPException(503, "Check unavailable. Configure Gemini to use the live text mapper.")
    try:
        with recording(req.turn_id, req.input_revision, "verification", response):
            return assess(req, POLICY, facts, provider, origins=origins)
    except (APIError, AlignmentError, ValidationError, NotImplementedError, OSError, TransportError, SDKTransportError) as exc:
        raise HTTPException(502, f"Check unavailable. {exc}", headers={"X-Tree-Attempts": response.headers["X-Tree-Attempts"]}) from exc
