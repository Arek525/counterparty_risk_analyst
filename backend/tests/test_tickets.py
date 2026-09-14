from uuid import uuid4

import pytest
from alembic import command
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from counterparty.ticket_service import create_receipt

pytestmark = pytest.mark.integration


def test_ticket_service_persists_idempotency_and_rejects_changed_payload(
    database_url, migration_config
):
    command.upgrade(migration_config, "head")
    engine = create_engine(database_url)
    payload = {
        "organization_id": str(uuid4()),
        "run_id": str(uuid4()),
        "title": "Missing DPA",
        "body": "Please provide supporting evidence.",
    }
    key = str(uuid4())
    try:
        first = create_receipt(engine, key, payload)
        assert create_receipt(engine, key, payload) == first
        with pytest.raises(HTTPException) as error:
            create_receipt(engine, key, {**payload, "title": "Changed"})
        assert error.value.status_code == 409
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM demo_tickets")) == 1
    finally:
        engine.dispose()
