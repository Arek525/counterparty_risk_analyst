from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from counterparty.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
