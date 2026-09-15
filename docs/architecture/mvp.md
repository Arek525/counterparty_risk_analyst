# MVP architecture

## A modular monolith, three application processes

FastAPI and the worker share one Python package and database model. Next.js serves
the browser and proxies `/api` to FastAPI. A separate worker keeps slow extraction
out of HTTP requests that start assessments. PostgreSQL provides both business
storage and a bounded durable job queue; no Redis/Kafka is needed at this scale.
The ticket simulator is a separate REST process so failures and write contracts
can be exercised without connecting a real business system.

## Documents, policy versions and snapshots

Uploads validate size/type/content, extract source locations, split into chunks,
and persist originals on a named volume. Scanned PDFs without usable text are
rejected rather than producing invented evidence. Content hashes deduplicate
within the authorized scope; each changed same-name document gets a new version.
A document's declaration/independent label is human metadata, not a model claim.

Policies contain reviewed structured requirements: applicability conditions,
expectations, allowed operators, severity and source citations. Approved versions
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

Semantic ranking is the default for new analyses; weighted reciprocal rank fusion
is an explicit hybrid option and Unicode lexical retrieval remains available without
the model. Historical hash-based reports and offline regressions remain historical.
See [model contract, evaluation and limits](../verification/embeddings.md).

## Analysis and trust

The adapter proposes requirements or extracts facts; application code validates
schemas and source quotes. Supported comparisons use an allowlist, never generated
Python. The report separates `pass/fail/unknown/conflict/not_applicable`, risk,
evidence completeness and the reviewer's decision. Explicit versioned aggregation
rules preserve a confirmed High risk when other evidence is absent.

Conflicts require matching fact, scope and period. EU hosting and a US subprocessor
produce a question rather than automatic noncompliance. Source resolution checks
that the exact quote exists; it does not prove a model interpreted the quote
correctly. Humans review requirements and findings. Untrusted document instructions
cannot modify roles, tool permissions, risk rules or ticket approvals.

The optional Gemini REST adapter uses structured output, input/output bounds,
timeouts and limited transient retries. HTTP429 stops; there is no paid fallback.
The default demo adapter uses deterministic English patterns. Separate evaluation
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
A failed preparation does not consume analysis attempts or block lexical/no-evidence
jobs and review finalization. Retried extraction nodes have no external write effects.

LangGraph saves checkpoints in PostgreSQL using the run UUID as thread ID. Its
review node interrupts after the report. A human Decision is an immutable business
record, then the worker resumes the saved graph. If final graph bookkeeping fails,
the recorded human decision survives and the report exposes a workflow error.
Checkpoints belong to the workflow library; explicit Alembic revisions own the
business schema and are applied before processes start.

## Approval and REST side effects

A ticket proposal freezes action, exact arguments, run, requesting actor, hash and
expiry. Only a reviewer/admin can approve; only that approving actor can execute.
Creating a newer run invalidates an unexecuted old proposal. An organization lock
serializes run-version changes with the authorization check and outbound write.
This deliberately trades per-organization write concurrency for clear safety in
a small local app; the REST timeout bounds the lock duration.

Approval persists an IntegrationCall with a stable idempotency key before sending.
The service atomically stores a receipt under a unique key and checks argument
hashes. Retrying after a lost response returns that receipt. If all responses are
lost, reconciliation reads by the original key even after expiry; it never issues
a new write. Request/response bodies are schema checked and the action is audited.

## Access boundaries

Opaque HttpOnly session cookies correspond to hashed tokens in the database.
Passwords use salted PBKDF2. Mutations check request origin; object access is
restricted by session organization, role and analyst ownership. The browser cannot
choose a trusted organization or actor. Auditors cannot mutate data. Runtime
tracing to external providers is disabled; secrets and private model reasoning
are not stored in logs. Audit history is append-only through application APIs.

These controls support a local demo and tested isolation. They are not a complete
enterprise identity, distributed quota or production operations platform.
