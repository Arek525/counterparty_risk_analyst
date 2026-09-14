# MVP implementation contract

The approved target is the full local MVP. Model calls default to an explicitly
labeled deterministic demo adapter. A configured real adapter is optional and
must never silently fall back to paid services. Real-model quality remains an
explicit pending evaluation when credentials are absent.

## Shared API

All business routes use `/api`. Session authentication uses an HttpOnly cookie
and server-side sessions; same-origin frontend requests through Next rewrites.
Mutations enforce Origin when present and role/organization/case permissions.
Demo credentials are seeded explicitly, documented, and usable only locally.

- GET /api/meta: demo/model configuration (no secrets), application version.
- POST /api/auth/login {email,password}; GET /api/auth/me; POST /api/auth/logout.
- GET /api/demo/accounts: local demo account descriptions, gated by demo mode.
- GET/POST /api/cases: {name,counterparty_name,relationship:{purpose,data_shared,
  system_access,business_criticality,personal_data,privileged_access}}.
- GET /api/cases/{id}: case details. PATCH /api/cases/{id}: relationship/name.
- GET /api/documents?case_id=... (omit for organization policy documents).
- POST /api/documents multipart file, kind=policy|evidence, optional case_id.
- GET /api/documents/{id}: metadata and chunks [{id,text,location}].
- GET /api/documents/{id}/download; DELETE /api/documents/{id}: reject referenced
  versions (retained audit history), delete unreferenced file/chunks/embeddings.
- GET /api/policies; POST /api/policies/propose {document_ids:[uuid],name}.
- GET /api/policies/{id}; PUT /api/policies/{id}/requirements {requirements:[...]}
  only drafts; POST /api/policies/{id}/approve reviewer only. Edits to approved
  policies require POST /api/policies/{id}/clone, producing a draft new version.
- GET/POST /api/cases/{id}/runs: POST {policy_version_id,retrieval_variant:'lexical'|'hybrid'}.
- GET /api/runs/{id}: status, report, timestamps, events, model and input version.
- POST /api/runs/{id}/decision {decision:'accepted'|'rejected'|'needs_information',rationale}.
- GET /api/audit?case_id=... (optional, organization scoped).
- POST /api/runs/{id}/ticket-proposals {title,body}: create exact proposed args.
- POST /api/approvals/{id}/approve: reviewer, bound action/run/args/actor/expiry.
- GET /api/runs/{id}/tickets; POST /api/approvals/{id}/execute: durable idempotent
  REST call; returns current result, never creates a duplicate; GET ticket status.
- POST /api/approvals/{id}/reconcile: recover a lost receipt by read-only lookup
  of the persisted idempotency key, with no repeated external write.

Objects use string UUID `id`, ISO8601 timestamps, and list endpoints return arrays.
Errors are JSON {detail:...}, standard 401/403/404/409/422. Never trust an organization
or actor supplied in a request. Auditor is read-only; analyst creates cases,
documents, drafts and analysis; reviewer also approves policies/decisions/writes;
administrator also manages local configuration. Case ownership limits analysts;
reviewers/auditors/admin can access all cases within their organization.

## Analysis adapter contract (owned by analysis module)

`counterparty.analysis.propose_requirements(chunks: list[dict], mode="demo") -> list[dict]`.
Each chunk has id, document_id, text, location, kind, optional evidence_type.
Requirement keys: id, title, field, operator, expected, severity (Low/Medium/High),
applicability (dict context key -> required value), source (chunk_id,document_id,
location,quote), evaluation_method (deterministic|llm|manual).
Supported operators eq,lte,gte,contains,present,manual. All returned data must be
validated before approval and source quote must resolve to an eligible chunk.

