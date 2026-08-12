from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Batch(Base):
    __tablename__ = "batches"

    __table_args__ = (
        Index(
            "uq_batches_active_batch_name",
            "batch_name",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    batch_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    location: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    class_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    training_days: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    monthly_fee: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    yearly_fee: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )