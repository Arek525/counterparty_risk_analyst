# Foundation Implementation Plan

> Execute inline, task by task, using the executing-plans workflow.

**Goal:** Run and verify the API/database foundation locally.

**Architecture:** FastAPI owns a SQLAlchemy pool. Compose starts PostgreSQL,
then Alembic, then the API. A CLI loads synthetic data explicitly.

**Tech Stack:** Python 3.13, FastAPI, Pydantic Settings, SQLAlchemy 2,
Psycopg 3, Alembic, PostgreSQL 17 with pgvector, Docker Compose, pytest, Ruff.

**Spec:** `docs/architecture/foundation.md`

## Global constraints

- No model calls, paid services, or external business integrations.
- Private working files stay Git-ignored and outside container build contexts.
- Tests run on real, disposable PostgreSQL databases, separate from demo data.
- No automatic database schema creation by ORM or API startup.

## Task 1: Health API and configuration

Files: `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/counterparty/`
(`config.py`, `database.py`, `main.py`, `health.py`),
`backend/tests/test_health.py`, `backend/tests/test_config.py`.

- [x] Write tests: a live process returns 200 with an unreachable database;
  readiness returns 503 with no credentials in body/logs; invalid database
  schemes fail configuration without displaying secret values.
- [x] Run `pytest tests/test_config.py tests/test_health.py` and record failure.
- [x] Implement `Settings`, `create_engine_for_settings(settings)`,
  `create_app(settings=None)`, and the `/health/live` and `/health/ready` routes.
- [x] Run those tests and Ruff checks.

## Task 2: Migrated organization and synthetic fixture

Files: `backend/alembic.ini`, `backend/src/counterparty/migrations/`,
`backend/src/counterparty/organizations.py`, `backend/src/counterparty/seed.py`,
`backend/tests/conftest.py`, `backend/tests/test_database.py`,
`datasets/synthetic/organizations.json`.

- [x] Write PostgreSQL integration tests for missing/current/stale schema,
  upgrade/downgrade, ORM/migration agreement, and serial/concurrent fixture loading.
- [x] Run integration tests against disposable databases; record the reversed-import deadlock regression before its fix.
- [x] Implement explicit Alembic migration with UUID PK, unique slug, nonempty
  name/slug checks, synthetic marker, and creation timestamp.
- [x] Implement `seed_organizations(engine, fixture_path)` using PostgreSQL
  `INSERT ... ON CONFLICT DO NOTHING` in one transaction; reject non-synthetic
  fixture input and conflicts with existing non-synthetic organizations.
- [x] Run complete tests, including schema drift check.

## Task 3: Reproducible runtime and demonstration

Files: `backend/Dockerfile`, `backend/.dockerignore`, `compose.yaml`,
`compose.test.yaml`, `.env.example`, `README.md`.

- [x] Lock dependency versions and pin container image digests.
- [x] Build runtime and test images, run the entire suite with Compose.
- [x] Start app on an empty volume; load fixture twice and record its UUID.
- [x] Stop database: live=200, ready=503. Restart: ready=200.
- [x] Recreate containers without removing volumes; verify the same UUID.
- [x] Document exact startup/test commands, architecture and remaining scope.
- [x] Review diff, private-file exclusion, and record verification results.

## Completion

Implemented and verified on 2026-09-14. See `docs/verification/foundation.md`.
The initial health skeleton failed four behavioral assertions before endpoint and
configuration implementation. The reversed-import test reproduced a real
PostgreSQL deadlock before the sorting fix. Final checks: 13 tests passed without
warnings, Ruff lint/format passed, startup/outage/recovery/persistence verified.
Work remains local on `feat/foundation`; no commit, merge, push, or publication.
