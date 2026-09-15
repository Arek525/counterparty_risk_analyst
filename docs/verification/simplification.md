# Ponytail simplification verification

The whole-project audit covered backend routes, security, persistence, document
processing, analysis, worker recovery, indexing, integrations and migrations;
all frontend pages, shared components, API types and CSS; and the Compose, CI,
evaluation and dependency configuration. Synthetic policies and gold labels were
treated as product and evaluation data rather than code to minimize.

Seven audited cuts were applied on top of `dc1e14f`:

- removed frontend fallbacks for API response shapes that the application has
  never serialized, plus unused response types and fields;
- delegated analysis requirement bounds, uniqueness and citation resolution to
  the existing analysis validator after retaining public Pydantic validation;
- reused the existing organization reference lock during document deletion;
- removed a duplicate graph resume branch while preserving decision and
  interrupt precedence;
- removed single-child SVG fragments and a redundant workspace breakpoint;
- removed the duplicate `httpx` declaration from the development group while
  retaining `httpx==0.28.1` as a direct runtime dependency.

The implementation changes production source by 27 added and 120 removed lines,
for a net reduction of 93 lines. Dependency metadata removes two duplicate dev
entries from `uv.lock`; the resolved environment still contains 76 packages and
no package or pinned version changed.

Verification used the Python 3.13 test image and disposable PostgreSQL. The full
backend suite passed with 122 tests, Ruff check passed, and Ruff reported all 42
Python files formatted. The deterministic evaluation gate retained its expected
lexical and hybrid scores, and all eight evaluation tests passed. Next.js
typecheck and production build passed. Three mocked Playwright journeys passed
against a fresh development server built from this worktree on port 3001.

No gold labels, historical evaluation artifacts, tests or provider configuration
were changed, and routine checks made no provider calls. The refactor retains
tenant and case authorization, immutable analysis inputs and retrieval snapshots,
citation grounding and metadata resolution, claim fencing, the shared physical
lock/checkpointer session, process budgets, index/cache provenance, explicit
approvals, ticket idempotency and append-only history. Real-provider quality,
legal interpretation and production readiness remain outside this refactor's
claims.
