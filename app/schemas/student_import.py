from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ImportStudentRecord(BaseModel):

    row_number: int = Field(
        ge=1
    )

    full_name: str

    dob: date

    gender: str

    blood_group: str | None = None

    # Batch ID is OPTIONAL.
    # Batch name alone is enough.
    batch_id: int | None = None

    batch_name: str | None = None

    join_date: date

    parent_name: str

    phone_number: str

    emergency_contact: str

    monthly_fee: int

    avatar_uri: str | None = None

    status: Literal[
        "valid",
        "warning",
        "invalid",
    ]

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class StudentImportConfirmRequest(BaseModel):

    students: list[
        ImportStudentRecord
    ]