import calendar
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.attendance import Attendance
from app.models.batch import Batch
from app.models.fee import FeePayment
from app.models.session import Session as SessionModel
from app.models.student import Student

from app.schemas.dashboard import DashboardResponse


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


# =========================================================
# HELPER
# =========================================================

def get_time_of_day(start_time) -> str:

    hour = start_time.hour

    if hour < 12:
        return "Morning"

    if hour < 17:
        return "Afternoon"

    return "Evening"


# =========================================================
# HELPER - FORMAT TIME
# =========================================================

def format_session_time(
    start_time,
    end_time,
) -> str:

    start_label = start_time.strftime(
        "%I:%M"
    ).lstrip("0")

    end_label = end_time.strftime(
        "%I:%M"
    ).lstrip("0")

    start_ampm = start_time.strftime(
        "%p"
    ).lower()

    end_ampm = end_time.strftime(
        "%p"
    ).lower()

    # Same AM/PM
    if start_ampm == end_ampm:

        return (
            f"{start_label} - "
            f"{end_label} "
            f"{end_ampm}"
        )

    return (
        f"{start_label} {start_ampm} - "
        f"{end_label} {end_ampm}"
    )




# =========================================================
# HELPER - FIND NEXT TRAINING DATE
# =========================================================

def get_next_training_date(
    today: date,
    current_time,
    training_days,
    start_time,
):

    if not training_days:
        return None

    normalized_training_days = {
        str(day).strip().lower()
        for day in training_days
        if day
    }

    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    for offset in range(0, 8):

        candidate_date = today + timedelta(days=offset)

        candidate_day = weekdays[candidate_date.weekday()]

        if candidate_day not in normalized_training_days:
            continue

        if offset == 0:
            if current_time < start_time:
                return candidate_date
            continue

        return candidate_date

    return None


# =========================================================
# HELPER - TODAY'S ACTUAL SESSION
# =========================================================

def get_today_batch_session(
    db: Session,
    batch_id: int,
    today: date,
):

    return (
        db.query(SessionModel)
        .filter(
            SessionModel.batch_id == batch_id,
            SessionModel.session_date == today,
        )
        .order_by(SessionModel.id.desc())
        .first()
    )


# =========================================================
# GET DASHBOARD
# =========================================================

