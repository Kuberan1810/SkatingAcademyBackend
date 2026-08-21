import calendar
import uuid
from datetime import date, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.batch import Batch
from app.models.fee import FeePayment
from app.models.student import Student

from app.schemas.fee import (
    FeeCollect,
    FeeCollectResponse,
    FeePageResponse,
    RecentPaymentsResponse,
)


router = APIRouter(
    prefix="/fees",
    tags=["Fees"],
)


@router.post(
    "/collect",
    response_model=FeeCollectResponse,
    status_code=status.HTTP_201_CREATED,
)
def collect_fee(
    data: FeeCollect,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    # =====================================================
    # 1. Find student
    # =====================================================

    student = (
        db.query(Student)
        .filter(
            Student.id == data.student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or inactive",
        )

    # =====================================================
    # 2. Find student's active batch
    # =====================================================

    batch = (
        db.query(Batch)
        .filter(
            Batch.id == student.batch_id,
            Batch.is_active.is_(True),
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or inactive",
        )

    # =====================================================
    # 3. Base amount comes from batch
    # =====================================================

    base_amount = batch.monthly_fee

    # =====================================================
    # 4. Calculate net payable
    # =====================================================

    net_payable = (
        base_amount
        - data.discount
        + data.late_fine
    )

    if net_payable <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Net payable must be greater than 0",
        )

    # =====================================================
    # 5. Check if selected month already paid
    # =====================================================

    existing_payment = (
        db.query(FeePayment)
        .filter(
            FeePayment.student_id == data.student_id,
            FeePayment.fee_month == data.fee_month,
            FeePayment.fee_year == data.fee_year,
        )
        .first()
    )

    if existing_payment is not None:
        month_name = calendar.month_name[
            data.fee_month
        ]

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Fee for {month_name} "
                f"{data.fee_year} has already been collected"
            ),
        )

    # =====================================================
    # 6. Generate transaction ID
    # =====================================================

    transaction_id = (
        "TXN-"
        + uuid.uuid4().hex[:8].upper()
    )

    # =====================================================
    # 7. Create payment
    # =====================================================

    payment = FeePayment(
        transaction_id=transaction_id,
        student_id=student.id,

        fee_month=data.fee_month,
        fee_year=data.fee_year,

        base_amount=base_amount,

        discount=data.discount,

        late_fine=data.late_fine,

        net_payable=net_payable,

        payment_method=data.payment_method,

        notes=data.notes,

        collected_by=current_admin.id,
    )

    db.add(payment)

    # =====================================================
    # 8. Save transaction
    # =====================================================

    try:

        db.commit()

        db.refresh(payment)

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Fee for this student and selected "
                "month has already been collected"
            ),
        )

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect fee",
        )

    # =====================================================
    # 9. Create month label
    # =====================================================

    month_name = calendar.month_name[
        payment.fee_month
    ]

    fee_period_label = (
        f"{month_name} "
        f"{payment.fee_year} Monthly Fee"
    )

    # =====================================================
    # 10. Response
    # =====================================================

    return {
        "status": "success",

        "message": "Fee collected successfully",

        "data": {

            "transaction_id":
                payment.transaction_id,

            "student_id":
                student.id,

            "student_name":
                student.full_name,

            "batch_name":
                batch.batch_name,

            "fee_month":
                payment.fee_month,

            "fee_year":
                payment.fee_year,

            "fee_period_label":
                fee_period_label,

            "base_amount":
                payment.base_amount,

            "discount":
                payment.discount,

            "late_fine":
                payment.late_fine,

            "net_payable":
                payment.net_payable,

            "payment_method":
                payment.payment_method,

            "notes":
                payment.notes,

            "collected_by":
                payment.collected_by,

            "payment_date":
                payment.payment_date.isoformat(),

            "created_at":
                payment.created_at.isoformat(),
        },
    }




# =========================================================
# GET RECENT PAYMENTS
# =========================================================

