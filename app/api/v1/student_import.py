import os
import tempfile

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Body  


from app.auth.dependencies import (
    get_current_admin,
)

from app.core.dependencies import (
    get_db,
)

from app.models.admin import Admin
from app.models.batch import Batch
from app.models.student import Student

from app.schemas.student_import import (
    StudentImportConfirmRequest,
)

from app.services.student_import import (
    normalize_record,
    parse_file,
    parse_text_records,
)


router = APIRouter(
    prefix="/students/import",
    tags=[
        "Student Import"
    ],
)


# =========================================================
# FILE TYPES
# =========================================================

ALLOWED_EXTENSIONS = {
    ".xlsx",
    ".csv",
    ".docx",
    ".txt",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


MAX_FILE_SIZE = (
    10 * 1024 * 1024
)


# =========================================================
# COMMON PREVIEW RESPONSE
# =========================================================

def build_preview_response(
    students: list[dict],
    source: str,
    file_name: str | None = None,
    file_type: str | None = None,
):

    return {

        "status":
            "success",

        "message":
            "Student data extracted successfully",

        "data": {

            "source":
                source,

            "file_name":
                file_name,

            "file_type":
                file_type,

            "total_records":
                len(students),

            "valid_records":
                sum(
                    1
                    for student
                    in students
                    if student["status"]
                    == "valid"
                ),

            "warning_records":
                sum(
                    1
                    for student
                    in students
                    if student["status"]
                    == "warning"
                ),

            "invalid_records":
                sum(
                    1
                    for student
                    in students
                    if student["status"]
                    == "invalid"
                ),

            "students":
                students,
        },
    }


# =========================================================
# FILE PREVIEW
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

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail=(
                "File name is required"
            ),
        )

    extension = (
        os.path.splitext(
            file.filename
        )[1]
        .lower()
    )

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Supported: XLSX, CSV, DOCX, "
                "TXT, PDF, JPG, JPEG, PNG, WEBP"
            ),
        )

    content = (
        file.file.read()
    )

    if not content:

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    if len(content) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                "File size cannot exceed 10 MB"
            ),
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:

            temp_file.write(
                content
            )

            temp_path = (
                temp_file.name
            )

        try:

            raw_records = parse_file(
                temp_path
            )

        except Exception as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unable to read file: "
                    f"{str(exc)}"
                ),
            ) from exc

        if not raw_records:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No student records "
                    "were found in the file"
                ),
            )

        students = []

        

        for index, raw_record in enumerate(
            raw_records,
            start=2,
        ):

            normalized = normalize_record(
                raw_record,
                db,
            )

            normalized["row_number"] = index

            students.append(
                normalized
            )

        return build_preview_response(
            students,
            source="file",
            file_name=file.filename,
            file_type=extension.replace(
                ".",
                "",
            ),
        )

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            os.remove(
                temp_path
            )


# =========================================================
# COPY / PASTE TEXT
# =========================================================


class StudentImportTextRequest(
    BaseModel
):

    text: str


@router.post(
    "/text/preview",
    summary="Preview Student Import Text",
)
def preview_student_import_text(
    text: str = Body(
        ...,
        media_type="text/plain",
        description="Paste student data in any supported text format",
    ),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(
        get_current_admin
    ),
):
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text input is empty",
        )

    try:
        raw_records = parse_text_records(
            text
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to parse text: {exc}",
        ) from exc

    if not raw_records:
        raise HTTPException(
            status_code=400,
            detail="No student records found in the provided text",
        )

    students = []

    for index, raw_record in enumerate(
        raw_records,
        start=2,
    ):
        normalized = normalize_record(
            raw_record,
            db,
        )

        normalized["row_number"] = index

        students.append(
            normalized
        )

    return build_preview_response(
        students,
        source="text",
    )

# =========================================================
# CONFIRM IMPORT
# =========================================================

@router.post(
    "/confirm"
)
def confirm_student_import(

    request:
        StudentImportConfirmRequest,

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
            detail=(
                "No students to import"
            ),
        )

    created = []

    failed = []

    # =====================================================
    # PROCESS
    # =====================================================

    for record in request.students:

        # -------------------------------------------------
        # Only valid / warning records
        # -------------------------------------------------

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
            # BATCH RESOLUTION
            # =============================================

            batch = None

            # First ID
            if (
                record.batch_id
                is not None
            ):

                batch = (
                    db.query(Batch)
                    .filter(
                        Batch.id
                        == record.batch_id,

                        Batch.is_active.is_(
                            True
                        ),
                    )
                    .first()
                )

            # Fallback name
            if (
                batch is None
                and record.batch_name
            ):

                batch = (
                    db.query(Batch)
                    .filter(
                        Batch.batch_name.ilike(
                            record.batch_name.strip()
                        ),

                        Batch.is_active.is_(
                            True
                        ),
                    )
                    .first()
                )

            if batch is None:

                raise ValueError(
                    (
                        "Batch not found "
                        "or inactive"
                    )
                )

            # =============================================
            # DUPLICATE PHONE
            # =============================================

            duplicate = (
                db.query(Student)
                .filter(
                    Student.phone_number
                    == record.phone_number
                )
                .first()
            )

            if duplicate:

                raise ValueError(
                    (
                        "Student already exists "
                        "with phone number "
                        f"{record.phone_number}"
                    )
                )

            # =============================================
            # CREATE STUDENT
            # =============================================

            student = Student(

                full_name=
                    record.full_name,

                dob=
                    record.dob,

                gender=
                    record.gender,

                blood_group=
                    record.blood_group,

                batch_id=
                    batch.id,

                join_date=
                    record.join_date,

                parent_name=
                    record.parent_name,

                phone_number=
                    record.phone_number,

                emergency_contact=
                    record.emergency_contact,

                monthly_fee=
                    record.monthly_fee,

                avatar_uri=
                    record.avatar_uri,
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

                    "batch_id":
                        batch.id,

                    "batch_name":
                        batch.batch_name,

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

                    "errors":
                        [
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
        ) from exc

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "status":
            "success",

        "message":
            "Student import completed",

        "data": {

            "total_records":
                len(
                    request.students
                ),

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