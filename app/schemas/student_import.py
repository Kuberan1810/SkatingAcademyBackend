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
    # REQUIRED (Only Name, DOB, Phone are mandatory)
    # =====================================================

    full_name: str

    dob: date

    phone_number: str

    # =====================================================
    # OPTIONAL
    # =====================================================

    gender: str | None = None

    parent_name: str | None = None

    monthly_fee: int | None = None

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