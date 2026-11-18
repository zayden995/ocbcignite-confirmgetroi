# OCBC TREE

Hackathon prototype for the OCBC Ignite Innovation Challenge, Problem Statement 1: how can an employee judge whether an AI agent's answer is trustworthy?

TREE does not stop at finding evidence that supports an AI answer. It also tries to **disprove** it, then shows the result as an interactive Proof Tree: **Investigate** (evidence, authenticity, applicability, slot coverage) -> **Challenge** (counter-queries for exceptions, conflicts, superseded or inapplicable policy, unsupported assumptions) -> **Verify** (a deterministic matrix). It is compared side by side with a citation-only baseline.

> **Two modes.** The four scripted demo scenarios always run on the **MOCK LLM (scripted outputs)**:
> their model calls return scripted fixtures (`backend/app/llm/fixtures.json`), so their verdicts are the
> designed ones, and the SE/SC scores are derived from those scripted outputs, so they are **not measured
> results**. Typed questions need Google Gemini and work only when a `GEMINI_API_KEY` is set (see
> "Gemini mode" below); without a key the header shows a MOCK badge. In both modes all data is
> **Synthetic - not real OCBC policy**.

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

### Gemini mode (the default once a key is set)

Create `backend/.env` (git-ignored; never commit it) with a key from Google AI Studio and restart the
backend:

```
GEMINI_API_KEY=<your key>
# optional: TREE_GEMINI_MODEL=<model id>   (the default is set in backend/app/llm/provider.py)
# optional: TREE_LLM_PROVIDER=mock         (forces the scripted fixtures even with a key)
```

A key switches typed questions to Gemini and the header's MOCK badge disappears. The four scripted
scenarios (`POST /api/verify`, and "Run all 4 scenarios" via `GET /api/summary`) stay on the scripted
fixtures even with a key, and their results keep the MOCK label. This is deliberate: on Gemini their
verdicts sometimes differed from the designed ones, each check took 36 to 157 seconds, and running them
used up the free-tier quota. `POST /api/ask` answers a
typed question the way a plain chatbot would (top-2 keyword retrieval, no governance filters), and
`POST /api/verify-custom` runs TREE on that answer. The server keeps no chat history: the browser sends
the earlier turns of the conversation with each request, so one visitor's questions never reach
another's. If a Gemini call fails (bad key, quota, outage) the app reports the reason; it does not
silently fall back to the mock. The corpus is still synthetic.

Without a key the app runs on the MOCK LLM, which only knows the four scripted questions. If Gemini
replies "503 UNAVAILABLE ... high demand", the chosen model is overloaded at Google; wait, or set
`TREE_GEMINI_MODEL` to another model (`gemini-3.6-flash` and `gemini-3.5-flash` have both worked). The tests
always use the mock or a faked network call (`backend/tests/conftest.py`), so they need no key and
ignore `backend/.env`.

## Deploy to Vercel

