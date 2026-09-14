from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase

from counterparty.config import Settings


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def create_engine_for_settings(settings: Settings) -> Engine:
    url = make_url(settings.database_url.get_secret_value())
    if settings.database_password is not None:
        url = url.set(password=settings.database_password.get_secret_value())
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=2,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 2,
            "options": "-c statement_timeout=2000 -c lock_timeout=2000",
        },
    )
