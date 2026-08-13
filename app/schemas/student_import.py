from datetime import date

from pydantic import BaseModel, Field


class ImportStudentRecord(BaseModel):
    row_number: int

    full_name: str | None = None
    dob: date | None = None
    gender: str | None = None
    blood_group: str | None = None

    batch_id: int | None = None
    batch_name: str | None = None

    join_date: date | None = None

    parent_name: str | None = None
    phone_number: str | None = None
    emergency_contact: str | None = None

    monthly_fee: int | None = None

    avatar_uri: str | None = None

    status: str = "valid"

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class StudentImportPreviewResponse(BaseModel):
    status: str
    message: str
    data: dict


class StudentImportConfirmRequest(BaseModel):
    students: list[ImportStudentRecord]


class StudentImportResult(BaseModel):
    row_number: int
    student_id: int | None = None
    full_name: str | None = None
    status: str
    errors: list[str] = Field(
        default_factory=list
    )


class StudentImportConfirmResponse(BaseModel):
    status: str
    message: str
    data: dict