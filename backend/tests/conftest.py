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
