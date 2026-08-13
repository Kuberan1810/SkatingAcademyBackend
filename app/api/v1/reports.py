from app.api.v1.students import calculate_age
from calendar import month_name
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.student import Student
from app.models.batch import Batch
from app.models.session import Session as SessionModel
from app.models.attendance import Attendance
from app.models.fee import FeePayment


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


# =========================================================
# HELPERS
# =========================================================

def get_month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def get_next_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)

    return date(
        year,
        month + 1,
        1,
    )


def previous_month(year: int, month: int):
    if month == 1:
        return year - 1, 12

    return year, month - 1


def last_n_months(
    year: int,
    month: int,
    count: int,
):
    months = []

    current_year = year
    current_month = month

    for _ in range(count):

        months.append(
            (
                current_year,
                current_month,
            )
        )

        current_year, current_month = (
            previous_month(
                current_year,
                current_month
            )
        )

    months.reverse()

    return months


# =========================================================
# 1. REPORTS PAGE
# =========================================================

@router.get("/page")
def get_reports_page(
    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):
    today = date.today()

    current_year = today.year
    current_month = today.month

    current_month_start = get_month_start(
        current_year,
        current_month,
    )

    next_month_start = get_next_month(
        current_year,
        current_month,
    )

    # =====================================================
    # STUDENTS
    # =====================================================

    total_students = (
        db.query(func.count(Student.id))
        .filter(
            Student.is_active.is_(True)
        )
        .scalar()
        or 0
    )

    # =====================================================
    # COMPLETED SESSIONS THIS MONTH
    # =====================================================

    completed_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.status == "COMPLETED",

            SessionModel.session_date
            >= current_month_start,

            SessionModel.session_date
            < next_month_start,
        )
        .all()
    )

    session_ids = [
        session.id
        for session in completed_sessions
    ]

    # =====================================================
    # ATTENDANCE
    # =====================================================

    present_count = 0

    if session_ids:

        present_count = (
            db.query(
                func.count(Attendance.id)
            )
            .filter(
                Attendance.session_id.in_(
                    session_ids
                ),

                Attendance.status
                == "Present",
            )
            .scalar()
            or 0
        )

    # Expected attendance:

    expected_count = 0

    for session in completed_sessions:

        batch_student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id
                == session.batch_id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        expected_count += (
            batch_student_count
        )

    if expected_count > 0:

        attendance_percentage = round(
            (
                present_count
                / expected_count
            )
            * 100,
            2,
        )

    else:

        attendance_percentage = 0

    # =====================================================
    # THIS MONTH REVENUE
    # =====================================================

    this_month_revenue = (
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
            >= datetime.combine(
                current_month_start,
                time.min,
            ),

            FeePayment.payment_date
            < datetime.combine(
                next_month_start,
                time.min,
            ),
        )
        .scalar()
        or 0
    )

    this_month_revenue = int(
        this_month_revenue
    )

    # =====================================================
    # ALL TIME REVENUE
    # =====================================================

    all_time_revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    FeePayment.net_payable
                ),
                0,
            )
        )
        .scalar()
        or 0
    )

    all_time_revenue = int(
        all_time_revenue
    )

    # =====================================================
    # PREVIOUS MONTH REVENUE
    # =====================================================

    previous_year, previous_month_number = (
        previous_month(
            current_year,
            current_month,
        )
    )

    previous_month_start = get_month_start(
        previous_year,
        previous_month_number,
    )

    previous_month_end = get_next_month(
        previous_year,
        previous_month_number,
    )

    previous_month_revenue = (
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
            >= datetime.combine(
                previous_month_start,
                time.min,
            ),

            FeePayment.payment_date
            < datetime.combine(
                previous_month_end,
                time.min,
            ),
        )
        .scalar()
        or 0
    )

    previous_month_revenue = int(
        previous_month_revenue
    )

    # =====================================================
    # REVENUE CHANGE
    # =====================================================

    if previous_month_revenue > 0:

        revenue_change = round(
            (
                (
                    this_month_revenue
                    - previous_month_revenue
                )
                / previous_month_revenue
            )
            * 100,
            2,
        )

    elif this_month_revenue > 0:

        revenue_change = 100

    else:

        revenue_change = 0

    # =====================================================
    # LAST 6 MONTHS REVENUE
    # =====================================================

    revenue_months = []

    six_month_period = last_n_months(
        current_year,
        current_month,
        6,
    )

    for (
        year,
        month,
    ) in six_month_period:

        month_start = get_month_start(
            year,
            month,
        )

        month_end = get_next_month(
            year,
            month,
        )

        amount = (
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
                >= datetime.combine(
                    month_start,
                    time.min,
                ),

                FeePayment.payment_date
                < datetime.combine(
                    month_end,
                    time.min,
                ),
            )
            .scalar()
            or 0
        )

        revenue_months.append(
            {
                "month": month,

                "month_name":
                    month_name[month],

                "year": year,

                "amount":
                    int(amount),
            }
        )

    # =====================================================
    # PENDING FEES
    # =====================================================

    active_students = (
        db.query(
            Student,
            Batch,
        )
        .join(
            Batch,
            Student.batch_id
            == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
        .all()
    )

    paid_student_ids = {
        payment.student_id
        for payment in (
            db.query(FeePayment)
            .filter(
                FeePayment.fee_month
                == current_month,

                FeePayment.fee_year
                == current_year,
            )
            .all()
        )
    }

    pending_students = 0
    pending_amount = 0

    for student, batch in active_students:

        if student.id not in paid_student_ids:

            pending_students += 1

            pending_amount += int(
                batch.monthly_fee or 0
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
    # RESPONSE
    # =====================================================

    return {
        "status": "success",

        "message":
            "Reports data fetched successfully",

        "data": {

            # =============================================
            # OVERVIEW
            # =============================================

            "overview": {

                "students": {
                    "total":
                        total_students,
                },

                "attendance": {
                    "percentage":
                        attendance_percentage,

                    "present":
                        present_count,

                    "total_expected":
                        expected_count,
                },

                "revenue": {
                    "this_month":
                        this_month_revenue,

                    "all_time":
                        all_time_revenue,

                    "change_percentage":
                        revenue_change,
                },

                "pending_fees": {
                    "amount":
                        pending_amount,

                    "students":
                        pending_students,
                },

                "batches": {
                    "total":
                        total_batches,
                },
            },

            # =============================================
            # REVENUE TREND
            # =============================================

            "revenue_trend": {

                "period":
                    "last_6_months",

                "months":
                    revenue_months,

                "current_month": {
                    "amount":
                        this_month_revenue,
                },

                "previous_month": {
                    "amount":
                        previous_month_revenue,
                },

                "change_percentage":
                    revenue_change,
            },

            # =============================================
            # REPORT CATEGORIES
            # =============================================

            "report_categories": [

                {
                    "type":
                        "attendance",

                    "title":
                        "Attendance Report",

                    "description":
                        "Daily · Weekly · Monthly · Batch-wise",
                },

                {
                    "type":
                        "revenue",

                    "title":
                        "Revenue Report",

                    "description":
                        "Collected · Pending · Growth",
                },

                {
                    "type":
                        "students",

                    "title":
                        "Student Report",

                    "description":
                        "New admissions · Inactive students",
                },

                {
                    "type":
                        "batches",

                    "title":
                        "Batch Report",

                    "description":
                        "Batch strength · Attendance",
                },
            ],
        },
    }


# =========================================================
# 2. ATTENDANCE REPORT
# =========================================================

@router.get("/attendance")
def get_attendance_report(
    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
        default=None
    ),

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    today = date.today()

    start_date = (
        from_date
        or today.replace(day=1)
    )

    end_date = (
        to_date
        or today
    )

    if start_date > end_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "from_date cannot be "
                "greater than to_date"
            ),
        )

    # =====================================================
    # SESSIONS
    # =====================================================

    session_query = (
        db.query(SessionModel)
        .filter(
            SessionModel.status
            == "COMPLETED",

            SessionModel.session_date
            >= start_date,

            SessionModel.session_date
            <= end_date,
        )
    )

    if batch_id:

        session_query = session_query.filter(
            SessionModel.batch_id
            == batch_id
        )

    sessions = (
        session_query
        .order_by(
            SessionModel.session_date.asc()
        )
        .all()
    )

    session_ids = [
        session.id
        for session in sessions
    ]

    # =====================================================
    # TOTAL PRESENT
    # =====================================================

    present = 0

    if session_ids:

        present = (
            db.query(
                func.count(Attendance.id)
            )
            .filter(
                Attendance.session_id.in_(
                    session_ids
                ),

                Attendance.status
                == "Present",
            )
            .scalar()
            or 0
        )

    # =====================================================
    # DAILY
    # =====================================================

    daily = []

    for session in sessions:

        student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id
                == session.batch_id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        session_present = (
            db.query(
                func.count(Attendance.id)
            )
            .filter(
                Attendance.session_id
                == session.id,

                Attendance.status
                == "Present",
            )
            .scalar()
            or 0
        )

        percentage = (
            round(
                (
                    session_present
                    / student_count
                )
                * 100,
                2,
            )
            if student_count > 0
            else 0
        )

        daily.append(
            {
                "session_id":
                    str(session.id),

                "date":
                    session.session_date.isoformat(),

                "present":
                    session_present,

                "expected":
                    student_count,

                "absent":
                    max(
                        student_count
                        - session_present,
                        0,
                    ),

                "percentage":
                    percentage,
            }
        )

    expected = sum(
        item["expected"]
        for item in daily
    )

    absent = max(
        expected - present,
        0,
    )

    percentage = (
        round(
            (present / expected) * 100,
            2,
        )
        if expected > 0
        else 0
    )

    # =====================================================
    # BATCH WISE
    # =====================================================

    batch_ids = {
        session.batch_id
        for session in sessions
    }

    batch_wise = []

    for current_batch_id in batch_ids:

        batch = (
            db.query(Batch)
            .filter(
                Batch.id
                == current_batch_id
            )
            .first()
        )

        if not batch:
            continue

        batch_sessions = [
            session
            for session in sessions
            if session.batch_id
            == current_batch_id
        ]

        batch_present = 0
        batch_expected = 0

        for session in batch_sessions:

            students_count = (
                db.query(
                    func.count(Student.id)
                )
                .filter(
                    Student.batch_id
                    == current_batch_id,

                    Student.is_active.is_(True),
                )
                .scalar()
                or 0
            )

            batch_expected += (
                students_count
            )

            batch_present += (
                db.query(
                    func.count(Attendance.id)
                )
                .filter(
                    Attendance.session_id
                    == session.id,

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

        batch_percentage = (
            round(
                (
                    batch_present
                    / batch_expected
                )
                * 100,
                2,
            )
            if batch_expected > 0
            else 0
        )

        student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id
                == current_batch_id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        batch_wise.append(
            {
                "batch_id":
                    current_batch_id,

                "batch_name":
                    batch.batch_name,

                "students":
                    student_count,

                "present":
                    batch_present,

                "absent":
                    max(
                        batch_expected
                        - batch_present,
                        0,
                    ),

                "percentage":
                    batch_percentage,
            }
        )

    return {
        "status": "success",

        "message":
            "Attendance report fetched successfully",

        "data": {

            "filters": {
                "from_date":
                    start_date.isoformat(),

                "to_date":
                    end_date.isoformat(),

                "batch_id":
                    batch_id,
            },

            "summary": {
                "present":
                    present,

                "absent":
                    absent,

                "total_expected":
                    expected,

                "attendance_percentage":
                    percentage,
            },

            "daily":
                daily,

            "batch_wise":
                batch_wise,
        },
    }


# =========================================================
# 3. REVENUE REPORT
# =========================================================

@router.get("/revenue")
def get_revenue_report(
    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
        default=None
    ),

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    today = date.today()

    start_date = (
        from_date
        or today.replace(day=1)
    )

    end_date = (
        to_date
        or today
    )

    if start_date > end_date:

        raise HTTPException(
            status_code=400,
            detail="Invalid date range",
        )

    query = (
        db.query(
            FeePayment,
            Student,
            Batch,
        )
        .join(
            Student,
            FeePayment.student_id
            == Student.id,
        )
        .join(
            Batch,
            Student.batch_id
            == Batch.id,
        )
        .filter(
            FeePayment.payment_date
            >= datetime.combine(
                start_date,
                time.min,
            ),

            FeePayment.payment_date
            < datetime.combine(
                end_date
                + timedelta(days=1),
                time.min,
            ),

            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
    )

    if batch_id:

        query = query.filter(
            Student.batch_id
            == batch_id
        )

    payments = (
        query
        .order_by(
            FeePayment.payment_date.desc()
        )
        .all()
    )

    total_collected = sum(
        int(
            payment.net_payable
            or 0
        )
        for payment, student, batch
        in payments
    )

    # =====================================================
    # PAYMENT METHODS
    # =====================================================

    payment_methods = {
        "cash": 0,
        "upi": 0,
        "card": 0,
        "other": 0,
    }

    for payment, student, batch in payments:

        amount = int(
            payment.net_payable
            or 0
        )

        method = str(
            payment.payment_method
        ).upper()

        if method == "CASH":

            payment_methods[
                "cash"
            ] += amount

        elif method == "UPI":

            payment_methods[
                "upi"
            ] += amount

        elif method == "CARD":

            payment_methods[
                "card"
            ] += amount

        else:

            payment_methods[
                "other"
            ] += amount

    # =====================================================
    # MONTHLY
    # =====================================================

    monthly = []

    periods = last_n_months(
        today.year,
        today.month,
        6,
    )

    for year, month in periods:

        month_start = get_month_start(
            year,
            month,
        )

        month_end = get_next_month(
            year,
            month,
        )

        month_query = (
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
                >= datetime.combine(
                    month_start,
                    time.min,
                ),

                FeePayment.payment_date
                < datetime.combine(
                    month_end,
                    time.min,
                ),
            )
        )

        if batch_id:

            month_query = (
                month_query
                .join(
                    Student,
                    FeePayment.student_id
                    == Student.id,
                )
                .filter(
                    Student.batch_id
                    == batch_id
                )
            )

        amount = (
            month_query
            .scalar()
            or 0
        )

        monthly.append(
            {
                "month":
                    month,

                "month_name":
                    month_name[month],

                "year":
                    year,

                "amount":
                    int(amount),
            }
        )

    # =====================================================
    # PENDING
    # =====================================================

    active_students = (
        db.query(
            Student,
            Batch,
        )
        .join(
            Batch,
            Student.batch_id
            == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
        .all()
    )

    paid_ids = {
        payment.student_id
        for payment in (
            db.query(FeePayment)
            .filter(
                FeePayment.fee_month
                == today.month,

                FeePayment.fee_year
                == today.year,
            )
            .all()
        )
    }

    pending_amount = 0

    for student, batch in active_students:

        if student.id not in paid_ids:

            if (
                batch_id is None
                or student.batch_id
                == batch_id
            ):

                pending_amount += int(
                    batch.monthly_fee
                    or 0
                )

    return {
        "status": "success",

        "message":
            "Revenue report fetched successfully",

        "data": {

            "filters": {
                "from_date":
                    start_date.isoformat(),

                "to_date":
                    end_date.isoformat(),

                "batch_id":
                    batch_id,
            },

            "summary": {
                "total_collected":
                    total_collected,

                "pending_amount":
                    pending_amount,

                "total_transactions":
                    len(payments),
            },

            "payment_methods":
                payment_methods,

            "monthly":
                monthly,

            "transactions": [
                {
                    "payment_id":
                        str(payment.id),

                    "student_id":
                        str(student.id),

                    "student_name":
                        student.full_name,

                    "batch_name":
                        batch.batch_name,

                    "amount":
                        int(
                            payment.net_payable
                            or 0
                        ),

                    "payment_method":
                        str(
                            payment.payment_method
                        ),

                    "fee_month":
                        payment.fee_month,

                    "fee_year":
                        payment.fee_year,

                    "payment_date":
                        (
                            payment.payment_date.isoformat()
                            if payment.payment_date
                            else None
                        ),
                }

                for payment, student, batch
                in payments
            ],
        },
    }


# =========================================================
# STUDENT REPORT
# =========================================================

@router.get("/students")
def get_student_report(
    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    today = date.today()

    current_month = today.month
    current_year = today.year

    month_start = today.replace(day=1)

    next_month_start = get_next_month(
        current_year,
        current_month,
    )

    # =====================================================
    # 1. GET ALL STUDENTS
    # =====================================================

    students = (
        db.query(Student, Batch)
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .order_by(
            Student.id.desc()
        )
        .all()
    )

    # =====================================================
    # 2. SUMMARY
    # =====================================================

    total_students = len(students)

    active_students = sum(
        1
        for student, batch in students
        if student.is_active
    )

    inactive_students = sum(
        1
        for student, batch in students
        if not student.is_active
    )

    new_this_month = sum(
        1
        for student, batch in students
        if (
            student.join_date
            and student.join_date >= month_start
            and student.join_date < next_month_start
        )
    )

    # =====================================================
    # 3. GENDER
    # =====================================================

    male_count = sum(
        1
        for student, batch in students
        if (
            student.is_active
            and student.gender == "Male"
        )
    )

    female_count = sum(
        1
        for student, batch in students
        if (
            student.is_active
            and student.gender == "Female"
        )
    )

    other_count = max(
        active_students
        - male_count
        - female_count,
        0,
    )

    # =====================================================
    # 4. STUDENT LIST
    # =====================================================

    student_list = []

    for student, batch in students:

        # =================================================
        # CLASSES CONDUCTED
        #
        # Only completed classes after student joined.
        # =================================================

        completed_sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id
                == student.batch_id,

                SessionModel.status
                == "COMPLETED",

                SessionModel.session_date
                <= today,
            )
        )

        if student.join_date:

            completed_sessions = (
                completed_sessions.filter(
                    SessionModel.session_date
                    >= student.join_date
                )
            )

        completed_sessions = (
            completed_sessions
            .order_by(
                SessionModel.session_date.asc()
            )
            .all()
        )

        conducted_count = len(
            completed_sessions
        )

        completed_session_ids = [
            session.id
            for session in completed_sessions
        ]

        # =================================================
        # CLASSES ATTENDED
        # =================================================

        attended_count = 0

        if completed_session_ids:

            attended_count = (
                db.query(
                    func.count(
                        Attendance.id
                    )
                )
                .filter(
                    Attendance.student_id
                    == student.id,

                    Attendance.session_id.in_(
                        completed_session_ids
                    ),

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

        # =================================================
        # CLASSES ABSENT
        # =================================================

        absent_count = max(
            conducted_count
            - attended_count,
            0,
        )

        # =================================================
        # ATTENDANCE PERCENTAGE
        # =================================================

        if conducted_count > 0:

            attendance_percentage = round(
                (
                    attended_count
                    / conducted_count
                )
                * 100,
                2,
            )

        else:

            attendance_percentage = 0

        # =================================================
        # CURRENT MONTH PAYMENT
        # =================================================

        current_payment = (
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
        # CURRENT MONTH FEE STATUS
        # =================================================

        monthly_fee = int(
            student.monthly_fee
            or batch.monthly_fee
            or 0
        )

        if current_payment is not None:

            current_payment_status = "paid"

            current_paid_amount = int(
                current_payment.net_payable
                or 0
            )

            current_paid_date = (
                current_payment.payment_date.strftime(
                    "%d %b %Y"
                )
                if current_payment.payment_date
                else None
            )

            current_payment_method = (
                str(
                    current_payment.payment_method
                )
                if current_payment.payment_method
                else None
            )

        else:

            current_paid_amount = 0

            current_paid_date = None

            current_payment_method = None

            # ---------------------------------------------
            # DUE DATE
            # ---------------------------------------------

            due_day = min(
                student.join_date.day
                if student.join_date
                else 1,
                28,
            )

            due_date = date(
                current_year,
                current_month,
                due_day,
            )

            # ---------------------------------------------
            # STATUS
            # ---------------------------------------------

            if today > due_date:

                current_payment_status = "overdue"

            elif today == due_date:

                current_payment_status = "due_today"

            else:

                current_payment_status = "unpaid"

        # =================================================
        # PAYMENT HISTORY
        # =================================================

        payments = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id
                == student.id
            )
            .order_by(
                FeePayment.payment_date.desc()
            )
            .all()
        )

        payment_history = []

        total_paid = 0

        for payment in payments:

            amount = int(
                payment.net_payable
                or 0
            )

            total_paid += amount

            payment_history.append(
                {
                    "payment_id":
                        str(payment.id),

                    "fee_month":
                        payment.fee_month,

                    "fee_year":
                        payment.fee_year,

                    "amount":
                        amount,

                    "payment_method":
                        (
                            str(
                                payment.payment_method
                            )
                            if payment.payment_method
                            else None
                        ),

                    "payment_date":
                        (
                            payment.payment_date.strftime(
                                "%d %b %Y %I:%M %p"
                            )
                            if payment.payment_date
                            else None
                        ),

                    "status":
                        "paid",
                }
            )

        # =================================================
        # STUDENT DATA
        # =================================================

        student_list.append(
            {
                # =========================================
                # BASIC INFORMATION
                # =========================================

                "id":
                    student.id,

                "full_name":
                    student.full_name,

                "gender":
                    student.gender,

                "dob":
                    student.dob,

                "age":
                    calculate_age(
                        student.dob
                    ),

                "blood_group":
                    student.blood_group,

                "avatar_uri":
                    student.avatar_uri,

                # =========================================
                # BATCH INFORMATION
                # =========================================

                "batch": {
                    "id":
                        batch.id,

                    "name":
                        batch.batch_name,

                    "location":
                        batch.location,

                    "level":
                        batch.level,

                    "class_type":
                        batch.class_type,
                },

                # =========================================
                # JOIN / CONTACT
                # =========================================

                "join_date":
                    student.join_date,

                "parent_name":
                    student.parent_name,

                "phone_number":
                    student.phone_number,

                "emergency_contact":
                    student.emergency_contact,

                "is_active":
                    student.is_active,

                # =========================================
                # ATTENDANCE
                # =========================================

                "attendance": {
                    "classes_conducted":
                        conducted_count,

                    "classes_attended":
                        attended_count,

                    "classes_absent":
                        absent_count,

                    "attendance_percentage":
                        attendance_percentage,
                },

                # =========================================
                # CURRENT FEE
                # =========================================

                "current_fee": {
                    "month":
                        current_month,

                    "year":
                        current_year,

                    "monthly_fee":
                        monthly_fee,

                    "status":
                        current_payment_status,

                    "paid_amount":
                        current_paid_amount,

                    "paid_date":
                        current_paid_date,

                    "payment_method":
                        current_payment_method,

                    "pending_amount":
                        (
                            0
                            if current_payment
                            else monthly_fee
                        ),
                },

                # =========================================
                # PAYMENT SUMMARY
                # =========================================

                "payment_summary": {
                    "total_payments":
                        len(payments),

                    "total_paid":
                        total_paid,

                    "payment_history":
                        payment_history,
                },
            }
        )

    # =====================================================
    # 5. RESPONSE
    # =====================================================

    return {
        "status": "success",

        "message":
            "Student report fetched successfully",

        "data": {

            # =============================================
            # SUMMARY
            # =============================================

            "summary": {

                "total_students":
                    total_students,

                "active_students":
                    active_students,

                "inactive_students":
                    inactive_students,

                "new_this_month":
                    new_this_month,
            },

            # =============================================
            # GENDER
            # =============================================

            "gender": {

                "male":
                    male_count,

                "female":
                    female_count,

                "other":
                    other_count,
            },

            # =============================================
            # STUDENTS
            # =============================================

            "students":
                student_list,
        },
    }

# =========================================================
# 5. BATCH REPORT
# =========================================================

@router.get("/batches")
def get_batch_report(
    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    today = date.today()

    batches = (
        db.query(Batch)
        .filter(
            Batch.is_active.is_(True)
        )
        .order_by(
            Batch.batch_name.asc()
        )
        .all()
    )

    batch_data = []

    total_students = 0

    for batch in batches:

        student_count = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id
                == batch.id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        total_students += (
            student_count
        )

        # -------------------------------------------------
        # COMPLETED SESSIONS
        # -------------------------------------------------

        sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id
                == batch.id,

                SessionModel.status
                == "COMPLETED",

                SessionModel.session_date
                <= today,
            )
            .all()
        )

        session_ids = [
            session.id
            for session in sessions
        ]

        present_count = 0

        if session_ids:

            present_count = (
                db.query(
                    func.count(
                        Attendance.id
                    )
                )
                .filter(
                    Attendance.session_id.in_(
                        session_ids
                    ),

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

        expected_count = (
            student_count
            * len(sessions)
        )

        attendance_percentage = (
            round(
                (
                    present_count
                    / expected_count
                )
                * 100,
                2,
            )
            if expected_count > 0
            else 0
        )

        batch_data.append(
            {
                "batch_id":
                    batch.id,

                "batch_name":
                    batch.batch_name,

                "location":
                    batch.location,

                "student_count":
                    student_count,

                "completed_sessions":
                    len(sessions),

                "attendance_percentage":
                    attendance_percentage,
            }
        )

    return {
        "status": "success",

        "message":
            "Batch report fetched successfully",

        "data": {

            "summary": {
                "total_batches":
                    len(batches),

                "active_batches":
                    len(batches),

                "total_students":
                    total_students,
            },

            "batches":
                batch_data,
        },
    }