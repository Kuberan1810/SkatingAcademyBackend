from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FeePayment(Base):

    __tablename__ = "fee_payments"

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "fee_month",
            "fee_year",
            name="uq_student_fee_period",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    transaction_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )

    fee_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    fee_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    base_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    discount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    late_fine: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    net_payable: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    collected_by: Mapped[int] = mapped_column(
        ForeignKey("admins.id"),
        nullable=False,
    )

    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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