from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config
from .challenge import COUNTER_TEMPLATES
from .corpus import load_approved_sources, load_corpus
from .errors import NoScriptedFixture, ScenarioNotFound
from .filters import passage_state
from .llm import get_llm
from .models import Employee
from .pipeline import MOCK_BADGE, run_tree
from .scenarios import get_scenario, load_scenarios, load_slot_defs
from .summary import run_summary
from .tree import STATE_LABELS
from .verify import SC_REFUTE, SC_VERIFY, SE_VERIFY

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
            {"id": s["id"], "title": s["title"], "employee": s["employee"], "question": s["question"]}
            for s in load_scenarios()
        ],
    }


@app.get("/api/summary")
def summary():
    """Runs every scenario through the real pipeline; labelled as a scripted demo set, not a benchmark."""
    return run_summary(corpus, get_llm())


@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    s = get_scenario(scenario_id)
    return {k: s[k] for k in ("id", "title", "question", "ai_answer", "employee", "citations")}


def _check_employee(role: str, region: str) -> None:
    defs = load_slot_defs()
    if role not in {r["code"] for r in defs["roles"]}:
        raise HTTPException(422, f"unknown role '{role}'")
    if region not in {r["code"] for r in defs["regions"]}:
        raise HTTPException(422, f"unknown region '{region}'")


@app.get("/api/admin/corpus")
def admin_corpus(role: str = "RM", region: str = "SG"):
    """Every ingested passage with its ingestion checks and its state for this employee (read-only)."""
    _check_employee(role, region)
    emp = Employee(role=role, region=region)
    return {
        "employee": emp,
        "approved_sources": load_approved_sources(),
        "passages": [
            {
                **rec.passage.model_dump(mode="json", exclude={"hash"}),
                "hash": rec.computed_hash,
                "hash_ok": rec.hash_ok,
                "approved": rec.approved,
                "state": passage_state(rec, emp, config.DEMO_DATE),
                "state_label": STATE_LABELS[passage_state(rec, emp, config.DEMO_DATE)],
            }
            for rec in corpus.records.values()
        ],
    }


@app.get("/api/admin/config")
def admin_config():
    llm = get_llm()
    return {
        "demo_date": config.DEMO_DATE.isoformat(),
        "data_label": config.DATA_LABEL,
        "llm_mode": "mock" if llm.is_mock else config.LLM_PROVIDER,
        "llm_badge": MOCK_BADGE if llm.is_mock else None,
        "thresholds": {"refute_sc": SC_REFUTE, "verify_se": SE_VERIFY, "verify_sc": SC_VERIFY},
        "counter_templates": COUNTER_TEMPLATES,
        "passage_count": len(corpus.records),
        "searchable_count": len(corpus.searchable()),
    }


@app.post("/api/verify")
def verify(req: VerifyRequest):
    _check_employee(req.role, req.region)
    return run_tree(get_scenario(req.scenario_id), req.role, req.region, req.params, llm=get_llm(), corpus=corpus)
