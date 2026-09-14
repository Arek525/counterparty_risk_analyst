import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from counterparty.main import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client_factory():
    @asynccontextmanager
    async def open_client(settings):
        app = create_app(settings)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            yield client

    return open_client


@pytest.fixture
def database_url():
    """CREATE/DROP only a uniquely named database on an explicit test server."""
    admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    if not admin_url:
        pytest.fail("TEST_DATABASE_ADMIN_URL is required; use compose.test.yaml")
    name = f"test_counterparty_{uuid4().hex}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
        yield make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def migration_config(database_url):
    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture
def workflow_setup(database_url, migration_config):
    from alembic import command
    from sqlalchemy.orm import Session

    from counterparty.config import Settings
    from counterparty.database import create_engine_for_settings
    from counterparty.models import AnalysisRun, AssessmentCase, PolicySetVersion, User
    from counterparty.organizations import Organization
    from counterparty.security import hash_password
    from counterparty.worker import setup_checkpoints

    command.upgrade(migration_config, "head")
    settings = Settings(database_url=database_url)
    engine = create_engine_for_settings(settings)
    setup_checkpoints(engine)
    with Session(engine) as session:
        org = Organization(slug="workflow-test", name="Synthetic workflow", is_synthetic=True)
        session.add(org)
        session.flush()
        user = User(
            organization_id=org.id,
            email="workflow@example.test",
            name="Reviewer",
            password_hash=hash_password("Test-password-2026!"),
            role="reviewer",
        )
        session.add(user)
        session.flush()
        case = AssessmentCase(
            organization_id=org.id,
            owner_id=user.id,
            name="Test",
            counterparty_name="Synthetic vendor",
            relationship={"personal_data": True},
        )
        policy = PolicySetVersion(
            organization_id=org.id,
            created_by=user.id,
            name="Synthetic policy",
            version=1,
            status="approved",
            document_ids=[],
            requirements=[],
        )
        session.add_all([case, policy])
        session.flush()
        run = AnalysisRun(
            organization_id=org.id,
            case_id=case.id,
            created_by=user.id,
            policy_version_id=policy.id,
            input_snapshot={
                "case": {"id": str(case.id), "name": "Test", "relationship": {}},
                "policy": {"id": str(policy.id), "name": "Synthetic policy"},
                "requirements": [],
                "chunks": [],
                "model_mode": "demo",
            },
        )
        session.add(run)
        session.commit()
        ids = (run.id, user.id, org.id)
    yield engine, settings, ids
    engine.dispose()
