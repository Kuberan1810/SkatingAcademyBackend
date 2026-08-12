from pydantic import BaseModel


# =========================================================
# STUDENTS
# =========================================================

class DashboardStudents(BaseModel):
    total: int
    new_this_month: int


# =========================================================
# ATTENDANCE
# =========================================================

class DashboardAttendance(BaseModel):
    present_today: int
    total_expected: int
    percentage: float


# =========================================================
# FEES
# =========================================================

class DashboardFees(BaseModel):
    pending_amount: int
    students_due: int


# =========================================================
# REVENUE
# =========================================================

class DashboardRevenue(BaseModel):
    total: int
    change_percentage: float


# =========================================================
# TODAY'S SESSIONS
# =========================================================

class DashboardTodaySessions(BaseModel):
    scheduled: int
    completed: int
    total_active_sessions: int


# =========================================================
# OVERVIEW
# =========================================================

class DashboardOverview(BaseModel):

    students: DashboardStudents

    attendance: DashboardAttendance

    fees: DashboardFees

    revenue: DashboardRevenue

    total_batches: int

    new_batches_this_month: int

    todays_sessions: DashboardTodaySessions


# =========================================================
# UPCOMING SESSIONS
# =========================================================

class UpcomingSessionItem(BaseModel):

    id: str

    title: str

    time: str

    students_count: str

    status: str

    time_of_day: str


class UpcomingSessions(BaseModel):

    display_date: str

    sessions: list[UpcomingSessionItem]


# =========================================================
# PENDING FEES
# =========================================================

class PendingFeeSummary(BaseModel):

    total_amount: int

    students_count: int


class PendingFeeItem(BaseModel):

    id: str

    student_name: str

    batch_name: str

    due_date: str

    amount: int

    status: str

    phone: str

    avatar_uri: str | None


class PendingFees(BaseModel):

    summary: PendingFeeSummary

    fees: list[PendingFeeItem]


# =========================================================
# DASHBOARD DATA
# =========================================================

class DashboardData(BaseModel):

    overview: DashboardOverview

    upcoming_sessions: UpcomingSessions

    pending_fees: PendingFees


# =========================================================
# FINAL RESPONSE
# =========================================================

class DashboardResponse(BaseModel):

    status: str

    message: str

    data: DashboardData