The repo is set up for [Vercel Services](https://vercel.com/docs/services) (Beta): one project, two
services. `vercel.json` builds `frontend/` (Vite) and `backend/` (FastAPI, `app.main:app`) and routes
`/api/*` to the backend and everything else to the frontend, so the app calls `/api` on its own domain
and needs no CORS or URL settings. The backend reads its synthetic data from `backend/data/`, which is
why that folder lives inside `backend/`. For Gemini mode on the deployed site, add `GEMINI_API_KEY`
(and optionally `TREE_GEMINI_MODEL`) under the Vercel project's Environment Variables and redeploy
(there is no `.env` file on Vercel).
Without it the deployed site runs on the MOCK LLM: the four scenarios work, and typed questions return
an error asking for the key.

To try the same routing locally: `npx vercel dev --local` (then open http://localhost:3000).

## Two views

- **Employee** (`http://localhost:5173/`): opens like a new chat ("Good morning, how may I help you?").
  Tap a starter or type one of the sample questions (in Gemini mode, any question), read the AI's
  answer, press **Run TREE**. The result opens with one large verdict: the label (Verified,
  Unresolved or Refuted), why in one sentence, and what to say or do instead. When several claims share
  the verdict (scenario 1 has two Refuted ones), it lists each reason and each correction, numbered to
  match. Claim-by-claim
  detail is folded away under it. Beside it is the **Proof Tree**: an illustrated tree where each branch
  is a claim and its colour is the claim's status (green Verified, amber Unresolved, red Refuted), the
  trunk is the AI's conclusion, and the roots are the source passages. Hover anything for status
  details; click a branch for the full breakdown.
- **Report missing input.** When a claim is Unresolved because the answer assumed details nobody gave
  (scenario 3: deposit amount and funding channel), the verdict shows a **Report missing input** button.
  It opens a small form with one field per missing input (number or dropdown, from `missing_inputs`);
  submitting re-runs TREE with those values, and the verdict notes what you reported, with a **Change**
  link to try other values.
- **Role and region** ("Asking as ... in ...") say who is asking. Policies are written for specific
  roles and regions, and TREE checks that an answer relies on ones that apply to *that* employee. Try
  scenario 4 as a Relationship Manager in Singapore (Verified), a Call Centre Agent (Unresolved: the
  bonus policy is not written for that role) and a Malaysia employee (Refuted: Malaysia has no bonus).
- **Admin** (`http://localhost:5173/#/admin`): a read-only backend inspector with a run summary, a
  per-claim pipeline trace (every passage considered, every counter-query and what it found, the
  matrix decision), the whole corpus with its approved-source and SHA-256 checks, the matrix and
  settings, the structured claim-to-passage graph (React Flow), and the raw JSON payload. There is
  no login; "Admin" is just a second page in this prototype.

The Proof Tree illustration is custom SVG (a photo cannot change branch colour). The slide image shown
before a run is `frontend/public/brand/ocbc-tree-slide.png`.

## The four scenarios

| # | Scenario | The AI cites | What TREE finds | Verdict |
|---|---|---|---|---|
| 1 | Overruled by another document (hero) | FD-101 (general rate rule), an unofficial wiki tip (FD-500) and FD-300 (expired, SGD 200k FAST limit) | FD-102 amends the rate rule: FAST-funded deposits are excluded. FD-301 supersedes FD-300 (SGD 100k, so SGD 150,000 needs more than one transfer). As a Malaysia employee, FD-302 says the FAST limits do not apply there | Refuted |
| 2 | Conflicting documents | FD-200 (1.0% early-withdrawal penalty) | FD-201, equal authority, says no principal penalty. A conflict is a flag, not SC | Unresolved |
| 3 | Unsupported assumption | FD-101 | The answer never asked for deposit amount or funding channel | Unresolved |
| 4 | Clean control | FD-320 (Priority bonus, RM/BM in Singapore) | Nothing challenges it for an RM in Singapore. The same answer is Unresolved for a Call Centre Agent and Refuted in Malaysia | Verified |

Each scenario is one short question and one short answer with one to four claims (branches). Scenario 1
has four (two green, two red: the missed exception and the out-of-date limit) and scenario 3 has four
(three green, one amber), so the tree shows a fuller canopy. Scenario 1 combines what used to be two
separate scenarios (overlooked exception, and outdated or inapplicable policy), because both show the
same idea: the cited document has been overruled by another one.

A citation-only check says **Verified** for all four, because every cited passage exists and says what the
answer says. Try the variants: scenario 1 with the region set to Malaysia; scenario 3 with
`deposit_amount` / `channel` supplied through the **Report missing input** form in the employee chat
(or `POST /api/verify` with `params`): 5000 + GIRO refutes it (below the minimum), 20000 + GIRO
verifies it (the FAST exception is not triggered), and 20000 + FAST refutes it.

The summary strip on the employee page ("Run all 4 scenarios", `GET /api/summary`) runs every scenario
through the real pipeline and compares the citation-only check with TREE against each scenario's expected
verdict (1 of 4 vs 4 of 4). It is labelled **Scripted demo set, not a benchmark**: the scenarios were
written to contain these failures and the model outputs are scripted, so it illustrates the pipeline
and is not a measured accuracy.

## Status

All build steps are done: four scenarios, the Malaysia variant of scenario 1, the role variants of
scenario 4, the "Report missing input" form, the summary strip and the admin inspector work end to end.
Not built on purpose: the reviewer queue, reliability dashboard and cross-answer blast radius (the admin
view inspects one run; it does not aggregate across runs).

## What is mocked (honest list)

- **The LLM for the four scenarios, always.** `extract()` and `nli()` return scripted fixtures keyed to
  the scenarios, and nothing is measured. Typed questions call Gemini when `GEMINI_API_KEY` is set
  (`backend/app/llm/provider.py`, see "Gemini mode" above). Setting `TREE_LLM_PROVIDER` to any name
  other than `mock` or `gemini` raises `NotImplementedError`.
- **Proposed corrections** for the scenarios are scripted text; for typed questions they are built from
  the policy passage that drove the verdict.
- **SE / SC scores** shown on branches come from the scripted model outputs for the scenarios, where
  they are not measured. For typed questions they are the scores Gemini returned.
- **The scenarios' AI answers** are scripted text.
- **The four scenarios** are a scripted demo set written to contain these failures. The summary strip
  (1 of 4 citation-only vs 4 of 4 TREE) is labelled "Scripted demo set, not a benchmark" and is not an
  accuracy figure.
- **The data** is synthetic: the policy corpus, the approved-source list and the rates are invented and
  are not real OCBC policy.
- **The date** is fixed (`DEMO_DATE`, 2026-10-28) so freshness checks give the same answer every run.
- **Employee identity** is two dropdowns (role, region); there is no SSO.
- **Corrective-action chips** are stubs.
- **Retrieval** is keyword overlap plus metadata filters, behind one function (`retrieval.retrieve`).
- **Hashes** are a SHA-256 manifest of the synthetic passage text, recomputed and compared at ingestion.

Everything else is real code running on those outputs: the approved-source whitelist, SHA-256
verification, freshness (`effective_date <= today < expiry_date`, with a fixed `DEMO_DATE`),
region/role applicability, structured-condition evaluation, slot coverage, the verification
matrix and Proof Tree serialisation.
