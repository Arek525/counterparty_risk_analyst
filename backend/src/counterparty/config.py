from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True, extra="ignore")

    database_url: SecretStr
    database_password: SecretStr | None = None
    demo_mode: bool = True
    model_mode: str = "demo"
    storage_path: str = "/app/storage"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://test",
    ]
    cookie_secure: bool = False
    ticket_service_url: str = "http://tickets:8010"
    ticket_service_token: SecretStr = SecretStr("local-demo-ticket-token")
    model_cache_path: str = "/app/model-cache"
    model_prepare_timeout_seconds: int = 600
    model_retry_seconds: int = 60
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 30
    worker_max_attempts: int = 3
    worker_max_runtime_seconds: int = 120

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and bool(url.database)
            # Also validate the port without including connection details in errors.
            _ = url.port
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must identify a postgresql+psycopg database")
        return value
