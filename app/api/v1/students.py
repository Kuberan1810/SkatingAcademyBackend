from calendar import monthrange
from datetime import date, timedelta


from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.batch import Batch
from app.models.student import Student

from app.schemas.student import (
    StudentCreate,
    StudentCreateResponse,
    StudentListResponse,
    StudentUpdate,
    StudentProfileResponse,

)
from app.schemas.student import (
    AllStudentsPageResponse,
)
from app.models.session import Session as SessionModel
from app.models.attendance import Attendance
from app.models.fee import FeePayment

from app.schemas.student import (
    BulkDeleteStudentsRequest,
)



router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


# =========================================================
# Helper
# =========================================================

def calculate_age(dob: date) -> int:
    today = date.today()

    age = today.year - dob.year

    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1

    return age


# =========================================================
# Create Student
# =========================================================

@router.post(
    "",
    response_model=StudentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    # Check batch exists and is active
    batch = (
        db.query(Batch)
        .filter(
            Batch.id == data.batch_id,
            Batch.is_active.is_(True),
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or inactive",
        )

    # Calculate age
    age = calculate_age(data.dob)

    if age < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student age must be at least 3 years",
        )

    # Create student
    student = Student(
        full_name=data.full_name,
        dob=data.dob,
        gender=data.gender,
        blood_group=data.blood_group,
        batch_id=data.batch_id,
        join_date=data.join_date,
        parent_name=data.parent_name,
        phone_number=data.phone_number,
        emergency_contact=data.emergency_contact,
        monthly_fee=data.monthly_fee,
        avatar_uri=data.avatar_uri,
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return {
        "status": "success",
        "message": "Student created successfully",
        "data": {
            "id": student.id,
            "full_name": student.full_name,
            "age": age,
            "gender": student.gender,
            "dob": student.dob,
            "blood_group": student.blood_group,
            "batch_id": student.batch_id,
            "batch_name": batch.batch_name,
            "join_date": student.join_date,
            "parent_name": student.parent_name,
            "phone_number": student.phone_number,
            "emergency_contact": student.emergency_contact,
            "monthly_fee": student.monthly_fee,
            "avatar_uri": student.avatar_uri,
            "is_active": student.is_active,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
        },
    }

# =========================================================
# Get All Students
# =========================================================

@router.get(
    "",
    response_model=StudentListResponse,
)
def get_students(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    students = (
        db.query(Student, Batch.batch_name)
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
        )
        .order_by(Student.id.desc())
        .all()
    )

    data = []

    for student, batch_name in students:
        data.append(
            {
                "id": student.id,
                "full_name": student.full_name,
                "age": calculate_age(student.dob),
                "gender": student.gender,
                "dob": student.dob,
                "blood_group": student.blood_group,
                "batch_id": student.batch_id,
                "batch_name": batch_name,
                "join_date": student.join_date,
                "parent_name": student.parent_name,
                "phone_number": student.phone_number,
                "emergency_contact": student.emergency_contact,
                "monthly_fee": student.monthly_fee,
                "avatar_uri": student.avatar_uri,
                "is_active": student.is_active,
                "created_at": student.created_at,
                "updated_at": student.updated_at,
            }
        )

    return {
        "status": "success",
        "message": "Students fetched successfully",
        "data": data,
    }



# =========================================================
# GET ALL STUDENTS PAGE
# =========================================================

@router.get(
    "/page",
    response_model=AllStudentsPageResponse,
)
def get_all_students_page(
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
    # 2. NEW STUDENTS THIS MONTH
    #
    # Based on join_date
    # =====================================================

    new_this_month = sum(
        1
        for student, batch in students
        if (
            student.join_date >= current_month_start
            and student.join_date < next_month_start
        )
    )

    # =====================================================
    # 3. GENDER OVERVIEW
    # =====================================================

    boys_count = sum(
        1
        for student, batch in students
        if student.gender == "Male"
    )

    girls_count = sum(
        1
        for student, batch in students
        if student.gender == "Female"
    )

    if total_students > 0:

        boys_percent = round(
            (boys_count / total_students) * 100,
            2,
        )

        girls_percent = round(
            (girls_count / total_students) * 100,
            2,
        )

    else:

        boys_percent = 0
        girls_percent = 0

    # =====================================================
    # 4. STUDENT LIST
    # =====================================================

    student_items = []

    pending_fees_count = 0

    # =====================================================
    # 5. LOOP THROUGH STUDENTS
    # =====================================================

    for student, batch in students:

        # =================================================
        # GET COMPLETED SESSIONS FOR THIS STUDENT'S BATCH
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
        # ATTENDED COUNT
        # =================================================

        if completed_session_ids:

            attended_count = (
                db.query(
                    func.count(Attendance.id)
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

        else:

            attended_count = 0

        # =================================================
        # ATTENDANCE PERCENTAGE
        # =================================================

        if conducted_count > 0:

            attendance_percentage = round(
                (
                    attended_count
                    / conducted_count
                ) * 100,
                2,
            )

        else:

            attendance_percentage = 0

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
        # LAST PAYMENT
        # =================================================

        last_payment = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id == student.id,
            )
            .order_by(
                FeePayment.payment_date.desc()
            )
            .first()
        )


        if last_payment is not None:

            last_payment_data = {
                "amount": int(
                    last_payment.net_payable
                ),

                "fee_month":
                    last_payment.fee_month,

                "fee_year":
                    last_payment.fee_year,

                "paid_date": (
                    last_payment.payment_date.strftime(
                        "%d %b %Y"
                    )
                    if last_payment.payment_date
                    else None
                ),
            }

        else:

            last_payment_data = None
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
                student.monthly_fee
                if (student.monthly_fee is not None and student.monthly_fee > 0)
                else (batch.monthly_fee or 0)
            )

            paid_date = None

            # ---------------------------------------------
            # DUE DATE
            # ---------------------------------------------

            due_day = 1

            due_date = date(
                current_year,
                current_month,
                due_day,
            )

            # ---------------------------------------------
            # PAYMENT STATUS
            # ---------------------------------------------

            if today > due_date:

                payment_status = "overdue"

            elif today == due_date:

                payment_status = "due_today"

            else:

                payment_status = "unpaid"

            # ---------------------------------------------
            # PENDING FEE COUNT
            # ---------------------------------------------

            pending_fees_count += 1

        # =================================================
        # ADD STUDENT
        # =================================================

        student_items.append(
            {
                "id":
                    str(student.id),

                "name":
                    student.full_name,

                "batch_name":
                    batch.batch_name,

                "joined_date":
                    student.join_date.strftime(
                        "%d %b %Y"
                    ),

                "location":
                    batch.location,

                "attendance_percent":
                    f"{attendance_percentage:g}%",

                "phone":
                    student.phone_number,

                "payment_status":
                    payment_status,

                "amount":
                    amount,

                "paid_date":
                    paid_date,

                "last_payment": last_payment_data,

                "attended_count":
                    attended_count,

                "conducted_count":
                    conducted_count,

                "avatar_uri":
                    student.avatar_uri,
            }
        )

    # =====================================================
    # 6. FINAL RESPONSE
    # =====================================================

    return {

        "status":
            "success",

        "message":
            "All students page data fetched successfully",

        "data": {

            # ==============================================
            # OVERVIEW
            # ==============================================

            "overview": {

                "total_students":
                    total_students,

                "new_this_month":
                    new_this_month,

                "boys_count":
                    boys_count,

                "boys_percent":
                    boys_percent,

                "girls_count":
                    girls_count,

                "girls_percent":
                    girls_percent,

                "pending_fees_count":
                    pending_fees_count,
            },

            # ==============================================
            # STUDENTS
            # ==============================================

            "students":
                student_items,
        },
    }




# =========================================================
# GET STUDENT PROFILE
# =========================================================

@router.get(
    "/{student_id}/profile",
    response_model=StudentProfileResponse,
)
def get_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    # =====================================================
    # 1. GET STUDENT + BATCH
    # =====================================================

    result = (
        db.query(Student, Batch)
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    student, batch = result

    today = date.today()

    current_month = today.month
    current_year = today.year

    # =====================================================
    # 2. CURRENT MONTH RANGE
    # =====================================================

    first_day_of_month = date(
        current_year,
        current_month,
        1,
    )

    last_day_number = monthrange(
        current_year,
        current_month,
    )[1]

    last_day_of_month = date(
        current_year,
        current_month,
        last_day_number,
    )

    # =====================================================
    # 3. BATCH TRAINING DAYS
    #
    # Batch stores:
    #
    # ["Monday", "Wednesday"]
    #
    # Example:
    #
    # ["Monday", "Tuesday", "Thursday", "Saturday"]
    # =====================================================

    training_days = batch.training_days or []

    training_days_set = {
        str(day).strip().lower()
        for day in training_days
    }

    # =====================================================
    # 4. GENERATE SCHEDULED TRAINING DATES
    #
    # Only:
    # - Batch training days
    # - Student joined date onwards
    # - Current month
    #
    # Future days are included in calendar,
    # but NOT counted in scheduled_days_count.
    # =====================================================

    calendar_dates = []

    scheduled_dates_until_today = []

    current_date = first_day_of_month

    while current_date <= last_day_of_month:

        day_name = (
            current_date
            .strftime("%A")
            .lower()
        )

        # Only batch training days
        if day_name in training_days_set:

            # Student should not have attendance
            # before joining the batch.
            if current_date >= student.join_date:

                calendar_dates.append(
                    current_date
                )

                if current_date <= today:

                    scheduled_dates_until_today.append(
                        current_date
                    )

        current_date += timedelta(days=1)

    scheduled_days_count = len(
        scheduled_dates_until_today
    )

    # =====================================================
    # 5. GET ALL COMPLETED SESSIONS
    #
    # Classes that ACTUALLY happened.
    # =====================================================

    completed_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.batch_id == batch.id,
            SessionModel.status == "COMPLETED",
            SessionModel.session_date >= student.join_date,
            SessionModel.session_date <= today,
        )
        .order_by(
            SessionModel.session_date.asc()
        )
        .all()
    )

    conducted_days_count = len(
        completed_sessions
    )

    completed_session_ids = [
        session.id
        for session in completed_sessions
    ]

    # =====================================================
    # 6. GET ATTENDANCE RECORDS
    # =====================================================

    attendance_records = []

    if completed_session_ids:

        attendance_records = (
            db.query(Attendance)
            .filter(
                Attendance.student_id == student.id,
                Attendance.session_id.in_(
                    completed_session_ids
                ),
            )
            .all()
        )

    # =====================================================
    # 7. ATTENDANCE BY SESSION
    # =====================================================

    attendance_by_session = {}

    for attendance in attendance_records:

        attendance_by_session[
            attendance.session_id
        ] = str(
            attendance.status
        ).lower()

    # =====================================================
    # 8. ATTENDED COUNT
    # =====================================================

    attended_count = sum(
        1
        for attendance in attendance_records
        if str(
            attendance.status
        ).lower() == "present"
    )

    # =====================================================
    # 9. ABSENT COUNT
    # =====================================================

    absent_count = max(
        conducted_days_count
        - attended_count,
        0,
    )

    # =====================================================
    # 10. ATTENDANCE PERCENTAGE
    # =====================================================

    if conducted_days_count > 0:

        attendance_percentage = round(
            (
                attended_count
                / conducted_days_count
            ) * 100,
            2,
        )

    else:

        attendance_percentage = 0

    attendance_percent_text = (
        f"{attendance_percentage:g}%"
    )

    # =====================================================
    # 11. MAP SESSION BY DATE
    # =====================================================

    session_by_date = {}

    for session in completed_sessions:

        session_by_date[
            session.session_date
        ] = session

    # =====================================================
    # 12. ATTENDANCE GRID
    #
    # IMPORTANT:
    #
    # Only batch training days are displayed.
    #
    # Example:
    #
    # Monday
    # Wednesday
    #
    # Tuesday will NOT appear.
    # =====================================================

    attendance_grid = []

    for training_date in calendar_dates:

        # -------------------------------------------------
        # FUTURE TRAINING DAY
        # -------------------------------------------------

        if training_date > today:

            grid_status = "none"

        # -------------------------------------------------
        # TODAY
        # -------------------------------------------------

        elif training_date == today:

            today_session = session_by_date.get(
                training_date
            )

            if today_session:

                attendance_status = (
                    attendance_by_session.get(
                        today_session.id
                    )
                )

                if attendance_status == "present":

                    grid_status = "present"

                elif attendance_status == "absent":

                    grid_status = "absent"

                else:

                    grid_status = "current"

            else:

                grid_status = "current"

        # -------------------------------------------------
        # PAST TRAINING DAY
        # -------------------------------------------------

        else:

            session = session_by_date.get(
                training_date
            )

            # Class actually happened
            if session:

                attendance_status = (
                    attendance_by_session.get(
                        session.id
                    )
                )

                if attendance_status == "present":

                    grid_status = "present"

                elif attendance_status == "absent":

                    grid_status = "absent"

                else:

                    grid_status = "none"

            # Training day but class was not conducted
            else:

                grid_status = "none"

        attendance_grid.append(
            {
                "day_name":
                    training_date.strftime("%a"),

                "day_number":
                    training_date.strftime("%d"),

                "full_date":
                    training_date.isoformat(),

                "status":
                    grid_status,
            }
        )

    # =====================================================
    # 13. CURRENT MONTH PAYMENT
    # =====================================================

    current_payment = (
        db.query(FeePayment)
        .filter(
            FeePayment.student_id == student.id,
            FeePayment.fee_month == current_month,
            FeePayment.fee_year == current_year,
        )
        .order_by(
            FeePayment.payment_date.desc()
        )
        .first()
    )

    # =====================================================
    # 14. LAST PAYMENT
    # =====================================================

    last_payment = (
        db.query(FeePayment)
        .filter(
            FeePayment.student_id == student.id,
        )
        .order_by(
            FeePayment.payment_date.desc()
        )
        .first()
    )

    # =====================================================
    # 15. MONTHLY FEE
    #
    # Student has monthly_fee in your model.
    # =====================================================

    monthly_fee = int(
        student.monthly_fee
    )

    # =====================================================
    # 16. PAYMENT DUE DATE
    # =====================================================

    due_day = 1

    due_date = date(
        current_year,
        current_month,
        due_day,
    )

    # =====================================================
    # 17. CURRENT PAYMENT STATUS
    # =====================================================

    if current_payment is not None:

        current_payment_status = "PAID"

        pending_amount = 0

        if current_payment.payment_date:

            current_status_subtext = (
                current_payment.payment_date.strftime(
                    "Paid on %d %b"
                )
            )

        else:

            current_status_subtext = "Paid"

        current_payment_details = (
            f"Paid by: "
            f"{current_payment.payment_method}"
        )

    else:

        pending_amount = monthly_fee

        if today > due_date:

            current_payment_status = "OVERDUE"

            current_status_subtext = (
                f"Due: "
                f"{due_date.strftime('%d %b %Y')}"
            )

            current_payment_details = "Overdue"

        elif today == due_date:

            current_payment_status = "PENDING"

            current_status_subtext = (
                f"Due: "
                f"{due_date.strftime('%d %b %Y')}"
            )

            current_payment_details = "Pending"

        else:

            current_payment_status = "PENDING"

            current_status_subtext = (
                f"Due: "
                f"{due_date.strftime('%d %b %Y')}"
            )

            current_payment_details = "Pending"

    # =====================================================
    # 18. LAST PAYMENT DATA
    # =====================================================

    if last_payment is not None:

        last_paid_amount = int(
            last_payment.net_payable
        )

        if last_payment.payment_date:

            last_paid_date = (
                last_payment.payment_date.strftime(
                    "Paid on %d %b %Y"
                )
            )

        else:

            last_paid_date = None

    else:

        last_paid_amount = None
        last_paid_date = None

    # =====================================================
    # 19. NEXT PAYMENT DATE
    # =====================================================

    if current_payment is not None:

        # December → January
        if current_month == 12:

            next_payment_due_date = date(
                current_year + 1,
                1,
                due_day,
            )

        else:

            next_payment_due_date = date(
                current_year,
                current_month + 1,
                due_day,
            )

    else:

        next_payment_due_date = due_date

    # =====================================================
    # 20. DAYS LEFT
    # =====================================================

    days_difference = (
        next_payment_due_date
        - today
    ).days

    if days_difference > 0:

        days_left_text = (
            f"{days_difference} Days Left"
        )

    elif days_difference == 0:

        days_left_text = "Due Today"

    else:

        days_left_text = "Overdue"

    # =====================================================
    # 21. TRANSACTION HISTORY
    # =====================================================

    payments = (
        db.query(FeePayment)
        .filter(
            FeePayment.student_id == student.id,
        )
        .order_by(
            FeePayment.payment_date.desc()
        )
        .limit(12)
        .all()
    )

    transactions = []

    for payment in payments:

        # -------------------------------------------------
        # Month name
        # -------------------------------------------------

        try:

            month_name = date(
                payment.fee_year,
                payment.fee_month,
                1,
            ).strftime("%B")

        except Exception:

            month_name = str(
                payment.fee_month
            )

        # -------------------------------------------------
        # Payment date
        # -------------------------------------------------

        if payment.payment_date:

            payment_date_text = (
                payment.payment_date.strftime(
                    "%d %b %Y"
                )
            )

        else:

            payment_date_text = ""

        # -------------------------------------------------
        # Payment method
        # -------------------------------------------------

        payment_method = str(
            payment.payment_method
        )

        transactions.append(
            {
                "id":
                    str(payment.id),

                "title":
                    f"{month_name} Fee",

                "date_and_method":
                    (
                        f"{payment_date_text} • "
                        f"{payment_method}"
                    ),

                "amount":
                    int(
                        payment.net_payable
                    ),

                "status":
                    "PAID",
            }
        )

    # =====================================================
    # 22. LOCATION
    # =====================================================

    location = (
        batch.location
        if batch.location
        else ""
    )

    # =====================================================
    # 23. FINAL RESPONSE
    # =====================================================

    return {

        "status":
            "success",

        "message":
            "Student profile fetched successfully",

        "data": {

            # =================================================
            # BASIC PROFILE
            # =================================================

            "id":
                str(student.id),

            "name":
                student.full_name,

            "avatar_uri":
                student.avatar_uri,

            "joined_date":
                student.join_date.strftime(
                    "%d %b %Y"
                ),

            "location":
                location,

            "attendance_percent":
                attendance_percent_text,

            # =================================================
            # OVERVIEW TAB
            # =================================================

            "parent_info": {

                "parent_name":
                    student.parent_name,

                "phone":
                    student.phone_number,

                "emergency":
                    student.emergency_contact,
            },

            "personal_info": {

                "gender":
                    student.gender,

                "dob":
                    student.dob,

                "blood_group":
                    student.blood_group,
            },

            "fee_info": {

                "monthly_fee":
                    monthly_fee,

                "pending":
                    pending_amount,

                "status":
                    current_payment_status,
            },

            # =================================================
            # ATTENDANCE TAB
            # =================================================

            "attendance_stats": {

                "present":
                    attended_count,

                "absent":
                    absent_count,

                "attendance_percent":
                    attendance_percent_text,

                "scheduled_days_count":
                    scheduled_days_count,

                "conducted_days_count":
                    conducted_days_count,
            },

            "attendance_grid":
                attendance_grid,

            # =================================================
            # PAYMENTS TAB
            # =================================================

            "balance_summary": {

                "last_paid_amount":
                    last_paid_amount,

                "last_paid_date":
                    last_paid_date,

                "next_payment_amount":
                    monthly_fee,

                "next_payment_due_date":
                    next_payment_due_date.strftime(
                        "%d %b %Y"
                    ),

                "days_left_text":
                    days_left_text,
            },

            "current_month_fee": {

                "month_year":
                    today.strftime(
                        "%B %Y"
                    ).upper(),

                "amount":
                    monthly_fee,

                "status":
                    current_payment_status.lower(),

                "status_subtext":
                    current_status_subtext,

                "payment_details":
                    current_payment_details,
            },

            "transactions":
                transactions,
        },
    }





# =========================================================
# Get Single Student
# =========================================================

@router.get(
    "/{student_id}",
    response_model=StudentCreateResponse,
)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = (
        db.query(Student, Batch.batch_name)
        .join(
            Batch,
            Student.batch_id == Batch.id,
        )
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    student, batch_name = result

    return {
        "status": "success",
        "message": "Student fetched successfully",
        "data": {
            "id": student.id,
            "full_name": student.full_name,
            "age": calculate_age(student.dob),
            "gender": student.gender,
            "dob": student.dob,
            "blood_group": student.blood_group,
            "batch_id": student.batch_id,
            "batch_name": batch_name,
            "join_date": student.join_date,
            "parent_name": student.parent_name,
            "phone_number": student.phone_number,
            "emergency_contact": student.emergency_contact,
            "monthly_fee": student.monthly_fee,
            "avatar_uri": student.avatar_uri,
            "is_active": student.is_active,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
        },
    }


# =========================================================
# Update Student
# =========================================================

@router.put(
    "/{student_id}",
    response_model=StudentCreateResponse,
)
def update_student(
    student_id: int,
    data: StudentUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    # Validate batch if changing batch
    if "batch_id" in update_data:
        batch = (
            db.query(Batch)
            .filter(
                Batch.id == update_data["batch_id"],
                Batch.is_active.is_(True),
            )
            .first()
        )

        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found or inactive",
            )

    # Update fields
    for field, value in update_data.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)

    batch = (
        db.query(Batch)
        .filter(Batch.id == student.batch_id)
        .first()
    )

    return {
        "status": "success",
        "message": "Student updated successfully",
        "data": {
            "id": student.id,
            "full_name": student.full_name,
            "age": calculate_age(student.dob),
            "gender": student.gender,
            "dob": student.dob,
            "blood_group": student.blood_group,
            "batch_id": student.batch_id,
            "batch_name": batch.batch_name if batch else "",
            "join_date": student.join_date,
            "parent_name": student.parent_name,
            "phone_number": student.phone_number,
            "emergency_contact": student.emergency_contact,
            "monthly_fee": student.monthly_fee,
            "avatar_uri": student.avatar_uri,
            "is_active": student.is_active,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
        },
    }


# =========================================================
# Soft Delete Student
# =========================================================


@router.delete(
    "/{student_id}",
)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    student.is_active = False

    db.commit()

    return {
        "status": "success",
        "message": "Student deleted successfully",
    }




@router.post(
    "/bulk-delete",
)
def bulk_delete_students(
    request: BulkDeleteStudentsRequest,

    db: Session = Depends(
        get_db
    ),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):
    # =====================================================
    # CLEAN / UNIQUE IDS
    # =====================================================

    student_ids = list(
        set(
            request.student_ids
        )
    )

    if not student_ids:
        raise HTTPException(
            status_code=400,
            detail="No student IDs provided",
        )

    # =====================================================
    # FETCH STUDENTS
    # =====================================================

    students = (
        db.query(Student)
        .filter(
            Student.id.in_(
                student_ids
            ),
            Student.is_active.is_(True),
        )
        .all()
    )

    found_ids = {
        student.id
        for student in students
    }

    not_found_ids = [
        student_id
        for student_id in student_ids
        if student_id not in found_ids
    ]

    # =====================================================
    # DELETE
    # =====================================================

    deleted = []

    failed = []

    for student in students:

        try:
            # ---------------------------------------------
            # IMPORTANT:
            # Soft delete is safer than hard delete.
            # ---------------------------------------------

            student.is_active = False

            deleted.append(
                {
                    "id": student.id,
                    "full_name": student.full_name,
                    "status": "deleted",
                }
            )

        except Exception as exc:

            failed.append(
                {
                    "id": student.id,
                    "full_name": student.full_name,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    # =====================================================
    # COMMIT
    # =====================================================

    try:

        db.commit()

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Bulk student delete failed: "
                f"{str(exc)}"
            ),
        ) from exc

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "status": "success",

        "message":
            "Bulk student deletion completed",

        "data": {
            "requested_count":
                len(student_ids),

            "deleted_count":
                len(deleted),

            "failed_count":
                len(failed),

            "not_found_count":
                len(not_found_ids),

            "deleted":
                deleted,

            "not_found":
                not_found_ids,

            "failed":
                failed,
        },
    }