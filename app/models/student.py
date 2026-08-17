from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    dob: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # OPTIONAL
    gender: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # OPTIONAL
    blood_group: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"),
        nullable=False,
        index=True,
    )

    # OPTIONAL
    join_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    parent_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # OPTIONAL
    emergency_contact: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    monthly_fee: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    avatar_uri: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
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