`counterparty.analysis.analyze(snapshot: dict, variant: str='hybrid') -> dict`.
Immutable snapshot contains case:{id,name,relationship}, policy:{id,name},
requirements:[...], chunks:[...], model_mode:'demo'|'gemini'. Report contains
findings:[{requirement_id,title,status,severity,explanation,evidence:[{chunk_id,
document_id,location,quote,evidence_type}],missing_information}], risk,
completeness (0..100), summary, questions:[str], discrepancies:[...], model_mode,
model_name, metrics:{input_tokens,output_tokens,cost_usd,duration_ms},
rules_version,prompt_version. Risk statuses Low/Medium/High/Unable to assess;
finding statuses pass/fail/unknown/conflict/not_applicable.

## Shared persistence (owned by backend domain module)

`counterparty.models` registers all tables on existing Base. UUID ids and
timezone-aware dates. JSON fields use JSONB. Public helpers in
`counterparty.security`: `get_session(request)` dependency yields SQLAlchemy
Session; `current_user` FastAPI dependency yields User; `require_roles(user,*roles)`;
`get_case(session,user,case_id)` returns scoped case or raises 404/403;
`audit(session,user,event,case_id=None,run_id=None,details=None)` inserts AuditEvent.

User: id,organization_id,email,password_hash,role,name,is_active.
AssessmentCase: id,organization_id,owner_id,name,counterparty_name,relationship,
created_at,updated_at.
Document: id,organization_id,case_id nullable,uploaded_by,kind,filename,sha256,
storage_key,version,media_type,created_at.
DocumentChunk: id,document_id,organization_id,case_id nullable,text,location,
embedding Vector(128),embedding_model='demo-hash-v1'.
PolicySetVersion: id,organization_id,name,version,status,document_ids JSON,
requirements JSON,created_by,approved_by nullable,created_at,approved_at nullable.
AnalysisRun: id,organization_id,case_id,created_by,policy_version_id,status
(queued,running,awaiting_review,completed,failed),input_snapshot JSON,report JSON
nullable,retrieval_variant,model_mode,error nullable,attempts int default0,
lease_owner nullable,lease_expires_at nullable,created_at,started_at nullable,
finished_at nullable. Worker creates report and awaits reviewer; decision completes.
Decision: id,organization_id,run_id,actor_id,decision,rationale,created_at.
AuditEvent: id,organization_id,actor_id nullable,case_id nullable,run_id nullable,
event,details JSON,created_at. Application does not update/delete audit records.
ApprovalRequest: id,organization_id,run_id,requested_by,approved_by nullable,
action='create_ticket',arguments JSON,arguments_hash,status
(proposed,approved,executing,executed,failed),expires_at,created_at,approved_at nullable.
IntegrationCall: id,organization_id,approval_id unique,idempotency_key unique,
status (pending,succeeded,failed),request JSON,response JSON nullable,error nullable,
attempts int default0,created_at,updated_at.

Business models and schema revisions live alongside the shared backend package.
Analysis adapters, orchestration and REST integration remain separate modules.

## Durable execution

Separate worker claims runs in PostgreSQL using FOR UPDATE SKIP LOCKED. Session
advisory lock per run prevents two workers executing the same run even after a
lease expires. Lease/retries bounded; process crash releases lock and lease allows
recovery. LangGraph with PostgreSQL checkpointer uses run UUID as thread id,
resumes checkpoint, generates report then interrupts for review. Human decision
is immutable DB business data; worker resumes graph with the stored decision.
Ticket writes use stable persisted idempotency key and a demo REST service with
durable database receipts. Retries cover lost responses without duplicate effects.

## Acceptance

Run backend PostgreSQL tests, frontend build/type check and browser end-to-end
journey. Cover two policy sets and complete/missing/conflict/discrepancy/injection
cases, input immutability, source citations, roles and organization isolation,
worker recovery, exact write approval, expiration and duplicate execution.
Compare lexical/hybrid retrieval on held-out synthetic data. Document measured
demo results and real-provider evaluation pending credentials, without claiming
LLM quality from fixtures.
