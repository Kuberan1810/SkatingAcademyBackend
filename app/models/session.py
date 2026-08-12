from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"),
        nullable=False,
        index=True,
    )

    coach_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id"),
        nullable=False,
        index=True,
    )

    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    scheduled_start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    scheduled_end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    actual_start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    actual_end_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="LIVE",
    )

    location: Mapped[str] = mapped_column(
        String(150),
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