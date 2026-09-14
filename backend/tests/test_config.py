import pytest
from pydantic import ValidationError

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings


def test_rejects_non_postgresql_without_disclosing_password():
    with pytest.raises(ValidationError) as error:
        Settings(database_url="mysql://user:sensitive-password@db/app")
    assert "sensitive-password" not in str(error.value)


def test_settings_repr_hides_credentials():
    settings = Settings(database_url="postgresql+psycopg://user:sensitive-password@db/app")
    assert "sensitive-password" not in repr(settings)


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_separate_password_supports_url_reserved_characters():
    password = "literal@:/?#%$password"
    settings = Settings(
        database_url="postgresql+psycopg://user@db/app",
        database_password=password,
    )
    engine = create_engine_for_settings(settings)
    try:
        assert engine.url.password == password
        assert password not in repr(settings)
    finally:
        engine.dispose()
