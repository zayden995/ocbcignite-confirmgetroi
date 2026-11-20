# OCBC TREE

Hackathon prototype for the OCBC Ignite Innovation Challenge, Problem Statement 1: how can an employee judge whether an AI agent's answer is trustworthy?

The decision assessment API checks whether an AI answer covers the decisions an employee needs to make. It identifies those decisions from the question, applies synthetic policy to employee-supplied facts, and returns a verdict with evidence for each required decision.

The four original scenarios demonstrate claim-level verification. TREE checks each claim's sources and policy conditions, looks for conflicting evidence, then compares the result with a citation-only check.

> **Synthetic demo.** The decision assessment fixture and the four claim scenarios run offline. Typed chat uses Gemini when configured. All policy data and rates are synthetic.

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

## Try the decision verifier API

Start the backend, then run this from the repository root.

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v2/assess?mode=fixture' -ContentType 'application/json' -InFile 'backend/data/decision_fixture.json'
```

The fixture asks for the standard rate and checks one S$150,000 FAST transfer. The rate-only answer gives **Hold · 1/2** because it omits the transfer decision. The response cites **FD-301 v2**, which sets a **S$100,000** cap, and includes a suggested repair.

## Gemini mode (the default once a key is set)

Create `backend/.env` (git-ignored; never commit it) with a key from Google AI Studio and restart the
backend:

```
GEMINI_API_KEY=<your key>
# optional: TREE_GEMINI_MODEL=<model id>   (the default is set in backend/app/llm/provider.py)
# optional: TREE_LLM_PROVIDER=mock         (forces the scripted fixtures even with a key)
```

With a key, `POST /api/ask` generates a typed chat answer from the top two keyword matches. The chat verifies claims through `POST /api/verify-custom`. Call `POST /api/v2/assess?mode=live` directly for a live decision assessment.

The browser sends conversation history with each request. Gemini errors are shown in the app. The four original scenarios and **Run all 4 scenarios** continue using offline fixtures when a key is configured.

## Verify locally

Run each block from the repository root.

```powershell
cd frontend
npm run build
```

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

The backend suite includes the 15 public decision cases through `POST /api/v2/assess` and the original claim scenarios. Tests use offline fixtures or simulated provider responses.

## Deploy to Vercel

The repo is set up for [Vercel Services](https://vercel.com/docs/services) (Beta): one project, two
services. `vercel.json` builds `frontend/` (Vite) and `backend/` (FastAPI, `app.main:app`) and routes
`/api/*` to the backend and everything else to the frontend, so the app calls `/api` on its own domain
and needs no CORS or URL settings. The backend reads its synthetic data from `backend/data/`, which is
why that folder lives inside `backend/`. For Gemini mode on the deployed site, add `GEMINI_API_KEY`
(and optionally `TREE_GEMINI_MODEL`) under the Vercel project's Environment Variables and redeploy
(there is no `.env` file on Vercel).
The deployed site can run all four claim scenarios without a Gemini key. Typed chat requires the key.

To try the same routing locally: `npx vercel dev --local` (then open http://localhost:3000).

## Claim scenarios and admin tools

- **Employee** (`http://localhost:5173/`): opens like a new chat ("Good morning, how may I help you?").
  Open one of the four original starters, read the AI's answer, then press **Run TREE**. The result opens with one large verdict: the label (Verified,
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

## Demo assumptions

- **The original four scenarios.** `extract()` and `nli()` return scripted fixtures keyed to
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
