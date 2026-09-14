# AI Counterparty & Compliance Analyst

An application for assessing counterparties against an organization's approved
information-security and privacy requirements. Planned assessments will link
findings to source evidence and keep risk, evidence completeness, and human
decisions separate.

**Implemented scope:** the API/database foundation, schema migrations, health
checks, and an explicit synthetic organization fixture. Document ingestion,
authentication, the frontend, assessments, and model integrations are subsequent
increments. No model API key or paid service is needed for this foundation.

## Run locally

Requirements: Docker Engine or Docker Desktop with Docker Compose v2. The first
build downloads container images and Python dependencies. Host Python is not
required.

From the repository root:

```bash
cp -n .env.example .env
docker compose up --build -d --wait
docker compose run --rm seed
```

Open [API documentation](http://localhost:8000/docs). The API listens on loopback
only; PostgreSQL is reachable only inside the Compose network. Change `API_PORT`
in `.env` if port 8000 is occupied. This setup is for local synthetic development.
Compose passes the database password separately from `DATABASE_URL`, so URL
characters such as `@` and `:` do not need escaping. In `.env`, single-quote a
password containing `$` to prevent Compose variable interpolation.
The development database account owns its database; separate restricted runtime
credentials are required before a public deployment.

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
docker compose exec db psql -U counterparty -d counterparty -c \
  'SELECT id, slug, name, is_synthetic, created_at FROM organizations;'
```

Both health endpoints return HTTP 200 when the application is ready. Liveness
only checks the API process. Readiness returns HTTP 503 when the database cannot
be queried or its migration revision differs from the application. Responses
do not expose database connection details.

The `seed` command loads `datasets/synthetic/organizations.json`. It is explicit,
transactional and safe to repeat, including concurrent calls. It preserves
existing records and rejects non-synthetic fixture data or a slug belonging to
an existing non-synthetic organization. Northstar Labs is fictional demo data,
not a customer encoded in application logic.

## Data and migrations

```text
Compose → PostgreSQL healthy → Alembic upgrade succeeds → FastAPI
CLI seed → validated synthetic fixture → transaction → organizations
```

Alembic version-controls database structure. The API does not create tables on
startup. The `migrate` service runs upgrades before the API starts.

```bash
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose logs api migrate
docker compose down
```

`docker compose down` removes containers and the network but retains database
data in the named `postgres-data` volume. Starting the stack again reuses that
volume. Adding `--volumes` deletes that data; use it only for a deliberate reset.

## Tests

Tests use the same PostgreSQL image as the application, with a separate Compose
project and temporary storage. Each database test creates and drops its own
randomly named database. They do not use application credentials or reset the
application database. A missing test database configuration fails the integration
suite instead of silently skipping it.

```bash
docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f compose.test.yaml run --rm --no-deps tests ruff check .
docker compose -f compose.test.yaml run --rm --no-deps tests ruff format --check .
docker compose -f compose.test.yaml down
```

The suite covers readiness with missing/current/stale schema, unavailable
database behavior, credential redaction, migration/model consistency,
upgrade/downgrade on a disposable database, and serial/concurrent synthetic data
loading with rollback on conflicting data. A regression test reproduces
overlapping imports in reversed record order to check deadlock prevention.

For local backend editing, install Python 3.13 and uv 0.12.13, then run `uv sync
--locked` from `backend/`. Unit tests can run with `uv run pytest tests/test_config.py
tests/test_health.py`. Use Compose for the complete integration suite.

## Structure

- `backend/src/counterparty/`: configuration, database access, health API,
  organization model, migrations, synthetic-data CLI.
- `backend/tests/`: behavioral and PostgreSQL integration tests.
- `backend/uv.lock`: locked Python dependencies.
- `datasets/synthetic/`: clearly labeled public demo fixtures.
- `compose.yaml`: persistent local application stack.
- `compose.test.yaml`: isolated, disposable test stack.
- [Foundation architecture](docs/architecture/foundation.md): boundaries,
  decisions, and links to upstream documentation.
- [Verification results](docs/verification/foundation.md): automated checks and
  the database outage/persistence demonstration.

No organization or case data is publicly exposed through this initial API.
Authentication, organization/case isolation, document permissions, and audit
history must accompany the first data-handling endpoints. This foundation does
not yet assess compliance or produce risk findings.
