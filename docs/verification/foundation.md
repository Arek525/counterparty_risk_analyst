# Foundation verification — 2026-09-14

Environment: containerized Python 3.13.15 and PostgreSQL 17.11. The database image
includes pgvector 0.8.6; vector indexing is outside this increment.

## Automated checks

Executed against the final test image:

```bash
docker compose -f compose.test.yaml build --quiet tests
docker compose -f compose.test.yaml run --rm --no-deps tests ruff check .
docker compose -f compose.test.yaml run --rm --no-deps tests ruff format --check .
docker compose -f compose.test.yaml up --abort-on-container-exit --exit-code-from tests --attach tests
```

- Ruff: all checks passed; 13 Python files already formatted.
- pytest: **13 passed in 1.49s**, no warnings.
- Each integration test used a new disposable PostgreSQL database.
- Alembic's schema comparison found no pending model changes.
- The reversed-import regression produced PostgreSQL `DeadlockDetected` before
  the fix and passed after enforcing consistent slug order.

## Runtime checks

| Scenario | Observed result |
| --- | --- |
| Compose startup on a new named volume | Migration completed; API healthy |
| First explicit synthetic seed | 1 organization inserted |
| Repeated seed | 0 inserted; original organization retained |
| `/health/live`, `/health/ready`, `/docs` | HTTP 200 |
| Stop PostgreSQL while API stays running | Liveness 200, readiness 503 |
| Restart PostgreSQL | Readiness recovered to 200 |
| `docker compose down` then `up -d --wait --no-build` | Same organization UUID and synthetic marker retained |

Private working files and `.env` are Git-ignored. The backend Docker build
context uses an allowlist and does not include repository-root private files.

## Limits

These checks validate the API/database foundation, not document processing,
authorization, AI quality, or production readiness. Public deployment and
restricted database credentials require subsequent work. No model calls ran.
