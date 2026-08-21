from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.batch import Batch
from app.models.student import Student
from app.models.session import Session as SessionModel
from app.models.attendance import Attendance
from app.models.batch_schedule_exception import BatchScheduleException

from app.schemas.session import (
    SessionStart,
    SessionStartResponse,
    SessionEnd,
    SessionEndResponse,
    CompletedSessionResponse,
)

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)



@router.post(
    "/start",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_class(
    data: SessionStart,
    db: DBSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    # =====================================================
    # 1. Find active batch
    # =====================================================

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

    # =====================================================
    # 2. Current date/time
    # =====================================================

    now = datetime.now()

    today = date.today()

    current_time = now.time()

    # =====================================================
    # 3. Check training day / compensation schedule
    # =====================================================

    today_name = today.strftime("%A")

    batch_days = {
        str(d).strip().lower()
        for d in (batch.training_days or [])
        if d
    }

    is_regular_training_day = today_name.lower() in batch_days

    compensation = (
        db.query(BatchScheduleException)
        .filter(
            BatchScheduleException.batch_id == batch.id,
            BatchScheduleException.compensation_date == today,
            BatchScheduleException.status == "APPROVED",
        )
        .first()
    )

    is_compensation_day = compensation is not None

    if not is_regular_training_day and not is_compensation_day:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Today ({today_name}) is not "
                f"a scheduled training day or approved compensation day for this batch"
            ),
        )

    # =====================================================
    # 4. Check if class already started or completed today
    # =====================================================

    existing_live_session = (
        db.query(SessionModel)
        .filter(
            SessionModel.batch_id == batch.id,
            SessionModel.session_date == today,
            SessionModel.status == "LIVE",
        )
        .first()
    )

    if existing_live_session is not None:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Class is already started for this batch",
        )

    completed_session = (
        db.query(SessionModel)
        .filter(
            SessionModel.batch_id == batch.id,
            SessionModel.session_date == today,
            SessionModel.status == "COMPLETED",
        )
        .first()
    )

    if completed_session is not None:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Today's class has already been completed for this batch",
        )

    # =====================================================
    # 5. Create session
    # =====================================================

    session = SessionModel(
        batch_id=batch.id,
        coach_id=current_admin.id,
        session_date=today,

        scheduled_start_time=batch.start_time,
        scheduled_end_time=batch.end_time,

        actual_start_time=current_time,

        status="LIVE",

        location=batch.location,
    )

    db.add(session)

    db.commit()

    db.refresh(session)

    # =====================================================
    # 6. Get students in this batch
    # =====================================================

    students = (
        db.query(Student)
        .filter(
            Student.batch_id == batch.id,
            Student.is_active.is_(True),
        )
        .order_by(Student.id.asc())
        .all()
    )

    # =====================================================
    # 7. Build student attendance data
    # =====================================================

    student_data = []

    for student in students:

        # -------------------------------------------------
        # Previous/current attendance records
        #
        # We count completed sessions only.
        # Current LIVE session is not included yet.
        # -------------------------------------------------

        conducted_classes = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id == batch.id,
                SessionModel.status == "COMPLETED",
                SessionModel.session_date <= today,
            )
            .count()
        )

        # -------------------------------------------------
        # Student attended count
        # -------------------------------------------------

        attended_classes = (
            db.query(Attendance)
            .join(
                SessionModel,
                Attendance.session_id == SessionModel.id,
            )
            .filter(
                Attendance.student_id == student.id,
                Attendance.status == "Present",
                SessionModel.batch_id == batch.id,
                SessionModel.status == "COMPLETED",
                SessionModel.session_date <= today,
            )
            .count()
        )

        # -------------------------------------------------
        # Attendance percentage
        # -------------------------------------------------

        if conducted_classes > 0:

            attendance_percentage = round(
                (
                    attended_classes
                    / conducted_classes
                ) * 100,
                2,
            )

        else:

            attendance_percentage = 0.0

        # -------------------------------------------------
        # Current session attendance
        # -------------------------------------------------

        current_attendance = (
            db.query(Attendance)
            .filter(
                Attendance.session_id == session.id,
                Attendance.student_id == student.id,
            )
            .first()
        )

        attendance_status = (
            current_attendance.status
            if current_attendance
            else None
        )

        student_data.append(
            {
                "id": student.id,

                "full_name": student.full_name,

                "avatar_uri": student.avatar_uri,

                "batch_name": batch.batch_name,

                "attendance_status": attendance_status,

                "attended_classes": attended_classes,

                "conducted_classes": conducted_classes,

                "attendance_percentage":
                    attendance_percentage,
            }
        )

    # =====================================================
    # 8. Response
    # =====================================================

    return {
        "status": "success",

        "message": "Class started successfully",

        "data": {
            "id": session.id,

            "batch_id": session.batch_id,

            "batch_name": batch.batch_name,

            "coach_id": session.coach_id,

            "session_date": session.session_date,

            "scheduled_start_time":
                session.scheduled_start_time,

            "scheduled_end_time":
                session.scheduled_end_time,

            "actual_start_time":
                session.actual_start_time,

            "actual_end_time":
                session.actual_end_time,

            "status": session.status,

            "location": session.location,

            "is_compensation_class": is_compensation_day,

            "compensation_reason": (
                compensation.reason
                if (is_compensation_day and compensation)
                else None
            ),

            "students": student_data,

            "created_at": session.created_at,

            "updated_at": session.updated_at,
        },
    }





