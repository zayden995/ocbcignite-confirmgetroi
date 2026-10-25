from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config
from .corpus import load_corpus
from .errors import NoScriptedFixture, ScenarioNotFound
from .llm import get_llm
from .pipeline import MOCK_BADGE, run_tree
from .scenarios import get_scenario, load_scenarios, load_slot_defs

app = FastAPI(title="OCBC TREE (prototype, synthetic data)")
corpus = load_corpus()


class VerifyRequest(BaseModel):
    scenario_id: str
    role: str
    region: str
    params: dict[str, Any] = Field(default_factory=dict)  # employee-supplied missing inputs


@app.exception_handler(NotImplementedError)
async def _provider_not_implemented(_, exc: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(ScenarioNotFound)
async def _scenario_not_found(_, exc: ScenarioNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NoScriptedFixture)
async def _no_fixture(_, exc: NoScriptedFixture):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/meta")
def meta():
    defs = load_slot_defs()
    llm = get_llm()
    return {
        "demo_date": config.DEMO_DATE.isoformat(),
        "data_label": config.DATA_LABEL,
        "llm_mode": "mock" if llm.is_mock else config.LLM_PROVIDER,
        "llm_badge": MOCK_BADGE if llm.is_mock else None,
        "roles": defs["roles"],
        "regions": defs["regions"],
        "scenarios": [
            {"id": s["id"], "title": s["title"], "employee": s["employee"]} for s in load_scenarios()
        ],
    }


@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    s = get_scenario(scenario_id)
    return {k: s[k] for k in ("id", "title", "question", "ai_answer", "employee", "citations")}


@app.post("/api/verify")
def verify(req: VerifyRequest):
    defs = load_slot_defs()
    if req.role not in {r["code"] for r in defs["roles"]}:
        raise HTTPException(422, f"unknown role '{req.role}'")
    if req.region not in {r["code"] for r in defs["regions"]}:
        raise HTTPException(422, f"unknown region '{req.region}'")
    return run_tree(get_scenario(req.scenario_id), req.role, req.region, req.params, llm=get_llm(), corpus=corpus)
