# Application foundation

The foundation runs a Python API and PostgreSQL as separate Docker Compose
services. A one-shot migration service upgrades the database before the API
starts. The same backend package will later be imported by a worker.

The API owns a SQLAlchemy connection pool for its process lifetime. Synchronous
database operations run in FastAPI's thread pool; no blocking database calls run
on the event loop. Psycopg 3 connects to PostgreSQL. Connection, pool checkout,
and SQL statement timeouts bound database health checks.

`GET /health/live` checks the API process only. `GET /health/ready` checks database
connectivity and the applied Alembic revision against the migration files shipped
with this application. It returns a generic 503 response when unavailable or
outdated, without exposing connection strings or database exceptions.

`Organization` has a UUID identity, unique slug, name, synthetic-data marker,
and timezone-aware creation timestamp. The initial fixture is synthetic and
loaded explicitly through a CLI. Its insertion is transactional and idempotent,
including concurrent invocations, without overwriting existing organizations.
Importers acquire row locks in slug order to avoid deadlocks when fixture files
list the same organizations in different orders.
No organization data endpoints are exposed before authentication and permission
boundaries are implemented.

PostgreSQL data lives on a named volume. Tests use a separate Compose project,
network, and temporary PostgreSQL storage. Tests create disposable databases on
that server; they never reset the application's database. The PostgreSQL image
includes pgvector, but this increment does not create embeddings or vector tables.

The build uses a dependency lock, pinned build dependencies and container image
digests, and runs as a non-root OS user. Compose binds
the API to loopback and does not publish the database port. Local database
credentials are development-only; this is not a public deployment configuration.
The database password is supplied separately from the connection URL, then
attached through SQLAlchemy's URL object so reserved characters retain their
literal meaning. Settings representations redact both values.

## Verification

Check clean migrations, migration/model consistency, upgrade/downgrade on an
empty disposable database, repeat/concurrent fixture loading, ready/not-ready
responses, absence of secret data in errors, and recovery after database loss.
Recreate application containers and check that the same fixture UUID remains.

## References

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [SQLAlchemy PostgreSQL / Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Compose startup ordering](https://docs.docker.com/compose/how-tos/startup-order/)
