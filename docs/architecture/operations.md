# Local operations and retention

## Persistence and recovery

`postgres-data` stores business records, queue leases, workflow checkpoints and
local ticket receipts. `document-storage` stores original uploaded files. Both are
needed for a complete backup. `docker compose down` retains both. Never use
`down --volumes` unless deliberately deleting the entire local installation.

After a worker restart, unfinished jobs become eligible after their lease expires.
The default lease is 30 seconds and the execution supervisor limit is 120 seconds.
Automatic retry count is bounded; a failed analysis can be rerun as a new version.
A stored human decision is not removed by workflow-finalization failure.

## Consistent backup

Stop writers first so database and files represent one point in time. The example
writes a new local directory; do not commit backups containing uploaded documents.

```bash
backup_dir="/tmp/counterparty-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
docker compose stop frontend api worker tickets
docker compose exec -T db pg_dump -U counterparty -d counterparty -Fc > "$backup_dir/database.dump"
docker compose cp api:/app/storage "$backup_dir/storage"
docker compose start api worker tickets frontend
```

Keep `.env` credentials separately and encrypted if retaining a backup. No model
key is embedded in this dump by the application. Protect backups according to the
sensitivity of source documents.

## Restore into an intentionally empty installation

Stop application writers; do not run the following over data you intend to keep.
Start the database container and restore its dump before starting application
services. Use the matching application revision and retain both storage components.

```bash
docker compose up -d db
docker compose exec -T db pg_restore -U counterparty -d counterparty \
  --clean --if-exists --no-owner < "$backup_dir/database.dump"
docker compose create api
docker compose cp "$backup_dir/storage/." api:/app/storage/
docker compose run --rm --no-deps --user root api chown -R 10001:10001 /app/storage
docker compose up -d --wait
```

A successful restore should open historical reports and download their cited
source files. Test restoration against a separate Compose project before relying
on a backup. Local ticket receipts restore with the database, retaining idempotency.

## Explicit MVP retention policy

There is no automatic time-based expiry of business evidence or analysis history.
Referenced policy/document versions, reports, decisions, audit events and graph
checkpoints are retained indefinitely on this local installation. This is a
transparent MVP policy, not a claim of regulatory compliance.

Deleting an **unreferenced** document through the API removes its file, chunks and
embeddings. A document used by a policy or run cannot be deleted through that API,
because old reports must remain inspectable. Superseded versions remain accessible
under the same access rules. Session cookies expire, while stale session database
records currently remain until a deliberate database reset.

Full deletion requires a deliberate removal of both Compose volumes plus any
backups, browser traces/screenshots and externally retained provider data. External
provider retention depends on the chosen account's terms; local deletion cannot
erase data already sent to it. Do not enable real-document use until those terms
and a project-specific deletion policy have been chosen.
