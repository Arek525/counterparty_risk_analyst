# Local MVP verification — 2026-09-14

Scope: local synthetic application with the deterministic demo adapter. No paid
model calls, external publication or real business-system writes were made.
Real-model quality remains [pending](../../evaluations/report-gemini.md).

## Automated backend and evaluation

The packaged backend test image runs against PostgreSQL 17/pgvector, using a fresh
random database per database test. Complete suite: **72 passed**, no skips;
Ruff check and format check passed. The image runs as a non-root user. The tests
cover:

- Fresh-process model registration, migrations/model agreement and reversible
  upgrade/downgrade on disposable databases; absent/stale/unavailable DB readiness.
- Sessions, logout/expiry, request origin, organization isolation, analyst ownership
  and read-only auditors.
- Upload validation, PDF text/unsupported scans, source coordinates, versioning,
  deduplication, concurrent ingestion and file rollback/deletion rules.
- Two policies, editable proposals, reviewed immutable versions, applicability,
  explicit comparisons, decimal/compound statements and evidence provenance.
- pgvector cosine agreement with the offline computation, eligible version/case
  filtering and immutable scores/snapshots after newer document uploads.
- Provider quota/configuration failures stop the job without outer retries; transient
  request retries remain bounded inside the adapter.
- Durable graph pause/resume, stale lease recovery, exclusive execution, lost
  ownership, immutable reviewed reports and preservation of human decisions on
  workflow-finalization failure.
- Approval actor/run/argument binding, expiry, replay, tampering, superseded runs,
  concurrent new analysis vs external write, lost responses and read-only receipt
  reconciliation after all three responses are lost.

The evaluation gate's **7 tests passed**. A separate held-out demo evaluation
completed with its regression gate passing on ten hand-authored synthetic cases:

| Variant | Finding accuracy | Risk accuracy | Retrieval recall@3 | Exact quote resolution |
|---|---:|---:|---:|---:|
| Lexical | 91.7% | 90.0% | 90.9% | 100% |
| Hybrid | 100% | 100% | 100% | 100% |

These measurements concern a tiny deterministic regression corpus. They do not
establish real LLM quality, semantic entailment or general retrieval quality.
Full per-case outputs and limitations are in [the evaluation report](../../evaluations/report-demo.md).

## Running application, real API and worker

The application image built from locked dependencies; migrations applied before
API/worker/tickets. Explicit seed created 5 accounts, 2 policies, 5 cases and 7 documents;
repeating seed created zero additional records. `alembic check` reported no new
upgrade operations after the worker created its library-owned checkpoint tables.

`python3 scripts/verify_demo.py` sent six actual API jobs to the separate worker,
covering both policies and all five seeded scenarios. Every referenced quote was
resolved through the document API:

| Scenario | Risk | Evidence completeness | Resolved quote references |
|---|---|---:|---:|
| Complete | Low | 100% | 3 |
| Missing | High | 33.3% | 1 |
| Direct conflict | High | 66.7% | 4 |
| Possible regional discrepancy | Unable to assess | 100% | 3 |
| Embedded hostile instructions | High | 100% | 3 |
| Alternate policy with manual requirement | Unable to assess | 75% | 3 |

A worker container restart while reports awaited review was followed by a human
`needs_information` decision. The saved graph resumed, retained the reviewed
findings and completed. A separately approved ticket was then created through the
real REST simulator. Repeating execute returned the same ticket UUID; status read
returned `open`.

## Persistence, backup and restore

After `docker compose down` and subsequent startup, all six reports, policy
originals and the same ticket remained available. Named database/file volumes
were retained.

A consistent backup stopped API/worker/ticket writers, ran `pg_dump -Fc` and
copied the document volume. The dump was restored into a newly created disposable
database. It contained 7 documents, 6 runs, 1 decision, 1 ticket and 19 checkpoints.
Every restored storage reference resolved to its copied original with a matching
SHA256 hash. The verification database was then dropped; the application database
was not overwritten. See [operations](../architecture/operations.md) for commands
and the explicit retention policy.

## Browser and build checks

Next.js production build and TypeScript checks passed. The final combined browser
run passed **4/4 tests** against the Docker-hosted frontend. Three browser boundary
tests passed, including nullable provider cost and workflow-error rendering.
The real-stack browser journey passed on the Docker-hosted frontend: login,
create case/context, independent evidence upload, approved policy selection,
worker report, citation dialog, accepted decision with rationale, ticket preview,
proposal, approval, execute and status refresh.

Manual browser inspection produced no page errors and no horizontal overflow at
390px width. Final visual review also checked desktop reports and empty-state
behavior. Synthetic browser test cases remain in the local demo database.

## CI and remaining boundary

GitHub Actions is configured to build/test PostgreSQL, backend, evaluation gate,
frontend and the real browser journey without API keys. Equivalent commands were
run locally. The remote workflow has not been run or published from this session.

Live Gemini compatibility and quality require an API key, explicit model choice,
quota/data-term review and a separate measured evaluation. The adapter's mocked
contract tests and demo scores do not fulfill that real-model validation step.
Public hosting and enterprise operational hardening remain outside this local MVP.
