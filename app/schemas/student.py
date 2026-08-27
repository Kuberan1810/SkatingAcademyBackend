from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


VALID_GENDERS = {
    "Male",
    "Female",
    "Other",
}

VALID_BLOOD_GROUPS = {
    "A+",
    "A-",
    "B+",
    "B-",
    "AB+",
    "AB-",
    "O+",
    "O-",
}


class StudentCreate(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    dob: date

    gender: str

    blood_group: str | None = None

    batch_id: int = Field(
        gt=0,
    )

    join_date: date

    parent_name: str = Field(
        min_length=2,
        max_length=150,
    )

    phone_number: str = Field(
        min_length=10,
        max_length=20,
    )

    emergency_contact: str = Field(
        min_length=10,
        max_length=20,
    )

    monthly_fee: int | None = Field(
        default=None,
        ge=0,
    )



    avatar_uri: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        if value not in VALID_GENDERS:
            raise ValueError(
                f"Invalid gender. Choose from: "
                f"{', '.join(sorted(VALID_GENDERS))}"
            )

        return value

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return value

        if value not in VALID_BLOOD_GROUPS:
            raise ValueError(
                f"Invalid blood group. Choose from: "
                f"{', '.join(sorted(VALID_BLOOD_GROUPS))}"
            )

        return value


class StudentUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    dob: date | None = None

    gender: str | None = None

    blood_group: str | None = None

    batch_id: int | None = Field(
        default=None,
        gt=0,
    )

    join_date: date | None = None

    parent_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
    )

    emergency_contact: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
    )

    monthly_fee: int | None = Field(
        default=None,
        gt=0,
    )

    avatar_uri: str | None = Field(
        default=None,
        max_length=500,
    )


class StudentResponse(BaseModel):
    id: int
    full_name: str
    age: int
    gender: str
    dob: date
    blood_group: str | None

    batch_id: int
    batch_name: str

    join_date: date
    parent_name: str
    phone_number: str
    emergency_contact: str

    monthly_fee: int

    avatar_uri: str | None

    is_active: bool

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class StudentCreateResponse(BaseModel):
    status: str
    message: str
    data: StudentResponse


class StudentListResponse(BaseModel):
    status: str
    message: str
    data: list[StudentResponse]







# =========================================================
# ALL STUDENTS PAGE
# =========================================================

class AllStudentsOverview(BaseModel):
    total_students: int
    new_this_month: int

    boys_count: int
    boys_percent: float

    girls_count: int
    girls_percent: float

    pending_fees_count: int

class LastPayment(BaseModel):
    amount: int
    fee_month: int
    fee_year: int
    paid_date: str | None


class AllStudentItem(BaseModel):
    id: str
    name: str
    batch_name: str
    joined_date: str
    location: str
    attendance_percent: str
    phone: str

    # Current month fee
    payment_status: str
    amount: int
    paid_date: str | None

    # Payment tracking & overdue history
    last_paid_date: str | None = None
    last_paid_month: str | None = None
    unpaid_months_count: int = 0
    total_pending_amount: int = 0
    previous_month_status: str = "unpaid"

    # Latest payment
    last_payment: LastPayment | None

    # Attendance
    attended_count: int
    conducted_count: int

    avatar_uri: str | None



class AllStudentsPageData(BaseModel):
    overview: AllStudentsOverview
    students: list[AllStudentItem]


class AllStudentsPageResponse(BaseModel):
    status: str
    message: str
    data: AllStudentsPageData


# =========================================================
# STUDENT PROFILE SCHEMAS
# =========================================================

class StudentParentInfo(BaseModel):
    parent_name: str
    phone: str
    emergency: str


class StudentPersonalInfo(BaseModel):
    gender: str
    dob: date
    blood_group: str | None = None


class StudentFeeInfo(BaseModel):
    monthly_fee: int
    pending: int
    status: str


class StudentAttendanceStats(BaseModel):
    present: int
    absent: int
    attendance_percent: str

    # Total training days up to today
    scheduled_days_count: int

    # Classes actually conducted
    conducted_days_count: int


class AttendanceGridItem(BaseModel):
    day_name: str
    day_number: str
    full_date: str
    status: str


class StudentBalanceSummary(BaseModel):
    last_paid_amount: int | None
    last_paid_date: str | None

    next_payment_amount: int
    next_payment_due_date: str

    days_left_text: str


class CurrentMonthFee(BaseModel):
    month_year: str
    amount: int
    status: str
    status_subtext: str
    payment_details: str


class StudentTransaction(BaseModel):
    id: str
    title: str
    date_and_method: str
    amount: int
    status: str


class StudentProfileData(BaseModel):

    id: str
    name: str
    avatar_uri: str | None

    joined_date: str
    location: str
    attendance_percent: str

    parent_info: StudentParentInfo
    personal_info: StudentPersonalInfo
    fee_info: StudentFeeInfo

    attendance_stats: StudentAttendanceStats
    attendance_grid: list[AttendanceGridItem]

    balance_summary: StudentBalanceSummary

    current_month_fee: CurrentMonthFee

    transactions: list[StudentTransaction]


class StudentProfileResponse(BaseModel):
    status: str
    message: str
    data: StudentProfileData







class BulkDeleteStudentsRequest(BaseModel):
    student_ids: list[int] = Field(
        min_length=1,
        max_length=500,
    )