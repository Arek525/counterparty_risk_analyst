# Local operations and retention

## Persistence and recovery

`postgres-data` stores business records, queue leases, workflow checkpoints and
saved information-request drafts. `document-storage` stores original uploaded files. Both are
needed for a complete backup. `docker compose down` retains both. Never use
`down --volumes` unless deliberately deleting the entire local installation.

After a worker restart, unfinished jobs become eligible after their lease expires.
The default lease is 30 seconds and the execution supervisor limit is 120 seconds.
Automatic retry count is bounded; explicit resume retries unfinished requirements
while retaining completed assessments. A new analysis creates a separate report.
A stored human decision is not removed by workflow-finalization failure.

## Database schema baseline

One frozen migration, `initial_schema.py`, creates the current schema directly.
It retains revision ID `0007_information_requests`, the former history's final
revision: databases already at that revision need no reset or version stamping.
`alembic upgrade head` leaves their records untouched. Earlier revisions are no
longer supported; do not stamp an older schema as current. Keep the previous
application version to upgrade such a database before switching to this baseline.
Future schema changes require new migrations; do not edit the baseline in place.

## Consistent backup

Stop writers first so database and files represent one point in time. The example
writes a new local directory; do not commit backups containing uploaded documents.

```bash
backup_dir="/tmp/counterparty-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
docker compose stop frontend api worker
docker compose exec -T db pg_dump -U counterparty -d counterparty -Fc > "$backup_dir/database.dump"
docker compose cp api:/app/storage "$backup_dir/storage"
docker compose start api worker frontend
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
on a backup. Saved drafts restore with the database.

## Explicit MVP retention policy

There is no automatic time-based expiry of business evidence or analysis history.
The UI supports explicit permanent deletion of reports, counterparty cases,
policy sets and documents. Each delete requires confirmation.
Deleting a report removes its saved progress, decision, workflow checkpoints,
saved information-request drafts and related activity content. Deleting a case also removes
its documents, files, chunks and embeddings. Shared organization policies remain.
A minimal deletion event records the actor and removed resource ID, without the
removed content. File removal is retried by the worker if a filesystem error
occurs; a durable cleanup record survives restart. The UI reports when original
file cleanup is still pending.

A policy set can be deleted after reports referring to it have been deleted.
A source document can be deleted after its referencing policy sets and reports.
Deleting a policy set removes its requirements and requirement embeddings, but
keeps its source files until separately deleted. Active processing blocks deletion;
only reviewers can delete company policies or whole cases. Analysts can delete
unreferenced evidence and unreviewed reports until the case is accepted or rejected.
Reviewed reports remain protected after a request for information. Deleted demo
seed content is not recreated by an application restart.


Full deletion requires a deliberate removal of both Compose volumes plus any
backups, browser traces/screenshots and externally retained provider data. External
provider retention depends on the chosen account's terms; local deletion cannot
erase data already sent to it. Do not enable real-document use until those terms
and a project-specific deletion policy have been chosen.


## Local embedding cache and reindex

Only the worker mounts `model-cache` at `/app/model-cache`; API startup does not
load model weights. The worker downloads two fixed public artifacts under a pinned
revision, verifies byte lengths and SHA256, and atomically renames complete files.
A filesystem lock serializes cache writers. Partial/corrupt files are retried; a
valid cache is read without a network request, even after process restart.

The document page shows index and model status, reports errors and offers **Reindex
document**. A repeated pending request is idempotent. Reindex preserves every source
chunk ID/location; retained reports and retrieval snapshots do not change. Indexing
has at most three automatic attempts. A crash recovers after its 150-second claim
lease; each work command is killed after 120 seconds. Reindex resets an exhausted
index for an explicit retry. Model preparation has a 600-second command budget and
60-second retry delay, independent of analysis attempts. The supervisor refreshes
its model heartbeat while commands run; status is stale after 30 seconds without it.
One worker is the supported deployment: status describes that single supervised child.

`MODEL_CACHE_PATH`, `MODEL_PREPARE_TIMEOUT_SECONDS`, and `MODEL_RETRY_SECONDS` can
be overridden in the worker environment. Changing the model requires a versioned
contract/migration and reindex; the revision is deliberately not a runtime switch.
No learned-to-hash or paid fallback exists. Source viewing and human-review
finalization remain available when preparation fails; new evidence-based analyses
require ready compatible indexes.

Cache files are reproducible public artifacts and contain no source documents.
They need not accompany the mandatory database+document backup, but retaining
`model-cache` enables offline recovery. `down --volumes` also removes this cache.
To reproduce a real-model check without a provider key, see
[embedding verification](retrieval.md).
