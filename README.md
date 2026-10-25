# OCBC TREE

Hackathon prototype for the OCBC Ignite Innovation Challenge, Problem Statement 1: how can an employee judge whether an AI agent's answer is trustworthy?

TREE does not stop at finding evidence that supports an AI answer. It also tries to **disprove** it, then shows the result as an interactive Proof Tree: **Investigate** (evidence, authenticity, applicability, slot coverage) -> **Challenge** (counter-queries for exceptions, conflicts, superseded or inapplicable policy, unsupported assumptions) -> **Verify** (a deterministic matrix). It is compared side by side with a citation-only baseline.

> **MOCK LLM (scripted outputs).** By default every model call returns scripted fixtures
> (`backend/app/llm/fixtures.json`). The SE/SC scores in the UI are derived from those scripted
> outputs. They are **not measured results**. All data is **Synthetic - not real OCBC policy**.

## Run it

Needs Python 3.12 and Node 22+. From the repo root (Windows PowerShell):

```powershell
# backend (terminal 1)
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev          # open http://localhost:5173  (the dev server proxies /api to :8000)
```

Tests: `cd backend; .venv\Scripts\python.exe -m pytest -q`

## Status

Build step 5 of 8: the hero scenario (1. Overlooked exception) works end to end. Scenarios 2-5,
the all-scenarios summary strip and the "Report missing input" dialog are not built yet.

## What is mocked (honest list)

- **The LLM.** `extract()` and `nli()` return scripted fixtures keyed to the scenarios. Nothing is
  measured. `TREE_LLM_PROVIDER=<name>` selects an adapter stub (`backend/app/llm/provider.py`) that
  raises `NotImplementedError`; there is no silent fallback to mock.
- **Proposed corrections** in mock mode are scripted text.
- **Employee identity** is two dropdowns (role, region); there is no SSO.
- **Corrective-action chips** are stubs.
- **Retrieval** is keyword overlap plus metadata filters, behind one function (`retrieval.retrieve`).
- **Hashes** are a SHA-256 manifest of the synthetic passage text, recomputed and compared at ingestion.

Everything else is real code running on those outputs: the approved-source whitelist, SHA-256
verification, freshness (`effective_date <= today < expiry_date`, with a fixed `DEMO_DATE`),
region/role applicability, structured-condition evaluation, slot coverage, the verification
matrix and Proof Tree serialisation.
