from datetime import date

from pydantic import BaseModel, Field


# =========================================================
# IMPORT STUDENT RECORD
# =========================================================

class ImportStudentRecord(BaseModel):

    # Automatically generated during preview
    row_number: int = Field(
        ge=1
    )

    # =====================================================
    # REQUIRED
    # =====================================================

    full_name: str

    dob: date

    gender: str

    parent_name: str

    phone_number: str

    monthly_fee: int

    # =====================================================
    # OPTIONAL
    # =====================================================

    blood_group: str | None = None

    emergency_contact: str | None = None

    join_date: date | None = None

    avatar_uri: str | None = None

    # =====================================================
    # PREVIEW
    # =====================================================

    status: str

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


# =========================================================
# CONFIRM REQUEST
# =========================================================

class StudentImportConfirmRequest(BaseModel):

    # User selects this from batch dropdown
    batch_id: int = Field(
        gt=0
    )

    students: list[
        ImportStudentRecord
    ]