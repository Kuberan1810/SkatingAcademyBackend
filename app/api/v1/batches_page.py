from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.batch import Batch
from app.models.student import Student
from app.models.session import Session as SessionModel
from app.models.attendance import Attendance
from app.models.batch_schedule_exception import BatchScheduleException

from app.schemas.batch import BatchPageResponse



router = APIRouter(
    prefix="/batches-page",
    tags=["Batches Page"],
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

def format_time(
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
# HELPER - NEXT TRAINING DATE
# =========================================================

def get_next_training_date(
    training_days: list[str],
    today: date,
) -> date:

    if not training_days:
        return today

    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    today_weekday = today.weekday()

    valid_weekdays = [
        weekday_map[str(day).strip().lower()]
        for day in training_days
        if str(day).strip().lower() in weekday_map
    ]

    if not valid_weekdays:
        return today

    # Check today first
    if today_weekday in valid_weekdays:
        return today

    # Find next training day
    for offset in range(1, 8):

        next_day = (
            today
            + timedelta(days=offset)
        )

        if next_day.weekday() in valid_weekdays:
            return next_day

    return today


# =========================================================
# GET BATCHES PAGE
# =========================================================

@router.get(
    "",
    response_model=BatchPageResponse,
)
def get_batches_page(
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
    # TOTAL BATCHES
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
    # NEW BATCHES THIS MONTH
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
    # ACTIVE STUDENTS
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
    # TODAY'S SESSIONS & SCHEDULED BATCHES
    # =====================================================

    today_weekday_name = today.strftime("%A").lower()

    active_batches_list = (
        db.query(Batch)
        .filter(Batch.is_active.is_(True))
        .all()
    )

    today_scheduled_batches = []
    for b in active_batches_list:
        days = {str(d).strip().lower() for d in (b.training_days or []) if d}
        is_comp = (
            db.query(BatchScheduleException)
            .filter(
                BatchScheduleException.batch_id == b.id,
                BatchScheduleException.compensation_date == today,
                BatchScheduleException.status == "APPROVED",
            )
            .first()
        ) is not None
        if (today_weekday_name in days) or is_comp:
            today_scheduled_batches.append(b)

    today_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_date == today
        )
        .all()
    )

    scheduled_sessions = max(len(today_scheduled_batches), len(today_sessions))

    completed_sessions = sum(
        1
        for session in today_sessions
        if session.status == "COMPLETED"
    )

    active_sessions = max(0, scheduled_sessions - completed_sessions)

    # =====================================================
    # TODAY'S EXPECTED STUDENTS (Total Active Students)
    # =====================================================

    total_expected = total_students

    # =====================================================
    # TODAY'S PRESENT STUDENTS
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
            func.lower(Attendance.status) == "present",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # ATTENDANCE %
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
    # BATCH LIST
    # =====================================================

    batches = (
        db.query(Batch)
        .filter(
            Batch.is_active.is_(True)
        )
        .order_by(
            Batch.id.desc()
        )
        .all()
    )

    batch_items = []

    for batch in batches:

        # =================================================
        # STUDENT COUNT
        # =================================================

        student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id == batch.id,
                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        # =================================================
        # TRAINING DAYS & SCHEDULE CHECK
        # =================================================

        batch_days = {
            str(d).strip().lower()
            for d in (batch.training_days or [])
            if d
        }

        is_compensation_today = (
            db.query(BatchScheduleException)
            .filter(
                BatchScheduleException.batch_id == batch.id,
                BatchScheduleException.compensation_date == today,
                BatchScheduleException.status == "APPROVED",
            )
            .first()
        ) is not None

        is_scheduled_today = (today_weekday_name in batch_days) or is_compensation_today

        next_training_date = get_next_training_date(
            batch.training_days,
            today,
        )

        # =================================================
        # TODAY'S SESSION FOR THIS BATCH (STRICTLY TODAY)
        # =================================================

        today_session = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id == batch.id,
                SessionModel.session_date == today,
            )
            .order_by(
                SessionModel.id.desc()
            )
            .first()
        )

        # =================================================
        # 3 STATUSES: live, completed, no_class
        # =================================================

        if today_session is not None and today_session.status == "COMPLETED":

            batch_status = "completed"

            present_count = (
                db.query(
                    func.count(
                        func.distinct(
                            Attendance.student_id
                        )
                    )
                )
                .filter(
                    Attendance.session_id
                    == today_session.id,

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

            attendance_value = (
                f"{present_count}/"
                f"{student_count}"
            )

            session_id_str = str(today_session.id)

            date_label = today.strftime("%d %b %Y")

        elif (today_session is not None and today_session.status == "LIVE") or is_scheduled_today:

            batch_status = "live"

            if today_session is not None:

                present_count = (
                    db.query(
                        func.count(
                            func.distinct(
                                Attendance.student_id
                            )
                        )
                    )
                    .filter(
                        Attendance.session_id
                        == today_session.id,

                        Attendance.status
                        == "Present",
                    )
                    .scalar()
                    or 0
                )

                attendance_value = (
                    f"{present_count}/"
                    f"{student_count}"
                )

                session_id_str = str(today_session.id)

            else:

                attendance_value = None

                session_id_str = None

            date_label = today.strftime("%d %b %Y")

        else:

            # Not scheduled today and no session created today
            batch_status = "no_class"

            attendance_value = None

            session_id_str = None

            date_label = next_training_date.strftime("%d %b %Y")

        # =================================================
        # TIME
        # =================================================

        time_label = format_time(
            batch.start_time,
            batch.end_time,
        )

        # =================================================
        # CATEGORY
        # =================================================

        category = get_time_of_day(
            batch.start_time
        )

        # =================================================
        # ADD BATCH
        # =================================================

        batch_items.append(
            {
                "id":
                    str(batch.id),

                "title":
                    batch.batch_name,

                "date":
                    date_label,

                "time":
                    time_label,

                "students_count":
                    student_count,

                "status":
                    batch_status,

                "category":
                    category,

                "attendance":
                    attendance_value,

                "session_id":
                    session_id_str,
            }
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "status": "success",

        "message":
            "Batches page data fetched successfully",

        "data": {

            # ==============================================
            # OVERVIEW
            # ==============================================

            "overview": {

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

                "students": {

                    "total":
                        total_students,
                },

                "todays_attendance": {

                    "present":
                        present_today,

                    "total_expected":
                        total_expected,

                    "percentage":
                        attendance_percentage,
                },
            },

            # ==============================================
            # BATCHES
            # ==============================================

            "batches":
                batch_items,
        },
    }