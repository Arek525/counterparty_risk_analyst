import pytest

from counterparty.config import Settings

pytestmark = pytest.mark.anyio


async def test_live_is_independent_of_database(client_factory):
    settings = Settings(database_url="postgresql+psycopg://user:secret@127.0.0.1:1/app")
    async with client_factory(settings) as client:
        assert (await client.get("/health/live")).status_code == 200


async def test_unreachable_database_is_not_ready_and_does_not_leak_secrets(caplog, client_factory):
    settings = Settings(database_url="postgresql+psycopg://user:sensitive-password@127.0.0.1:1/app")
    async with client_factory(settings) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "sensitive-password" not in response.text + caplog.text
