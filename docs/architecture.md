# Application architecture

## A modular monolith, three application processes

FastAPI and the worker share one Python package and database model. Next.js serves
the browser and proxies `/api` to FastAPI. A separate worker keeps slow extraction
out of HTTP requests that start assessments. PostgreSQL provides both business
storage and a bounded durable job queue; no Redis/Kafka is needed at this scale.

## Documents, policy versions and snapshots

Uploads validate size/type/content, extract source locations, split into chunks,
and persist originals on a named volume. Scanned PDFs without usable text are
rejected rather than producing invented evidence. Content hashes deduplicate
within the authorized scope; each changed same-name document gets a new version.
A document's declaration/independent label is human metadata, not a model claim.

Policies contain reviewed natural-language requirements: concise titles, full
wording, applicability, severity and exact source citations. Gemini reads the complete
selected policy text within explicit size limits. Extracted drafts require reviewer
approval; revised source documents require a new extraction. Approved versions
cannot be edited. A run freezes its relationship context, approved requirements,
current document versions and exact chunks. Later edits affect new runs only.
That snapshot also makes historical citations resolvable after new uploads.

Document vectors use pinned `intfloat/multilingual-e5-small` (384 dimensions).
The API stores originals/chunks and pending index status without loading the model.
A persistent spawned worker child owns ONNX Runtime and the tokenizer, streams
verified public artifacts into a shared cache, and publishes each complete document
index atomically under a claim token. Reindex invalidates any older claim while
preserving source IDs, text and citations. Failed/crashed indexing is bounded and visible.

Exact pgvector cosine search restricts organization, case, document IDs AND chunk
IDs captured at enqueue time, plus the full configuration fingerprint. At most 500
evidence chunks participate. API input snapshots are immutable; the worker publishes
queries/config/scores once in a separate retrieval snapshot and reuses it on retry.
Database triggers reject changes to input snapshots or an already populated retrieval
snapshot. New documents and reindex requests cannot silently enter a queued run.

All new analyses use hybrid retrieval: weighted reciprocal rank fusion combines
semantic ranking and Unicode lexical retrieval. Evidence indexes must be ready.
The API accepts no retrieval selector and the runtime ranker implements only hybrid.
Historical variant labels remain stored as provenance; alternative rankings live in
offline evaluations. The frozen index fingerprint is unchanged by this interface cleanup.
See [model contract, evaluation and limits](retrieval.md).

## Analysis and trust

For every approved requirement, the worker retrieves up to eight counterparty
chunks using hybrid ranking and asks Gemini to assess them against the requirement
and relationship context. Embeddings select candidate evidence locally; they are
not sent as text to the model. Structured responses are validated against schemas
and eligible source quotations. Completed assessments persist individually for retry.
The report separates `pass/fail/unknown/conflict/not_applicable`, risk,
evidence completeness and the reviewer's decision. Versioned application code
aggregates statuses; the current workflow does not execute numeric requirement rules.
Historical rule evaluation remains isolated in offline regression utilities.

Conflicts require matching fact, scope and period. EU hosting and a US subprocessor
produce a question rather than automatic noncompliance. Source resolution checks
that the exact quote exists; it does not prove a model interpreted the quote
correctly. Humans review requirements and findings. Untrusted document instructions
cannot modify roles, tool permissions, risk rules or human decisions.

The optional Gemini REST adapter uses structured output, input/output bounds,
timeouts and limited transient retries. HTTP429 stops; there is no paid fallback.
The default semantic demo returns conservative unknown assessments. Separate evaluation
results must not be confused with real-model validation.

## Durable work and human review

A job row records state, attempts, lease and input versions. Workers use a
per-run PostgreSQL session advisory lock and a row lock when claiming. Lease
expiration allows recovery after a dead process; the advisory lock prevents another
worker claiming a live execution. The lock and checkpoint saver share one physical
connection, so loss of ownership also stops checkpoint writes. A claim token fences final business writes if
an old worker loses its connection. A supervisor terminates a job that exceeds its
active runtime budget. The persistent child reuses its loaded model across commands;
model preparation has a separate 600-second budget, ordinary work retains 120 seconds.
A failed preparation does not consume analysis attempts or block review finalization.
New analyses with evidence require compatible ready indexes.

LangGraph saves checkpoints in PostgreSQL using the run UUID as thread ID. Its
review node interrupts after the report. A human Decision is an immutable business
record, then the worker resumes the saved graph. If final graph bookkeeping fails,
the recorded human decision survives and the report exposes a workflow error.
Checkpoints belong to the workflow library; explicit Alembic revisions own the
business schema and are applied before processes start.

## Information requests

A report stores one plain-text information-request draft. An analyst can submit it;
a reviewer can edit it and record the final text with a needs-information decision.
Users can copy the text for manual delivery; there is no outbound integration.
A needs-information review permits new evidence and another analysis while keeping
the reviewed report unchanged. Accepted and rejected decisions close analyst editing.

## Access boundaries

Opaque HttpOnly session cookies correspond to hashed tokens in the database.
Passwords use salted PBKDF2. Mutations check request origin; object access is
restricted by session organization and role; analysts share organization cases. The browser cannot
choose a trusted organization or actor. Policy changes and final decisions require a reviewer. Runtime
tracing to external providers is disabled; secrets and private model reasoning
are not stored in logs. Audit history is append-only through application APIs.

These controls support a local demo and tested isolation. They are not a complete
enterprise identity, distributed quota or production operations platform.

## Where to find the code

- `backend/src/counterparty/api/`: HTTP endpoints grouped by auth, cases,
  documents, policies, analyses and audit. `routes.py` only assembles routers.
- `documents.py`, `indexing.py`, `embeddings.py`: ingestion and local retrieval indexes.
- `analysis/semantic.py`, `analysis/adapters.py`, `analysis/schemas.py`:
  current assessment flow, provider prompts and response validation.
- `worker.py`: background execution and the durable LangGraph review flow.
- `models.py` and `migrations/`: persistence and versioned database upgrades.
- `frontend/app/`: pages; `frontend/components/`: shared UI.

The running FastAPI `/docs` page is the endpoint contract generated from code.
Keeping a second handwritten endpoint/schema inventory would duplicate it and drift.
