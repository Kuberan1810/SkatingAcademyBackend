from datetime import time

from pydantic import BaseModel, Field, field_validator

from pydantic import BaseModel

VALID_LEVELS = {
    "Basic",
    "Intermediate",
    "Advanced",
    "Professional",
}

VALID_CLASS_TYPES = {
    "Weekend",
    "Weekday",
    "Daily",
    "Custom",
}

VALID_DAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}


class BatchCreate(BaseModel):
    batch_name: str = Field(
        min_length=2,
        max_length=100,
    )

    level: str

    location: str = Field(
        min_length=2,
        max_length=150,
    )

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    class_type: str

    training_days: list[str] = Field(
        min_length=1,
        max_length=7,
    )

    start_time: time
    end_time: time

    monthly_fee: int = Field(
        gt=0,
    )

    yearly_fee: int = Field(
        gt=0,
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        if value not in VALID_LEVELS:
            raise ValueError(
                f"Invalid level. Choose from: "
                f"{', '.join(sorted(VALID_LEVELS))}"
            )

        return value

    @field_validator("class_type")
    @classmethod
    def validate_class_type(cls, value: str) -> str:
        if value not in VALID_CLASS_TYPES:
            raise ValueError(
                f"Invalid class type. Choose from: "
                f"{', '.join(sorted(VALID_CLASS_TYPES))}"
            )

        return value

    @field_validator("training_days")
    @classmethod
    def validate_training_days(cls, days: list[str]) -> list[str]:

        # Duplicate days
        if len(days) != len(set(days)):
            raise ValueError(
                "Training days cannot contain duplicates"
            )

        # Invalid days
        invalid_days = set(days) - VALID_DAYS

        if invalid_days:
            raise ValueError(
                f"Invalid training days: "
                f"{', '.join(sorted(invalid_days))}"
            )

        return days

    @field_validator("training_days")
    @classmethod
    def validate_days_by_class_type(
        cls,
        days: list[str],
        info,
    ) -> list[str]:

        class_type = info.data.get("class_type")

        selected_days = set(days)

        # Weekend
        if class_type == "Weekend":
            required_days = {
                "Saturday",
                "Sunday",
            }

            if selected_days != required_days:
                raise ValueError(
                    "Weekend batches must have Saturday and Sunday"
                )

        # Weekday
        elif class_type == "Weekday":
            required_days = {
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
            }

            if selected_days != required_days:
                raise ValueError(
                    "Weekday batches must have Monday to Friday"
                )

        # Daily
        elif class_type == "Daily":
            if selected_days != VALID_DAYS:
                raise ValueError(
                    "Daily batches must have all seven days"
                )

        # Custom
        elif class_type == "Custom":
            if not selected_days:
                raise ValueError(
                    "Custom batch must have at least one training day"
                )

        return days


class BatchResponse(BaseModel):
    id: int
    batch_name: str
    level: str
    location: str
    description: str | None
    class_type: str
    training_days: list[str]
    start_time: time
    end_time: time
    monthly_fee: int
    yearly_fee: int
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


#batch update

class BatchUpdate(BaseModel):
    batch_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    level: str | None = None

    location: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    class_type: str | None = None

    training_days: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=7,
    )

    start_time: time | None = None

    end_time: time | None = None

    monthly_fee: int | None = Field(
        default=None,
        gt=0,
    )

    yearly_fee: int | None = Field(
        default=None,
        gt=0,
    )





# =========================================================
# BATCH PAGE OVERVIEW
# =========================================================

class BatchPageStudents(BaseModel):
    total: int


class BatchPageAttendance(BaseModel):
    present: int
    total_expected: int
    percentage: float


class BatchPageTodaySessions(BaseModel):
    scheduled: int
    completed: int
    total_active_sessions: int


class BatchPageOverview(BaseModel):

    total_batches: int

    new_batches_this_month: int

    todays_sessions: BatchPageTodaySessions

    students: BatchPageStudents

    todays_attendance: BatchPageAttendance


# =========================================================
# BATCH ITEM
# =========================================================

class BatchPageItem(BaseModel):

    id: str

    title: str

    date: str

    time: str

    students_count: int

    status: str

    category: str

    attendance: str | None


# =========================================================
# BATCH PAGE DATA
# =========================================================

class BatchPageData(BaseModel):

    overview: BatchPageOverview

    batches: list[BatchPageItem]


# =========================================================
# FINAL RESPONSE
# =========================================================

class BatchPageResponse(BaseModel):

    status: str

    message: str

    data: BatchPageData


class BatchCreateResponse(BaseModel):
    status: str
    message: str
    data: BatchResponse


class BatchListResponse(BaseModel):
    status: str
    message: str
    data: list[BatchResponse]





class LastPayment(BaseModel):
    amount: int
    fee_month: int
    fee_year: int
    paid_date: str | None


class BatchStudentItem(BaseModel):
    id: str
    name: str
    joined_date: str
    location: str
    attendance_percent: str
    phone: str
    payment_status: str
    amount: int
    paid_date: str | None

    last_payment: LastPayment | None

    attendance_ratio: str
    attendance_ratio_status: str
    avatar_uri: str | None

# =========================================================
# BATCH DETAILS
# =========================================================

class BatchStudentDetails(BaseModel):
    batch_title: str
    batch_name: str
    total_students: str
    avg_attendance: str


# =========================================================
# BATCH STUDENTS DATA
# =========================================================

class BatchStudentsData(BaseModel):
    batch_details: BatchStudentDetails
    students: list[BatchStudentItem]


# =========================================================
# FINAL RESPONSE
# =========================================================

class BatchStudentsResponse(BaseModel):
    status: str
    message: str
    data: BatchStudentsData