@router.get(
    "",
    response_model=DashboardResponse,
)
def get_dashboard(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    today = date.today()

    # =====================================================
    # CURRENT MONTH
    # =====================================================

    current_month_start = today.replace(
        day=1
    )

    if today.month == 12:

        next_month_start = date(
            today.year + 1,
            1,
            1,
        )

    else:

        next_month_start = date(
            today.year,
            today.month + 1,
            1,
        )

    # =====================================================
    # PREVIOUS MONTH
    # =====================================================

    previous_month_end = current_month_start

    previous_month_start = (
        previous_month_end
        - timedelta(days=1)
    ).replace(day=1)

    # =====================================================
    # 1. TOTAL STUDENTS
    # =====================================================

    total_students = (
        db.query(
            func.count(Student.id)
        )
        .filter(
            Student.is_active.is_(True)
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 2. NEW STUDENTS THIS MONTH
    # =====================================================

    new_students_this_month = (
        db.query(
            func.count(Student.id)
        )
        .filter(
            Student.is_active.is_(True),
            Student.join_date >= current_month_start,
            Student.join_date < next_month_start,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 3. TOTAL BATCHES
    # =====================================================

    total_batches = (
        db.query(
            func.count(Batch.id)
        )
        .filter(
            Batch.is_active.is_(True)
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 4. NEW BATCHES THIS MONTH
    # =====================================================

    new_batches_this_month = (
        db.query(
            func.count(Batch.id)
        )
        .filter(
            Batch.is_active.is_(True),
            Batch.created_at >= current_month_start,
            Batch.created_at < next_month_start,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 5. TODAY'S SESSIONS
    # =====================================================

    today_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_date == today
        )
        .order_by(
            SessionModel.scheduled_start_time
        )
        .all()
    )

    scheduled_sessions = len(
        today_sessions
    )

    completed_sessions = sum(
        1
        for session in today_sessions
        if session.status == "COMPLETED"
    )

    active_sessions = sum(
        1
        for session in today_sessions
        if session.status == "LIVE"
    )

    # =====================================================
    # 6. TODAY'S EXPECTED STUDENTS
    # =====================================================

    total_expected = 0

    for session in today_sessions:

        student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id == session.batch_id,
                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        total_expected += student_count

    # =====================================================
    # 7. TODAY'S PRESENT STUDENTS
    # =====================================================

    present_today = (
        db.query(
            func.count(
                func.distinct(
                    Attendance.student_id
                )
            )
        )
        .join(
            SessionModel,
            Attendance.session_id
            == SessionModel.id,
        )
        .filter(
            SessionModel.session_date == today,
            Attendance.status == "Present",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 8. ATTENDANCE %
    # =====================================================

    attendance_percentage = (
        round(
            (
                present_today
                / total_expected
            ) * 100,
            2,
        )
        if total_expected > 0
        else 0
    )

    # =====================================================
    # 9. CURRENT MONTH REVENUE
    # =====================================================

    current_revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    FeePayment.net_payable
                ),
                0,
            )
        )
        .filter(
            FeePayment.payment_date
            >= current_month_start,
            FeePayment.payment_date
            < next_month_start,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 10. PREVIOUS MONTH REVENUE
    # =====================================================

    previous_revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    FeePayment.net_payable
                ),
                0,
            )
        )
        .filter(
            FeePayment.payment_date
            >= previous_month_start,
            FeePayment.payment_date
            < current_month_start,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # 11. REVENUE CHANGE %
    # =====================================================

    if previous_revenue > 0:

        revenue_change_percentage = round(
            (
                (
                    current_revenue
                    - previous_revenue
                )
                / previous_revenue
            )
            * 100,
            2,
        )

    elif current_revenue > 0:

        revenue_change_percentage = 100.0

    else:

        revenue_change_percentage = 0.0

    # =====================================================
    # 12. PENDING FEES
    # =====================================================

    active_students = (
        db.query(Student)
        .filter(
            Student.is_active.is_(True)
        )
        .all()
    )

    pending_fee_items = []

    for student in active_students:

        # ---------------------------------------------
        # Check current month's payment
        # ---------------------------------------------

        payment_exists = (
            db.query(FeePayment.id)
            .filter(
                FeePayment.student_id
                == student.id,

                FeePayment.fee_month
                == today.month,

                FeePayment.fee_year
                == today.year,
            )
            .first()
        )

        if payment_exists is not None:
            continue

        # ---------------------------------------------
        # Student batch
        # ---------------------------------------------

        batch = (
            db.query(Batch)
            .filter(
                Batch.id == student.batch_id,
                Batch.is_active.is_(True),
            )
            .first()
        )

        if batch is None:
            continue

        # ---------------------------------------------
        # Due date
        #
        # Current rule:
        # student's join-date day
        # ---------------------------------------------

        due_day = min(
            student.join_date.day,
            28,
        )

        due_date = today.replace(
            day=due_day
        )

        # ---------------------------------------------
        # Status
        # ---------------------------------------------

        if today > due_date:

            fee_status = "Overdue"

        elif today == due_date:

            fee_status = "Due Today"

        else:

            fee_status = "Upcoming"

        # ---------------------------------------------
        # Add fee
        # ---------------------------------------------

        pending_fee_items.append(
            {
                "id": str(student.id),

                "student_name":
                    student.full_name,

                "batch_name":
                    batch.batch_name,

                "due_date":
                    due_date.strftime(
                        "%b %d, %Y"
                    ),

                "amount":
                    batch.monthly_fee,

                "status":
                    fee_status,

                "phone":
                    student.phone_number,

                "avatar_uri":
                    student.avatar_uri,
            }
        )

    # =====================================================
    # 13. PENDING FEE SUMMARY
    # =====================================================

    pending_amount = sum(
        item["amount"]
        for item in pending_fee_items
    )

    students_due = len(
        pending_fee_items
    )

    # =====================================================
    # 14. UPCOMING SESSIONS
    #
    # Upcoming sessions are calculated from:
    # Batch.training_days
    # Batch.start_time
    # Batch.end_time
    #
    # No future SessionModel rows are created.
    # =====================================================

    upcoming_session_items = []

    now = datetime.now()
    current_time = now.time()

    active_batches = (
        db.query(Batch)
        .filter(Batch.is_active.is_(True))
        .order_by(Batch.start_time.asc())
        .all()
    )

    candidate_dates = []

    for batch in active_batches:

        next_date = get_next_training_date(
            today=today,
            current_time=current_time,
            training_days=batch.training_days,
            start_time=batch.start_time,
        )

        if next_date is not None:
            candidate_dates.append(next_date)

    if candidate_dates:
        upcoming_date = min(candidate_dates)
    else:
        upcoming_date = None

    if upcoming_date is not None:

        upcoming_weekday = upcoming_date.strftime("%A").lower()

        for batch in active_batches:

            training_days = batch.training_days or []

            normalized_training_days = {
                str(day).strip().lower()
                for day in training_days
                if day
            }

            if upcoming_weekday not in normalized_training_days:
                continue

            student_count = (
                db.query(func.count(Student.id))
                .filter(
                    Student.batch_id == batch.id,
                    Student.is_active.is_(True),
                )
                .scalar()
                or 0
            )

            existing_session = None

            if upcoming_date == today:
                existing_session = get_today_batch_session(
                    db=db,
                    batch_id=batch.id,
                    today=today,
                )

                if (
                    existing_session is not None
                    and existing_session.status == "COMPLETED"
                ):
                    continue

            time_label = format_session_time(
                batch.start_time,
                batch.end_time,
            )

            upcoming_session_items.append(
                {
                    "id": str(
                        existing_session.id
                        if existing_session is not None
                        else batch.id
                    ),
                    "batch_id": batch.id,
                    "batch_name": batch.batch_name,
                    "class_type": batch.class_type,
                    "location": batch.location,
                    "date": upcoming_date.isoformat(),
                    "day": upcoming_date.strftime("%A"),
                    "start_time": batch.start_time.strftime("%I:%M %p").lstrip("0"),
                    "end_time": batch.end_time.strftime("%I:%M %p").lstrip("0"),
                    "time": time_label,
                    "students_count": student_count,
                }
            )

    upcoming_session_items.sort(
        key=lambda item: item["start_time"]
    )

    if upcoming_date is not None:
        display_date = upcoming_date.strftime("%A, %d %b, %Y")
    else:
        display_date = None

    # =====================================================
    # 16. FINAL RESPONSE
    # =====================================================

    return {

        "status": "success",

        "message":
            "Dashboard data fetched successfully",

        "data": {

            # ==========================================
            # OVERVIEW
            # ==========================================

            "overview": {

                "students": {

                    "total":
                        total_students,

                    "new_this_month":
                        new_students_this_month,
                },

                "attendance": {

                    "present_today":
                        present_today,

                    "total_expected":
                        total_expected,

                    "percentage":
                        attendance_percentage,
                },

                "fees": {

                    "pending_amount":
                        pending_amount,

                    "students_due":
                        students_due,
                },

                "revenue": {

                    "total":
                        current_revenue,

                    "change_percentage":
                        revenue_change_percentage,
                },

                "total_batches":
                    total_batches,

                "new_batches_this_month":
                    new_batches_this_month,

                "todays_sessions": {

                    "scheduled":
                        scheduled_sessions,

                    "completed":
                        completed_sessions,

                    "total_active_sessions":
                        active_sessions,
                },
            },

            # ==========================================
            # UPCOMING SESSIONS
            # ==========================================

            "upcoming_sessions": {

                "display_date":
                    display_date,

                "sessions":
                    upcoming_session_items,
            },

            # ==========================================
            # PENDING FEES
            # ==========================================

            "pending_fees": {

                "summary": {

                    "total_amount":
                        pending_amount,

                    "students_count":
                        students_due,
                },

                "fees":
                    pending_fee_items,
            },
        },
    }