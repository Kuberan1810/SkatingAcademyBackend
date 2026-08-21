from datetime import date, datetime, time

from pydantic import BaseModel


class SessionStart(BaseModel):
    batch_id: int


class SessionEnd(BaseModel):
    session_id: int


class SessionStudent(BaseModel):
    id: int
    full_name: str
    avatar_uri: str | None
    batch_name: str
    attendance_status: str | None
    attended_classes: int
    conducted_classes: int
    attendance_percentage: float


class SessionData(BaseModel):
    id: int
    batch_id: int
    batch_name: str
    coach_id: int
    session_date: date
    scheduled_start_time: time
    scheduled_end_time: time
    actual_start_time: time | None
    actual_end_time: time | None
    status: str
    location: str
    is_compensation_class: bool = False
    compensation_reason: str | None = None
    students: list[SessionStudent]
    created_at: datetime
    updated_at: datetime


class SessionStartResponse(BaseModel):
    status: str
    message: str
    data: SessionData



class SessionEndData(BaseModel):
    id: int
    batch_id: int
    batch_name: str
    coach_id: int
    session_date: date
    scheduled_start_time: time
    scheduled_end_time: time
    actual_start_time: time | None
    actual_end_time: time | None
    status: str
    location: str

    attended_students: int
    absent_students: int
    total_students: int

    created_at: datetime
    updated_at: datetime


class SessionEndResponse(BaseModel):
    status: str
    message: str
    data: SessionEndData






# =========================================================
# SESSION DETAILS
# =========================================================

class CompletedSessionDetails(BaseModel):
    batch_title: str
    batch_name: str
    date_text: str

    total_count: int
    present_count: int
    absent_count: int


# =========================================================
# STUDENT ATTENDANCE ITEM
# =========================================================

class CompletedStudentItem(BaseModel):
    id: str
    name: str

    attendance_percent: str

    # Today's attendance
    status: str

    # Overall attendance count
    attended_count: int
    conducted_count: int

    avatar_uri: str | None


# =========================================================
# COMPLETED SESSION DATA
# =========================================================

class CompletedSessionData(BaseModel):
    session_details: CompletedSessionDetails
    students: list[CompletedStudentItem]


# =========================================================
# FINAL RESPONSE
# =========================================================

class CompletedSessionResponse(BaseModel):
    status: str
    message: str
    data: CompletedSessionData