@router.get(
    "/recent",
    response_model=RecentPaymentsResponse,
)
def get_recent_payments(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    recent_payment_records = (
        db.query(
            FeePayment,
            Student.full_name,
            Student.avatar_uri,
            Batch.batch_name,
        )
        .join(
            Student,
            FeePayment.student_id == Student.id,
        )
        .outerjoin(
            Batch,
            Student.batch_id == Batch.id,
        )
        .order_by(
            FeePayment.payment_date.desc()
        )
        .limit(limit)
        .all()
    )

    now = datetime.now()
    results = []

    for payment, student_name, avatar_uri, batch_name in recent_payment_records:
        payment_date = payment.payment_date
        if payment_date.tzinfo is not None:
            payment_date = payment_date.replace(tzinfo=None)

        difference = now - payment_date
        total_seconds = difference.total_seconds()
        total_hours = int(total_seconds // 3600)
        total_minutes = int(total_seconds // 60)

        if total_minutes < 60:
            time_label = "1 min ago" if total_minutes <= 1 else f"{total_minutes} min ago"
        elif total_hours < 24:
            time_label = "1 hr ago" if total_hours == 1 else f"{total_hours} hr ago"
        else:
            time_label = payment_date.strftime("%d/%m/%Y")

        results.append(
            {
                "id": str(payment.id),
                "student_id": payment.student_id,
                "name": student_name,
                "avatar_uri": avatar_uri,
                "batch_name": batch_name,
                "time_ago_or_date": time_label,
                "payment_date": payment_date.strftime("%Y-%m-%d"),
                "payment_method": payment.payment_method,
                "amount": int(payment.net_payable),
                "fee_month": payment.fee_month,
                "fee_year": payment.fee_year,
            }
        )

    return {
        "status": "success",
        "message": "Recent payments fetched successfully",
        "data": results,
    }


# =========================================================
# GET FEES PAGE
# =========================================================

@router.get(
    "/page",
    response_model=FeePageResponse,
)
def get_fees_page(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    today = date.today()

    # =====================================================
    # CURRENT MONTH
    # =====================================================

    current_month = today.month
    current_year = today.year

    current_month_start = today.replace(
        day=1
    )

    if current_month == 12:

        next_month_start = date(
            current_year + 1,
            1,
            1,
        )

    else:

        next_month_start = date(
            current_year,
            current_month + 1,
            1,
        )

    # =====================================================
    # 1. GET ALL ACTIVE STUDENTS
    # =====================================================

    students = (
        db.query(Student, Batch)
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
        .order_by(
            Student.id.desc()
        )
        .all()
    )

    total_students = len(students)

    # =====================================================
    # 2. TODAY'S COLLECTION COUNT
    # =====================================================

    # today_collection_count = (
    #     db.query(
    #         func.count(FeePayment.id)
    #     )
    #     .filter(
    #         FeePayment.payment_date >= today,
    #         FeePayment.payment_date
    #         < date(
    #             today.year,
    #             today.month,
    #             today.day,
    #         )
    #         .fromordinal(
    #             today.toordinal() + 1
    #         ),
    #     )
    #     .scalar()
    #     or 0
    # )


    tomorrow = date.fromordinal(
        today.toordinal() + 1
    )

    today_collection_count = (
        db.query(
            func.count(FeePayment.id)
        )
        .filter(
            FeePayment.payment_date >= today,
            FeePayment.payment_date < tomorrow,
        )
        .scalar()
        or 0
    )
    # =====================================================
    # 3. THIS MONTH COLLECTION
    # =====================================================

    this_month_amount = (
        db.query(
            func.coalesce(
                func.sum(
                    FeePayment.net_payable
                ),
                0,
            )
        )
        .filter(
            FeePayment.fee_month
            == current_month,

            FeePayment.fee_year
            == current_year,
        )
        .scalar()
        or 0
    )

    this_month_amount = int(
        this_month_amount
    )

    # =====================================================
    # 4. STUDENT FEE DATA
    # =====================================================

    student_items = []

    pending_fees_amount = 0

    for student, batch in students:

        # =================================================
        # CURRENT MONTH PAYMENT
        # =================================================

        payment = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id
                == student.id,

                FeePayment.fee_month
                == current_month,

                FeePayment.fee_year
                == current_year,
            )
            .order_by(
                FeePayment.payment_date.desc()
            )
            .first()
        )

        # =================================================
        # PAYMENT EXISTS
        # =================================================

        if payment is not None:

            payment_status = "paid"

            amount = int(
                payment.net_payable
            )

            paid_date = (
                payment.payment_date.strftime(
                    "%d %b %Y"
                )
                if payment.payment_date
                else None
            )

        # =================================================
        # NO CURRENT MONTH PAYMENT
        # =================================================

        else:

            amount = int(
                batch.monthly_fee
            )

            paid_date = None

            # ---------------------------------------------
            # FEE DUE DATE
            # ---------------------------------------------

            due_day = 1

            due_date = date(
                current_year,
                current_month,
                due_day,
            )

            # ---------------------------------------------
            # STATUS
            # ---------------------------------------------

            if today > due_date:

                payment_status = "overdue"

            elif today == due_date:

                payment_status = "due_today"

            else:

                payment_status = "unpaid"

            # ---------------------------------------------
            # Pending amount
            # ---------------------------------------------

            pending_fees_amount += amount

        # =================================================
        # ADD STUDENT
        # =================================================

        student_items.append(
            {
                "id":
                    str(student.id),

                "name":
                    student.full_name,
                    
                "batch_name": batch.batch_name,

                "location":
                    batch.location,

                "phone":
                    student.phone_number,

                "payment_status":
                    payment_status,

                "amount":
                    amount,

                "paid_date":
                    paid_date,
            }
        )

    # =====================================================
    # 5. RECENT PAYMENTS
    # =====================================================

    recent_payment_records = (
        db.query(
            FeePayment,
            Student.full_name,
        )
        .join(
            Student,
            FeePayment.student_id
            == Student.id,
        )
        .order_by(
            FeePayment.payment_date.desc()
        )
        .limit(10)
        .all()
    )

    recent_payments = []

    # =====================================================
    # 6. FORMAT RECENT PAYMENT TIME
    # =====================================================

    now = datetime.now(
        tz=None
    )

    for payment, student_name in (
        recent_payment_records
    ):

        payment_date = (
            payment.payment_date
        )

        # Remove timezone if database returns
        # timezone-aware datetime

        if (
            payment_date.tzinfo
            is not None
        ):

            payment_date = (
                payment_date.replace(
                    tzinfo=None
                )
            )

        difference = (
            now - payment_date
        )

        total_seconds = (
            difference.total_seconds()
        )

        total_hours = int(
            total_seconds // 3600
        )

        total_minutes = int(
            total_seconds // 60
        )

        # =================================================
        # LESS THAN 1 HOUR
        # =================================================

        if total_minutes < 60:

            if total_minutes <= 1:

                time_label = "1 min ago"

            else:

                time_label = (
                    f"{total_minutes} min ago"
                )

        # =================================================
        # LESS THAN 24 HOURS
        # =================================================

        elif total_hours < 24:

            if total_hours == 1:

                time_label = "1 hr ago"

            else:

                time_label = (
                    f"{total_hours} hr ago"
                )

        # =================================================
        # OLDER THAN 24 HOURS
        # =================================================

        else:

            time_label = (
                payment_date.strftime(
                    "%d/%m/%Y"
                )
            )

        # =================================================
        # ADD RECENT PAYMENT
        # =================================================

        recent_payments.append(
            {
                "id":
                    str(payment.id),

                "student_id":
                    payment.student_id,

                "name":
                    student_name,

                "time_ago_or_date":
                    time_label,

                "payment_method":
                    payment.payment_method,

                "amount":
                    int(
                        payment.net_payable
                    ),
            }
        )

    # =====================================================
    # 7. FINAL RESPONSE
    # =====================================================

    return {

        "status":
            "success",

        "message":
            "Fee page data fetched successfully",

        "data": {

            # ==============================================
            # OVERVIEW
            # ==============================================

            "overview": {

                "total_students_count":
                    total_students,

                "today_collection_count":
                    today_collection_count,

                "total_collection_target":
                    total_students,

                "pending_fees_amount":
                    pending_fees_amount,

                "this_month_amount":
                    this_month_amount,
            },

            # ==============================================
            # STUDENTS
            # ==============================================

            "students":
                student_items,

            # ==============================================
            # RECENT PAYMENTS
            # ==============================================

            "recent_payments":
                recent_payments,
        },
    }