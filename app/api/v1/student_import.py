import os
import tempfile
from datetime import date

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from sqlalchemy.orm import Session

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
import pytesseract

router = APIRouter(
    prefix="/students/import",
    tags=[
        "Student Import"
    ],
)


# =========================================================
# SUPPORTED FILES
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
# PREVIEW RESPONSE BUILDER
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
async def preview_student_import(

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
                "Supported: XLSX, CSV, DOCX, TXT, "
                "PDF, JPG, JPEG, PNG, WEBP"
            ),
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size cannot exceed 10 MB",
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

            temp_file.flush()
            os.fsync(temp_file.fileno())

            temp_path = temp_file.name

        raw_records = parse_file(
            temp_path
        )

        if not raw_records:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No student records found "
                    "in uploaded file"
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

            normalized[
                "row_number"
            ] = index

            students.append(
                normalized
            )

        return build_preview_response(
            students,
            source="file",
            file_name=file.filename,
            file_type=extension[1:],
        )

    except HTTPException:
        raise

    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Tesseract OCR engine is not installed or accessible on the server. "
                f"Details: {exc}"
            ),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):
            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass

# =========================================================
# TEXT PREVIEW
# =========================================================

@router.post(
    "/text/preview",
)
def preview_student_import_text(

    text: str = Body(
        ...,
        media_type="text/plain",
    ),

    db: Session = Depends(
        get_db
    ),

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

        raw_records = (
            parse_text_records(
                text
            )
        )

        if not raw_records:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No student records found"
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

            normalized[
                "row_number"
            ] = index

            students.append(
                normalized
            )

        return build_preview_response(
            students,
            source="text",
        )

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# =========================================================
# CONFIRM
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

    # =====================================================
    # VERIFY SELECTED BATCH
    # =====================================================

    batch = (
        db.query(
            Batch
        )
        .filter(
            Batch.id
            == request.batch_id,

            Batch.is_active.is_(
                True
            ),
        )
        .first()
    )

    if batch is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Selected batch "
                "not found or inactive"
            ),
        )

    # =====================================================
    # RESULTS
    # =====================================================

    created = []

    failed = []

    # =====================================================
    # PROCESS STUDENTS
    # =====================================================

    for record in request.students:

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
            # DUPLICATE CHECK
            # =============================================

            duplicate = (
                db.query(
                    Student
                )
                .filter(
                    Student.phone_number
                    == record.phone_number
                )
                .first()
            )

            if duplicate:

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
                                (
                                    "Student already exists "
                                    "with phone number "
                                    f"{record.phone_number}"
                                )
                            ],
                    }
                )

                continue

            # =============================================
            # FALLBACKS FOR OPTIONAL FIELDS
            # =============================================

            final_join_date = (
                record.join_date
                or date.today()
            )

            final_parent_name = (
                (record.parent_name or "").strip()
                or "Parent"
            )

            final_monthly_fee = (
                record.monthly_fee
                if (record.monthly_fee is not None and record.monthly_fee > 0)
                else (batch.monthly_fee or 0)
            )

            final_gender = (
                (record.gender or "").strip()
                or None
            )

            final_emergency_contact = (
                (record.emergency_contact or "").strip()
                or record.phone_number
            )

            # =============================================
            # CREATE
            # =============================================

            student = Student(

                full_name=
                    record.full_name,

                dob=
                    record.dob,

                gender=
                    final_gender,

                blood_group=
                    record.blood_group,

                # Selected batch
                batch_id=
                    batch.id,

                join_date=
                    final_join_date,

                parent_name=
                    final_parent_name,

                phone_number=
                    record.phone_number,

                emergency_contact=
                    final_emergency_contact,

                monthly_fee=
                    final_monthly_fee,

                avatar_uri=
                    record.avatar_uri,

                is_active=True,
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

            "batch": {

                "id":
                    batch.id,

                "batch_name":
                    batch.batch_name,
            },

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



@router.get("/ocr-test")
def ocr_test():
    try:
        version = pytesseract.get_tesseract_version()

        return {
            "status": "success",
            "ocr": "available",
            "version": str(version),
            "executable": pytesseract.pytesseract.tesseract_cmd,
        }

    except Exception as exc:
        return {
            "status": "error",
            "ocr": "unavailable",
            "message": str(exc),
            "executable": pytesseract.pytesseract.tesseract_cmd,
        }