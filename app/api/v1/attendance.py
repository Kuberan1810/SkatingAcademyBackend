from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.attendance import Attendance
from app.models.batch import Batch
from app.models.session import Session as SessionModel
from app.models.student import Student

from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceCreateResponse,
)


router = APIRouter(
    prefix="/attendance",
    tags=["Attendance"],
)


@router.post(
    "",
    response_model=AttendanceCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_attendance(
    data: AttendanceCreate,
    db: DBSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:

        # ==================================================
        # 1. Find LIVE session
        # ==================================================

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

        # ==================================================
        # 2. Check coach
        # ==================================================

        if session.coach_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not authorized "
                    "to confirm attendance for this session"
                ),
            )

        # ==================================================
        # 3. Get batch
        # ==================================================

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

        # ==================================================
        # 4. Get active students in this batch
        # ==================================================

        students = (
            db.query(Student)
            .filter(
                Student.batch_id == batch.id,
                Student.is_active.is_(True),
            )
            .all()
        )

        student_ids_from_batch = {
            student.id
            for student in students
        }

        # ==================================================
        # 5. Check duplicate student IDs
        # ==================================================

        submitted_student_ids = [
            item.student_id
            for item in data.attendance
        ]

        if len(submitted_student_ids) != len(
            set(submitted_student_ids)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Duplicate student IDs "
                    "are not allowed"
                ),
            )

        submitted_student_ids_set = set(
            submitted_student_ids
        )

        # ==================================================
        # 6. Make sure ALL batch students are submitted
        # ==================================================

        if submitted_student_ids_set != student_ids_from_batch:

            missing_students = (
                student_ids_from_batch
                - submitted_student_ids_set
            )

            extra_students = (
                submitted_student_ids_set
                - student_ids_from_batch
            )

            detail = {}

            if missing_students:
                detail["missing_student_ids"] = sorted(
                    missing_students
                )

            if extra_students:
                detail["invalid_student_ids"] = sorted(
                    extra_students
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": (
                        "Attendance must be submitted "
                        "for every active student "
                        "in the batch"
                    ),
                    **detail,
                },
            )

        # ==================================================
        # 7. Save attendance
        # ==================================================

        present_count = 0
        absent_count = 0

        for item in data.attendance:

            # ----------------------------------------------
            # Student belongs to batch
            # ----------------------------------------------

            if item.student_id not in student_ids_from_batch:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Student {item.student_id} "
                        "does not belong to this batch"
                    ),
                )

            # ----------------------------------------------
            # Check existing attendance
            # ----------------------------------------------

            existing_attendance = (
                db.query(Attendance)
                .filter(
                    Attendance.session_id == session.id,
                    Attendance.student_id == item.student_id,
                )
                .first()
            )

            if existing_attendance is not None:

                # Update if somehow already exists
                existing_attendance.status = item.status

            else:

                attendance_record = Attendance(
                    session_id=session.id,
                    student_id=item.student_id,
                    status=item.status,
                )

                db.add(attendance_record)

            # ----------------------------------------------
            # Count
            # ----------------------------------------------

            if item.status == "Present":
                present_count += 1

            elif item.status == "Absent":
                absent_count += 1

        # ==================================================
        # 8. Automatically END CLASS
        # ==================================================

        actual_end_time = datetime.now().time()

        session.actual_end_time = actual_end_time

        session.status = "COMPLETED"

        # ==================================================
        # 9. Commit everything together
        # ==================================================

        db.commit()

        # ==================================================
        # 10. Refresh session
        # ==================================================

        db.refresh(session)

        # ==================================================
        # 11. Response
        # ==================================================

        return {
            "status": "success",
            "message": (
                "Attendance confirmed and "
                "class completed successfully"
            ),
            "data": {
                "session_id": session.id,
                "batch_id": session.batch_id,
                "batch_name": batch.batch_name,
                "location": batch.location,

                "total_students": len(students),

                "present_students": present_count,

                "absent_students": absent_count,

                "attendance_confirmed": True,

                "class_completed": True,

                "actual_end_time": (
                    session.actual_end_time.isoformat()
                ),
            },
        }

    except HTTPException:
        # ----------------------------------------------
        # Re-raise expected API errors
        # ----------------------------------------------

        db.rollback()
        raise

    except Exception:
        # ----------------------------------------------
        # Rollback unexpected database errors
        # ----------------------------------------------

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to confirm attendance "
                "and complete class"
            ),
        )