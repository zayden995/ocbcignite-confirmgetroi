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

Tests: `cd backend; .venv\Scripts\python.exe -m pip install -r requirements-dev.txt; .venv\Scripts\python.exe -m pytest -q`
(`requirements.txt` is what the deployed app needs; `requirements-dev.txt` adds the test packages.)

## Deploy to Vercel

The repo is set up for [Vercel Services](https://vercel.com/docs/services) (Beta): one project, two
services. `vercel.json` builds `frontend/` (Vite) and `backend/` (FastAPI, `app.main:app`) and routes
`/api/*` to the backend and everything else to the frontend, so the app calls `/api` on its own domain
and needs no CORS or URL settings. The backend reads its synthetic data from `backend/data/`, which is
why that folder lives inside `backend/`. It runs in MOCK mode by default; do not set
`TREE_LLM_PROVIDER` unless a real adapter has been implemented.

To try the same routing locally: `npx vercel dev --local` (then open http://localhost:3000).

## Two views

- **Employee** (`http://localhost:5173/`): opens like a new chat ("Good morning, how may I help you?").
  Type one of the sample questions (this demo only knows those) or tap a starter, read the AI's
  answer, press **Run TREE**. The result opens with one large verdict: the label (Verified,
  Unresolved or Refuted), why in one sentence, and what to say or do instead. Claim-by-claim
  detail is folded away under it. Beside it is the **Proof Tree**: an illustrated tree where each branch
  is a claim and its colour is the claim's status (green Verified, amber Unresolved, red Refuted), the
  trunk is the AI's conclusion, and the roots are the source passages. Hover anything for status
  details; click a branch for the full breakdown.
- **Role and region** ("Asking as ... in ...") say who is asking. Policies are written for specific
  roles and regions, and TREE checks that an answer relies on ones that apply to *that* employee. Try
  scenario 5 as a Relationship Manager in Singapore (Verified), a Call Centre Agent (Unresolved: the
  bonus policy is not written for that role) and a Malaysia employee (Refuted: Malaysia has no bonus).
- **Admin** (`http://localhost:5173/#/admin`): a read-only backend inspector with a run summary, a
  per-claim pipeline trace (every passage considered, every counter-query and what it found, the
  matrix decision), the whole corpus with its approved-source and SHA-256 checks, the matrix and
  settings, the structured claim-to-passage graph (React Flow), and the raw JSON payload. There is
  no login; "Admin" is just a second page in this prototype.

The Proof Tree illustration is custom SVG (a photo cannot change branch colour). The slide image shown
before a run is `frontend/public/brand/ocbc-tree-slide.png`.

## The five scenarios

| # | Scenario | The AI cites | What TREE finds | Verdict |
|---|---|---|---|---|
| 1 | Overlooked exception (hero) | FD-101 (general rate rule) | FD-102 amends it: FAST-funded deposits are excluded | Refuted |
| 2 | Conflicting documents | FD-200 (1.0% early-withdrawal penalty) | FD-201, equal authority, says no principal penalty. A conflict is a flag, not SC | Unresolved |
| 3 | Outdated or inapplicable | FD-300 (expired, SGD 200k FAST limit) | FD-301 supersedes it (SGD 100k). As a Malaysia employee, FD-302 says the FAST limits do not apply there | Refuted |
| 4 | Unsupported assumption | FD-101 | The answer never asked for deposit amount or funding channel | Unresolved |
| 5 | Clean control | FD-320 (Priority bonus, RM/BM in Singapore) | Nothing challenges it for an RM in Singapore. The same answer is Unresolved for a Call Centre Agent and Refuted in Malaysia | Verified |

Each scenario is one short question and one short answer. Most have one or two claims (branches);
scenario 1 has three (two green, one red) and scenario 4 has four (three green, one amber) so the tree
shows a fuller canopy.

A citation-only check says **Verified** for all five, because every cited passage exists and says what the
answer says. Try the variants: scenario 3 with the region set to Malaysia; scenario 4 with
`deposit_amount` / `channel` supplied through `POST /api/verify` (`params`), for example 5000 + GIRO
refutes it (below the minimum), 20000 + GIRO verifies it (the FAST exception is not triggered), and
20000 + FAST refutes it. The employee UI has no input form for this yet.

The summary strip on the employee page ("Run all 5 scenarios", `GET /api/summary`) runs every scenario
through the real pipeline and compares the citation-only check with TREE against each scenario's expected
verdict (1 of 5 vs 5 of 5). It is labelled **Scripted demo set, not a benchmark**: the scenarios were
written to contain these failures and the model outputs are scripted, so it illustrates the pipeline
and is not a measured accuracy.

## Status

Build step 6 (plus the two-view UI revamp): all five scenarios, the Malaysia variant of scenario 3, and
the summary strip work end to end. Still to do: the "Report missing input" dialog in the employee UI
(the backend already re-runs with supplied inputs), and the final README pass. Not built on purpose:
the reviewer queue, reliability dashboard and cross-answer blast radius (the admin view inspects one
run; it does not aggregate across runs).

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