@router.post(
    "/end",
    response_model=SessionEndResponse,
)
def end_class(
    data: SessionEnd,
    db: DBSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    # =====================================================
    # 1. Find LIVE session
    # =====================================================

    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.id == data.session_id,
            SessionModel.status == "LIVE",
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session not found",
        )

    # =====================================================
    # 2. Verify coach
    # =====================================================

    if session.coach_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to end this class",
        )

    # =====================================================
    # 3. Get batch
    # =====================================================

    batch = (
        db.query(Batch)
        .filter(
            Batch.id == session.batch_id,
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # =====================================================
    # 4. Get batch students
    # =====================================================

    students = (
        db.query(Student)
        .filter(
            Student.batch_id == batch.id,
            Student.is_active.is_(True),
        )
        .all()
    )

    # =====================================================
    # 5. Get attendance for this session
    # =====================================================

    attendance_records = (
        db.query(Attendance)
        .filter(
            Attendance.session_id == session.id,
        )
        .all()
    )

    attended_students = sum(
        1
        for attendance in attendance_records
        if attendance.status == "Present"
    )

    absent_students = sum(
        1
        for attendance in attendance_records
        if attendance.status == "Absent"
    )

    total_students = len(students)

    # =====================================================
    # 6. End session
    # =====================================================

    session.actual_end_time = datetime.now().time()

    session.status = "COMPLETED"

    db.commit()
    db.refresh(session)

    # =====================================================
    # 7. Response
    # =====================================================

    return {
        "status": "success",
        "message": "Class ended successfully",
        "data": {
            "id": session.id,
            "batch_id": session.batch_id,
            "batch_name": batch.batch_name,
            "coach_id": session.coach_id,
            "session_date": session.session_date,
            "scheduled_start_time":
                session.scheduled_start_time,
            "scheduled_end_time":
                session.scheduled_end_time,
            "actual_start_time":
                session.actual_start_time,
            "actual_end_time":
                session.actual_end_time,
            "status": session.status,
            "location": session.location,

            "attended_students": attended_students,
            "absent_students": absent_students,
            "total_students": total_students,

            "created_at": session.created_at,
            "updated_at": session.updated_at,
        },
    }




# =========================================================
# GET COMPLETED SESSION ATTENDANCE
# =========================================================

@router.get(
    "/{session_id}/completed",
    response_model=CompletedSessionResponse,
)
def get_completed_session(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):

    # =====================================================
    # 1. GET SESSION
    # =====================================================

    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.id == session_id,
            SessionModel.status == "COMPLETED",
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Completed session not found",
        )

    # =====================================================
    # 2. GET BATCH
    # =====================================================

    batch = (
        db.query(Batch)
        .filter(
            Batch.id == session.batch_id,
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
    # 3. GET STUDENTS OF THIS BATCH
    # =====================================================

    students = (
        db.query(Student)
        .filter(
            Student.batch_id == batch.id,
            Student.is_active.is_(True),
        )
        .order_by(
            Student.id.asc()
        )
        .all()
    )

    total_count = len(students)

    # =====================================================
    # 4. GET ALL COMPLETED SESSIONS FOR THIS BATCH
    #
    # This is used for:
    #
    # attended_count
    # conducted_count
    #
    # Example:
    # attended_count = 20
    # conducted_count = 24
    # =====================================================

    completed_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.batch_id == batch.id,
            SessionModel.status == "COMPLETED",
            SessionModel.session_date <= session.session_date,
        )
        .order_by(
            SessionModel.session_date.asc()
        )
        .all()
    )

    conducted_count = len(
        completed_sessions
    )

    completed_session_ids = [
        item.id
        for item in completed_sessions
    ]

    # =====================================================
    # 5. GET CURRENT SESSION ATTENDANCE
    #
    # This tells us:
    #
    # Rahul -> Present
    # Sharma -> Absent
    # =====================================================

    current_attendance = (
        db.query(Attendance)
        .filter(
            Attendance.session_id == session.id
        )
        .all()
    )

    current_attendance_map = {
        attendance.student_id:
            attendance.status
        for attendance in current_attendance
    }

    # =====================================================
    # 6. GET TOTAL PRESENT ATTENDANCE
    #
    # For all completed sessions of this batch
    # =====================================================

    student_items = []

    present_count = 0
    absent_count = 0

    attendance_percentages = []

    for student in students:

        # =================================================
        # TODAY / CURRENT SESSION STATUS
        # =================================================

        current_status = (
            current_attendance_map.get(
                student.id
            )
        )

        if current_status is None:

            current_status = "absent"

        # Normalize status for frontend

        if str(current_status).lower() == "present":

            display_status = "present"

        else:

            display_status = "absent"

        # =================================================
        # SESSION PRESENT COUNT
        #
        # Count how many completed classes
        # this student attended.
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

        attendance_percentages.append(
            attendance_percentage
        )

        # =================================================
        # CURRENT SESSION SUMMARY
        # =================================================

        if display_status == "present":

            present_count += 1

        else:

            absent_count += 1

        # =================================================
        # STUDENT ITEM
        # =================================================

        student_items.append(
            {
                "id":
                    str(student.id),

                "name":
                    student.full_name,

                "attendance_percent":
                    f"{attendance_percentage:g}% Attendance",

                "status":
                    display_status,

                "attended_count":
                    attended_count,

                "conducted_count":
                    conducted_count,

                "avatar_uri":
                    student.avatar_uri,
            }
        )

    # =====================================================
    # 7. BATCH TIME
    # =====================================================

    start_label = batch.start_time.strftime(
        "%I:%M %p"
    ).lstrip("0")

    end_label = batch.end_time.strftime(
        "%I:%M %p"
    ).lstrip("0")

    batch_name_with_time = (
        f"{batch.batch_name} "
        f"({start_label} - {end_label})"
    )

    # =====================================================
    # 8. DATE TEXT
    # =====================================================

    if session.session_date == date.today():

        date_text = (
            f"Today · "
            f"{session.session_date.strftime('%d %b %Y')}"
        )

    else:

        date_text = (
            session.session_date.strftime(
                "%A · %d %b %Y"
            )
        )

    # =====================================================
    # 9. FINAL RESPONSE
    # =====================================================

    return {

        "status":
            "success",

        "message":
            "Completed class data fetched successfully",

        "data": {

            "session_details": {

                "batch_title":
                    f"{batch.batch_name} Students",

                "batch_name":
                    batch_name_with_time,

                "date_text":
                    date_text,

                "total_count":
                    total_count,

                "present_count":
                    present_count,

                "absent_count":
                    absent_count,
            },

            "students":
                student_items,
        },
    }