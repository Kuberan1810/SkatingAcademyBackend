import os
import tempfile
from app.models.batch import Batch
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_admin,
)

from app.core.dependencies import (
    get_db,
)

from app.models.admin import Admin
from app.models.student import Student

from app.schemas.student import (
    StudentCreate,
)

from app.schemas.student_import import (
    ImportStudentRecord,
    StudentImportConfirmRequest,
)

from app.services.student_import import (
    parse_file,
    normalize_record,
)


router = APIRouter(
    prefix="/students/import",
    tags=[
        "Student Import"
    ],
)


ALLOWED_EXTENSIONS = {
    ".xlsx",
    ".csv",
    ".docx",
    ".txt",
}


# =========================================================
# PREVIEW
# =========================================================

@router.post(
    "/preview"
)
def preview_student_import(

    file: UploadFile = File(...),

    db: Session = Depends(
        get_db
    ),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    # =====================================================
    # FILE VALIDATION
    # =====================================================

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="File name is required",
        )

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Supported: XLSX, CSV, DOCX, TXT"
            ),
        )

    # =====================================================
    # TEMP FILE
    # =====================================================

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:

            temp_path = (
                temp_file.name
            )

            content = (
                file.file.read()
            )

            if not content:

                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is empty",
                )

            # 10 MB limit
            if len(content) > 10 * 1024 * 1024:

                raise HTTPException(
                    status_code=413,
                    detail=(
                        "File size cannot exceed 10 MB"
                    ),
                )

            temp_file.write(
                content
            )

        # =================================================
        # PARSE
        # =================================================

        try:

            raw_records = parse_file(
                temp_path
            )

        except Exception as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Unable to read file: "
                    f"{str(exc)}"
                ),
            )

        if not raw_records:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No student records "
                    "were found in the file"
                ),
            )

        # =================================================
        # NORMALIZE + VALIDATE
        # =================================================

        students = []

        for raw_record in raw_records:

            normalized = normalize_record(
                raw_record,
                db,
            )

            students.append(
                normalized
            )

        # =================================================
        # SUMMARY
        # =================================================

        total_records = len(
            students
        )

        valid_records = sum(
            1
            for student
            in students
            if student["status"]
            == "valid"
        )

        warning_records = sum(
            1
            for student
            in students
            if student["status"]
            == "warning"
        )

        invalid_records = sum(
            1
            for student
            in students
            if student["status"]
            == "invalid"
        )

        # =================================================
        # RESPONSE
        # =================================================

        return {
            "status": "success",

            "message":
                "Student data extracted successfully",

            "data": {

                "file_name":
                    file.filename,

                "file_type":
                    extension.replace(
                        ".",
                        ""
                    ),

                "total_records":
                    total_records,

                "valid_records":
                    valid_records,

                "warning_records":
                    warning_records,

                "invalid_records":
                    invalid_records,

                "students":
                    students,
            },
        }

    finally:

        if temp_path and os.path.exists(
            temp_path
        ):

            os.remove(
                temp_path
            )


# =========================================================
# CONFIRM
# =========================================================

@router.post(
    "/confirm"
)
def confirm_student_import(

    request: StudentImportConfirmRequest,

    db: Session = Depends(
        get_db
    ),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    if not request.students:

        raise HTTPException(
            status_code=400,
            detail="No students to import",
        )

    created = []

    failed = []

    # =====================================================
    # PROCESS EACH STUDENT
    # =====================================================

    for record in request.students:

        # ---------------------------------------------
        # Only valid / warning records
        # ---------------------------------------------

        if record.status not in {
            "valid",
            "warning",
        }:

            failed.append(
                {
                    "row_number":
                        record.row_number,

                    "full_name":
                        record.full_name,

                    "status":
                        "failed",

                    "errors":
                        record.errors
                        or [
                            "Record is invalid"
                        ],
                }
            )

            continue

        try:

            # =============================================
            # FINAL BATCH CHECK
            # =============================================

            batch = (
                db.query(
                    __import__(
                        "app.models.batch",
                        fromlist=["Batch"]
                    ).Batch
                )
                .filter(
                    __import__(
                        "app.models.batch",
                        fromlist=["Batch"]
                    ).Batch.id
                    == record.batch_id,

                    __import__(
                        "app.models.batch",
                        fromlist=["Batch"]
                    ).Batch.is_active.is_(True),
                )
                .first()
            )

            if batch is None:

                raise ValueError(
                    "Batch not found or inactive"
                )

            # =============================================
            # FINAL SCHEMA VALIDATION
            # =============================================

            student_data = StudentCreate(
                full_name=record.full_name,

                dob=record.dob,

                gender=record.gender,

                blood_group=record.blood_group,

                batch_id=record.batch_id,

                join_date=record.join_date,

                parent_name=record.parent_name,

                phone_number=record.phone_number,

                emergency_contact=(
                    record.emergency_contact
                ),

                monthly_fee=record.monthly_fee,

                avatar_uri=record.avatar_uri,
            )

            # =============================================
            # DUPLICATE CHECK AGAIN
            # =============================================

            duplicate = (
                db.query(Student)
                .filter(
                    Student.phone_number
                    == student_data.phone_number
                )
                .first()
            )

            if duplicate:

                raise ValueError(
                    (
                        "Student already exists "
                        f"with phone number "
                        f"{student_data.phone_number}"
                    )
                )

            # =============================================
            # CREATE
            # =============================================

            student = Student(
                full_name=
                    student_data.full_name,

                dob=
                    student_data.dob,

                gender=
                    student_data.gender,

                blood_group=
                    student_data.blood_group,

                batch_id=
                    student_data.batch_id,

                join_date=
                    student_data.join_date,

                parent_name=
                    student_data.parent_name,

                phone_number=
                    student_data.phone_number,

                emergency_contact=
                    student_data.emergency_contact,

                monthly_fee=
                    student_data.monthly_fee,

                avatar_uri=
                    student_data.avatar_uri,
            )

            db.add(
                student
            )

            db.flush()

            created.append(
                {
                    "row_number":
                        record.row_number,

                    "student_id":
                        student.id,

                    "full_name":
                        student.full_name,

                    "status":
                        "created",
                }
            )

        except Exception as exc:

            failed.append(
                {
                    "row_number":
                        record.row_number,

                    "full_name":
                        record.full_name,

                    "status":
                        "failed",

                    "errors": [
                        str(exc)
                    ],
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
                "Student import failed: "
                f"{str(exc)}"
            ),
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "status": "success",

        "message":
            "Student import completed",

        "data": {

            "total_records":
                len(request.students),

            "created_count":
                len(created),

            "failed_count":
                len(failed),

            "created":
                created,

            "failed":
                failed,
        },
    }



    