from pydantic import BaseModel, Field, field_validator


VALID_ATTENDANCE_STATUS = {
    "Present",
    "Absent",
}


class AttendanceItem(BaseModel):
    student_id: int = Field(gt=0)
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_ATTENDANCE_STATUS:
            raise ValueError(
                "Status must be Present or Absent"
            )

        return value


class AttendanceCreate(BaseModel):
    session_id: int = Field(gt=0)

    attendance: list[AttendanceItem] = Field(
        min_length=1
    )


class AttendanceSummaryData(BaseModel):
    session_id: int
    batch_id: int
    batch_name: str
    location: str

    total_students: int
    present_students: int
    absent_students: int

    attendance_confirmed: bool
    class_completed: bool

    actual_end_time: str


class AttendanceCreateResponse(BaseModel):
    status: str
    message: str
    data: AttendanceSummaryData