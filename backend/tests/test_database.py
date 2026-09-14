import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import create_engine, event, inspect, text

from counterparty.config import Settings
from counterparty.seed import seed_organizations

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url):
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def fixture_path(tmp_path):
    path = tmp_path / "organizations.json"
    path.write_text(
        json.dumps(
            [
                {
                    "slug": "synthetic-northstar-labs",
                    "name": "Northstar Labs (synthetic)",
                    "is_synthetic": True,
                }
            ]
        )
    )
    return path


@pytest.mark.anyio
async def test_readiness_requires_current_migration(
    database_url,
    migration_config,
    engine,
    client_factory,
):
    async with client_factory(Settings(database_url=database_url)) as client:
        assert (await client.get("/health/ready")).status_code == 503
        command.upgrade(migration_config, "head")
        assert (await client.get("/health/ready")).status_code == 200
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'obsolete'"))
        assert (await client.get("/health/ready")).status_code == 503


def test_migration_matches_models_and_can_be_reversed(migration_config, engine):
    command.upgrade(migration_config, "head")
    assert "organizations" in inspect(engine).get_table_names()
    command.check(migration_config)
    command.downgrade(migration_config, "base")
    assert "organizations" not in inspect(engine).get_table_names()
    command.upgrade(migration_config, "head")
    command.check(migration_config)


def test_seed_is_persistent_idempotent_and_preserves_edits(migration_config, engine, fixture_path):
    command.upgrade(migration_config, "head")
    seed_organizations(engine, fixture_path)
    with engine.begin() as connection:
        original = connection.execute(text("SELECT * FROM organizations")).mappings().one()
        assert original["is_synthetic"] is True
        assert original["created_at"].tzinfo is not None
        connection.execute(text("UPDATE organizations SET name = 'Edited synthetic company'"))
    seed_organizations(engine, fixture_path)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM organizations")).mappings().one()
        assert row["id"] == original["id"]
        assert row["name"] == "Edited synthetic company"


def test_concurrent_seed_does_not_duplicate(migration_config, engine, fixture_path):
    command.upgrade(migration_config, "head")
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: seed_organizations(engine, fixture_path), range(4)))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM organizations")) == 1


def test_concurrent_seed_with_reversed_records_avoids_deadlock(
    migration_config,
    engine,
    fixture_path,
    tmp_path,
):
    command.upgrade(migration_config, "head")
    records = json.loads(fixture_path.read_text()) + [
        {"slug": "synthetic-acme", "name": "Synthetic Acme", "is_synthetic": True}
    ]
    fixture_path.write_text(json.dumps(records))
    reversed_path = tmp_path / "reversed.json"
    reversed_path.write_text(json.dumps(list(reversed(records))))
    start = Barrier(2)

    def slow_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO organizations"):
            # Keep real row locks held long enough for the other importer to overlap.
            time.sleep(0.2)

    def run_seed(path):
        start.wait(timeout=5)
        return seed_organizations(engine, path)

    event.listen(engine, "after_cursor_execute", slow_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sum(executor.map(run_seed, [fixture_path, reversed_path])) == 2
    finally:
        event.remove(engine, "after_cursor_execute", slow_insert)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM organizations")) == 2


def test_seed_rejects_real_data_before_writing(migration_config, engine, fixture_path):
    command.upgrade(migration_config, "head")
    fixture_path.write_text(
        json.dumps(
            [
                {"slug": "synthetic-example", "name": "Synthetic example", "is_synthetic": True},
                {"slug": "real", "name": "Real data", "is_synthetic": False},
            ]
        )
    )
    with pytest.raises(ValueError):
        seed_organizations(engine, fixture_path)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM organizations")) == 0


def test_seed_rolls_back_when_slug_belongs_to_real_organization(
    migration_config,
    engine,
    fixture_path,
):
    command.upgrade(migration_config, "head")
    with engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO organizations (id, slug, name, is_synthetic)
            VALUES (gen_random_uuid(), 'synthetic-northstar-labs', 'Existing real company', false)
        """)
        )
    existing = json.loads(fixture_path.read_text())
    fixture_path.write_text(
        json.dumps(
            [
                {"slug": "synthetic-new", "name": "Synthetic new", "is_synthetic": True},
                *existing,
            ]
        )
    )
    with pytest.raises(ValueError, match="non-synthetic"):
        seed_organizations(engine, fixture_path)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, is_synthetic FROM organizations")).one()
        assert row == ("Existing real company", False)
