# AI Counterparty & Compliance Analyst

Assess technology counterparties against your organization's reviewed security and
privacy policies. Upload documents, approve structured requirements, run an
assessment, inspect cited evidence and record a human decision. Follow-up tickets
require their own explicit approval.

The local MVP includes an English Next.js interface, FastAPI, PostgreSQL/pgvector,
a durable LangGraph worker and a local REST ticket simulator. New analyses use
**semantic-v2**: each reviewed requirement is assessed against retrieved evidence
and relationship context. Gemini performs interpretation when explicitly configured.
A pinned multilingual E5 model prepares embeddings locally on CPU.

**The default demo calls no LLM and conservatively returns unknown assessments.**
Its policy proposals are source-review placeholders, not extracted obligations.
No API key is needed to explore the workflow. Demo results and mocked tests do not
establish real-model quality. All bundled organizations and documents are synthetic.

## Start

Install Docker with Compose v2, then run from this directory:

```bash
cp -n .env.example .env
docker compose up --build -d --wait
docker compose run --rm -e MODEL_MODE=demo seed
```

Open [the application](http://localhost:3000) or [API docs](http://localhost:8000/docs).
Select a demo account on the login screen. All seeded passwords are
`Demo-only-2026!`:

| Account | Access |
|---|---|
| `analyst@northstar.demo` | Own cases, documents, policy drafts and analyses |
| `reviewer@northstar.demo` | Organization cases, policy approval, decisions and ticket approval |
| `auditor@northstar.demo` | Organization read-only access |
| `admin@northstar.demo` | Local administrator role |
| `analyst@other.demo` | Separate organization for isolation demonstrations |

`seed` is explicit and repeatable. It creates five role accounts, four substantial policy documents and one approved
Northstar Labs Third-Party Assurance Standard with 20 curated controls. It creates
no cases, evidence uploads, reports, tickets or old demo history. One audit event
records the new synthetic policy seed and its provenance. The seeded
approval is a synthetic fixture state, not an independent human review. It does not invoke a model or auto-approve a real external action.
Use the reviewer account for the complete demo journey. Demo credentials and the
shared ticket token are for local synthetic use only. `DEMO_MODE=false` disables
seeded account login; this is not a production identity-management system.

The frontend and API bind to loopback; the database and ticket simulator stay on
the Docker network. `FRONTEND_PORT`/`API_PORT` can change exposed ports; also adjust
`ALLOWED_ORIGINS` for a nondefault frontend origin. First build requires network
access to public image/package registries. On first indexing, the worker also
automatically downloads 487 MB of pinned public model artifacts (no account/key)
into the persistent `model-cache` volume. A verified cache supports offline reuse;
subsequent demo operation uses local services. Database passwords are passed separately from the URL. In
`.env`, single-quote values containing `$` to avoid Compose interpolation.

## Walk through the application

1. Open **Policies** and inspect the approved synthetic policy set. Upload a text
   PDF, Markdown or TXT and open its **Full document** view. Source excerpts and
   technical indexing controls are secondary details; the original remains downloadable.
2. Click **Extract requirements**, or select documents through **New policy set**.
   Extraction reads the complete selected policy text within the limits below and
   saves its result. Opening that version or repeating the same extraction reuses
   the saved result. **Regenerate requirements** explicitly confirms new model API
   calls and creates a new draft; viewing a document never triggers extraction.
3. Review each requirement's description, applicability, severity and exact source
   quotation, then approve the version. Requirements cannot be edited or cloned.
   Regenerate an incorrect extraction, or upload revised source documents and
   extract a new set when the policy changes. The worker prepares and caches embeddings
   for the approved requirements in the background.
4. Open **Cases**, create a relationship context, and upload counterparty evidence.
   Label each source as a declaration or independent support. Run an analysis
   against an approved policy once its requirements and evidence are ready.
   Hybrid retrieval is the default; comparison options sit under advanced settings.
5. Watch progress as the worker assesses requirements sequentially. A failed run
   exposes **Resume unfinished requirements**. Saved completed assessments are
   reused; unfinished work may make additional API calls. Partial results are not
   presented as a final report.
6. Inspect risk, evidence completeness and finding status separately. Each finding
   places the policy requirement and its source next to the counterparty evidence,
   with an explanation. Open citations to inspect exact excerpts and the full source.
   Missing evidence does not prove compliance. A possible discrepancy is not
   automatically a contradiction.
7. Record acceptance, rejection or a request for information with a rationale.
   The worker resumes its saved workflow after that human decision.
8. Propose a follow-up ticket, inspect its exact title/body, approve, then execute.
   Read its status in the local ticket service. A lost response can be reconciled
   without creating another ticket. Review the activity history.

For a synthetic example, upload
`datasets/synthetic/evidence/atlas-assurance-pack.md` as a **Counterparty declaration**
in a high-criticality case with personal data and privileged access. The pack is
not the independent report it describes. Inspect the support-portal assurance
exclusion and US support-access boundary. No fixed completeness percentage or
finding count is promised for a real-model assessment. Demo mode conservatively
leaves interpretation unresolved.

Historical tiny scenarios remain under `datasets/synthetic/regression` for tests
and are never seeded. Older approved policy versions and reports remain readable;
new assessments use the semantic workflow. An English interface does not imply
universal policy understanding.

## Architecture and data flow

```mermaid
flowchart LR
    Browser[Browser / Next.js] --> API[FastAPI: identity and permissions]
    API --> DB[(PostgreSQL + pgvector)]
    API --> Files[Persistent document volume]
    Worker[Worker / LangGraph] <--> DB
    Worker --> Adapter[Demo or optional Gemini adapter]
    API -->|Separately approved REST write| Tickets[Local ticket simulator]
    Tickets --> DB
```

The API captures immutable input versions before queuing a run. The worker retrieves
scoped evidence using pgvector and the approved requirement embeddings. Saved
retrieval provenance retains queries, scores, eligible chunks and model configuration.
For each requirement, the configured model interprets applicability and evidence,
returning a validated status, explanation and source quotations. The application
checks quotation grounding and aggregates risk and completeness using versioned
code. A matching quotation proves source resolution, not semantic entailment.

Each completed requirement assessment is persisted before the next begins. Explicit
retry resumes unfinished work without repeating saved completed assessments, including
completed paid model calls. A provider call interrupted before its result is saved
may still be repeated. The finished report pauses at a durable human-review checkpoint.
Neither a document nor a model grants permissions or authorizes a write.

The [original architecture](docs/architecture/mvp.md),
[original API contract](docs/architecture/mvp-contract.md),
[MVP verification](docs/verification/mvp.md),
[evaluation methodology/results](evaluations/README.md) and
[Northstar corpus acceptance](docs/verification/northstar.md) describe earlier
implementations and historical regression evidence. Their deterministic-rule scores
do not validate semantic-v2. The [local retrieval measurements](docs/verification/embeddings.md)
cover embedding/retrieval behavior, not correctness of requirement interpretation.

## Verification

Backend tests run against disposable PostgreSQL databases, independent of the app:

```bash
docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f compose.test.yaml run --rm --no-deps tests ruff check .
docker compose -f compose.test.yaml run --rm --no-deps tests ruff format --check .
docker compose -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" \
  tests python /evaluations/run.py --check
docker compose -f compose.test.yaml down
```

Frontend checks require Node 24 and Chrome (or `npx playwright install chrome`):

```bash
cd frontend
npm ci
npm run build
npm run typecheck
npm run test:e2e
E2E_REAL_API=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 npm run test:e2e
```

`scripts/verify_demo.py` is a historical deterministic-engine regression helper;
its fixed 6-pass/14-unknown assertions do not validate the new semantic workflow.
The evaluation command above also exercises the historical regression pipeline.
Use current backend/browser checks for workflow behavior and a separately reviewed
semantic-v2 corpus for model quality; passing mocks are not a model-quality result.

The final browser command needs the running, seeded Compose stack and writes synthetic
cases to it. Browser boundary tests use mocked HTTP; the real-stack test uses the
actual API, database, worker and ticket service. CI runs both without model keys. When the stack uses Gemini, the real-stack
journey invokes the configured provider for the entire selected policy set.

## Optional real model

Leave `MODEL_MODE=demo` to run without external credentials. To evaluate Gemini,
provide **`GEMINI_API_KEY` and an explicitly selected `GEMINI_MODEL`** in your local
`.env`. Verify the model's availability, account quotas and data terms first.
No billing activation or paid fallback is configured. Never commit the key.

The first live integration used `gemini-3.5-flash-lite`. On 2026-09-14 Google
rejected `gemini-2.5-flash-lite` for a new account despite listing it in Models.
The [historical live verification report](docs/verification/gemini.md) records
compatibility fixes and earlier extraction/rule-pipeline regression measurements;
it does not validate the new semantic-v2 assessment workflow. Availability
still depends on the account; there is no automatic model substitution.

The earlier extraction/rule pipeline has this explicit real-model regression command
(which makes provider calls); it is not a semantic-v2 quality evaluation:

```bash
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$PWD/evaluations:/evaluations" api python /evaluations/run.py --mode gemini
```

Missing credentials produce a `pending_credentials` report and exit code 2. This
is an explicit incomplete quality check, not a passing model evaluation. For semantic assessment, obtain a separately reviewed evaluation before relying on
its findings. Set `MODEL_MODE=gemini` and recreate API/worker via `docker compose up -d`.
Keep `DEMO_MODE=true` for local demo accounts. Configured-provider failures are
reported; they never silently switch to demo responses. Requests are bounded;
pricing is unknown (`null`) until checked externally.

## Removing saved data

Use **Delete report**, **Delete case**, **Delete policy set** or the document's
**Delete** action. A case deletion includes its reports and evidence documents;
a report deletion includes its decision and saved analysis progress. Delete
referencing reports before a policy set, and referencing policy sets before their
source documents. Local ticket records can also be deleted; this does not remove
a ticket already sent to another service. Deletion applies to active application
storage, not existing backups or model-provider records.

Source links open the full original text and highlight the exact cited passage.
Mechanical search chunks are not shown as excerpts. If the passage cannot be
located unambiguously, the document view says so instead of highlighting a guess.

## Operations and limitations

```bash
docker compose logs api worker tickets migrate
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose down
```

`down` preserves database, document and model-cache volumes. See
[backup, restore and retention](docs/architecture/operations.md) before deleting
volumes. The migrations build/update database structure; they do not analyze files.

Policy extraction accepts at most 100,000 source characters across selected documents,
with a 125,000-character model payload limit and 16,384 maximum output tokens.
Each requirement assessment has a 25,000-character input limit and 4,096 maximum
output tokens. Runs accept at most 100 requirements and 500 evidence chunks, with
at most three attempts per requirement. Oversized inputs fail explicitly rather
than silently dropping policy text. Full-document extraction does not guarantee
that the model identifies every obligation or correctly interprets exceptions.

This is a local portfolio MVP, not legal certification or production assurance.
OCR, real business integrations, public hosting, enterprise administration,
PDF report export and MCP are outside this release.
Scanned PDFs receive an unsupported-input error. The app database account owns
its schema; public deployment needs separate restricted credentials, managed
identity, TLS, shared quota controls and operational review.

## Repository

- `backend/src/counterparty/`: API/domain, ingestion, adapters, semantic assessment and risk aggregation,
  worker, ticket integration and packaged database migrations.
- `frontend/`: Next.js UI and browser tests.
- `datasets/synthetic/`: four substantial policies, an Atlas assurance pack and historical regression fixtures.
- `evaluations/`: frozen synthetic retrieval corpus and explicitly labelled demo/provider regression reports.
- `docs/`: architecture, contract and verification evidence.
- `.github/workflows/ci.yml`: reproducible checks without paid model calls.
