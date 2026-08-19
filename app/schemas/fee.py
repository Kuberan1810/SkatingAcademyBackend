from pydantic import BaseModel, Field, field_validator

from datetime import date

VALID_PAYMENT_METHODS = {
    "CASH",
    "UPI",
    "CARD",
}


class FeeCollect(BaseModel):

    student_id: int = Field(
        gt=0
    )

    # Selected fee month
    fee_month: int = Field(
        ge=1,
        le=12,
    )

    # Selected fee year
    fee_year: int = Field(
        ge=2020,
        le=2100,
    )

    discount: int = Field(
        default=0,
        ge=0,
    )

    late_fine: int = Field(
        default=0,
        ge=0,
    )

    net_payable: int = Field(
        gt=0,
    )

    payment_method: str

    notes: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(
        cls,
        value: str,
    ) -> str:

        value = value.upper()

        if value not in VALID_PAYMENT_METHODS:
            raise ValueError(
                "Invalid payment method. "
                "Choose from: CASH, UPI, CARD"
            )

        return value


class FeeCollectResponseData(BaseModel):

    transaction_id: str

    student_id: int
    student_name: str
    batch_name: str

    fee_month: int
    fee_year: int

    fee_period_label: str

    base_amount: int
    discount: int
    late_fine: int
    net_payable: int

    payment_method: str
    notes: str | None

    collected_by: int

    payment_date: str
    created_at: str


class FeeCollectResponse(BaseModel):

    status: str
    message: str
    data: FeeCollectResponseData







# =========================================================
# FEE PAGE OVERVIEW
# =========================================================

class FeePageOverview(BaseModel):
    total_students_count: int
    today_collection_count: int
    total_collection_target: int
    pending_fees_amount: int
    this_month_amount: int


# =========================================================
# STUDENT FEE ITEM
# =========================================================

class FeePageStudent(BaseModel):
    id: str
    name: str
    batch_name: str
    location: str
    phone: str
    payment_status: str
    amount: int
    paid_date: str | None

# =========================================================
# RECENT PAYMENT
# =========================================================

class RecentPayment(BaseModel):
    id: str
    student_id: int | None = None
    name: str
    time_ago_or_date: str
    payment_method: str
    amount: int


class RecentPaymentDetail(BaseModel):
    id: str
    student_id: int
    name: str
    avatar_uri: str | None = None
    batch_name: str | None = None
    time_ago_or_date: str
    payment_date: str | None = None
    payment_method: str
    amount: int
    fee_month: int | None = None
    fee_year: int | None = None


class RecentPaymentsResponse(BaseModel):
    status: str
    message: str
    data: list[RecentPaymentDetail]


# =========================================================
# FEE PAGE DATA
# =========================================================

class FeePageData(BaseModel):
    overview: FeePageOverview

    students: list[FeePageStudent]

    recent_payments: list[RecentPayment]


# =========================================================
# FINAL RESPONSE
# =========================================================

class FeePageResponse(BaseModel):
    status: str
    message: str
    data: FeePageData





# =========================================================
# PENDING FEE STUDENT
# =========================================================

class PendingFeeStudent(BaseModel):
    id: int

    name: str

    batch_id: int
    batch_name: str

    phone: str

    avatar_uri: str | None = None

    pending_amount: int

    due_date: date

    due_date_text: str

    status: str

# =========================================================
# PENDING FEE COLLECTION
# =========================================================

class PendingFeeSummary(BaseModel):
    total_pending_amount: int
    total_students_count: int

    overdue_amount: int
    overdue_count: int

    due_today_amount: int
    due_today_count: int

    upcoming_amount: int
    upcoming_count: int


class PendingFeeItem(BaseModel):
    id: str

    student_name: str
    batch_name: str

    due_date: str

    amount: int

    status: str

    phone: str

    avatar_uri: str | None = None


class PendingFeeData(BaseModel):
    summary: PendingFeeSummary

    fees: list[PendingFeeItem]


class PendingFeeCollectionResponse(BaseModel):
    status: str
    message: str
    data: PendingFeeData