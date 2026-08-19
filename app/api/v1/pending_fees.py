from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.student import Student
from app.models.batch import Batch
from app.models.fee import FeePayment

from app.schemas.fee import (
    PendingFeeCollectionResponse,
    PendingFeeItem,
)


router = APIRouter(
    prefix="/pending-fees",
    tags=["Pending Fees"],
)


# =========================================================
# GET ALL PENDING FEES
# =========================================================

@router.get(
    "",
    response_model=PendingFeeCollectionResponse,
)
def get_pending_fees(

    status: str = Query(
        default="all",
        pattern=(
            "^(all|overdue|due_today|"
            "tomorrow|upcoming)$"
        ),
    ),

    search: str | None = Query(
        default=None,
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    # =====================================================
    # DATE
    # =====================================================

    today = date.today()

    current_month = today.month
    current_year = today.year

    tomorrow = date.fromordinal(
        today.toordinal() + 1
    )

    # =====================================================
    # GET ACTIVE STUDENTS + ACTIVE BATCH
    # =====================================================

    query = (
        db.query(
            Student,
            Batch,
        )
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
        .order_by(
            Student.full_name.asc()
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    if search and search.strip():

        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            (
                Student.full_name
                .ilike(search_value)
            )
            |
            (
                Student.phone_number
                .ilike(search_value)
            )
            |
            (
                Batch.batch_name
                .ilike(search_value)
            )
        )

    students = query.all()

    # =====================================================
    # RESPONSE LIST
    # =====================================================

    fees = []

    # =====================================================
    # SUMMARY
    # =====================================================

    total_pending_amount = 0
    total_students_count = 0

    overdue_amount = 0
    overdue_count = 0

    due_today_amount = 0
    due_today_count = 0

    upcoming_amount = 0
    upcoming_count = 0

    # =====================================================
    # PROCESS STUDENTS
    # =====================================================

    for student, batch in students:

        # =================================================
        # MONTHLY FEE
        # =================================================

        monthly_fee = int(
            student.monthly_fee
            if (student.monthly_fee is not None and student.monthly_fee > 0)
            else (batch.monthly_fee or 0)
        )

        if monthly_fee <= 0:
            continue

        # =================================================
        # GET ALL PAYMENTS FOR CURRENT MONTH
        #
        # IMPORTANT:
        # Don't use .first()
        #
        # Student may have:
        #
        # Payment 1 = ₹500
        # Payment 2 = ₹500
        #
        # Total = ₹1000
        # Monthly fee = ₹1500
        #
        # Pending = ₹500
        # =================================================

        payments = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id
                == student.id,

                FeePayment.fee_month
                == current_month,

                FeePayment.fee_year
                == current_year,
            )
            .all()
        )

        # =================================================
        # TOTAL PAID
        # =================================================

        total_paid = sum(
            int(
                payment.net_payable or 0
            )
            for payment in payments
        )

        # =================================================
        # PENDING AMOUNT
        # =================================================

        pending_amount = (
            monthly_fee - total_paid
        )

        # =================================================
        # FULLY PAID
        # =================================================

        if pending_amount <= 0:
            continue

        # =================================================
        # DUE DATE
        #
        # Same logic as your existing fee API
        # =================================================

        due_day = 1

        due_date = date(
            current_year,
            current_month,
            due_day,
        )

        # =================================================
        # STATUS
        # =================================================

        if due_date < today:

            fee_status = "Overdue"

        elif due_date == today:

            fee_status = "Due Today"

        elif due_date == tomorrow:

            fee_status = "Tomorrow"

        else:

            fee_status = "Upcoming"

        # =================================================
        # SUMMARY
        #
        # IMPORTANT:
        # Summary is calculated BEFORE status filter.
        # =================================================

        total_pending_amount += (
            pending_amount
        )

        total_students_count += 1

        # =================================================
        # OVERDUE
        # =================================================

        if fee_status == "Overdue":

            overdue_amount += (
                pending_amount
            )

            overdue_count += 1

        # =================================================
        # DUE TODAY
        # =================================================

        elif fee_status == "Due Today":

            due_today_amount += (
                pending_amount
            )

            due_today_count += 1

        # =================================================
        # UPCOMING
        # =================================================

        elif fee_status in (
            "Tomorrow",
            "Upcoming",
        ):

            upcoming_amount += (
                pending_amount
            )

            upcoming_count += 1

        # =================================================
        # STATUS FILTER
        # =================================================

        if status != "all":

            if status == "overdue":

                if fee_status != "Overdue":
                    continue

            elif status == "due_today":

                if fee_status != "Due Today":
                    continue

            elif status == "tomorrow":

                if fee_status != "Tomorrow":
                    continue

            elif status == "upcoming":

                if fee_status not in (
                    "Tomorrow",
                    "Upcoming",
                ):
                    continue

        # =================================================
        # FORMAT DATE
        # =================================================

        formatted_due_date = (
            due_date.strftime(
                "%b %d, %Y"
            )
        )

        # =================================================
        # ADD FEE
        # =================================================

        fees.append(
            PendingFeeItem(

                id=str(
                    student.id
                ),

                student_name=(
                    student.full_name
                ),

                batch_name=(
                    batch.batch_name
                ),

                due_date=(
                    formatted_due_date
                ),

                amount=(
                    pending_amount
                ),

                status=(
                    fee_status
                ),

                phone=(
                    student.phone_number
                ),

                avatar_uri=(
                    student.avatar_uri
                ),
            )
        )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {

        "status": "success",

        "message": (
            "Pending fees fetched successfully"
        ),

        "data": {

            "summary": {

                "total_pending_amount":
                    total_pending_amount,

                "total_students_count":
                    total_students_count,

                "overdue_amount":
                    overdue_amount,

                "overdue_count":
                    overdue_count,

                "due_today_amount":
                    due_today_amount,

                "due_today_count":
                    due_today_count,

                "upcoming_amount":
                    upcoming_amount,

                "upcoming_count":
                    upcoming_count,
            },

            "fees": [

                fee.model_dump()

                for fee
                in fees

            ],
        },
    }