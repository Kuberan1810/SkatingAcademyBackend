import calendar
from datetime import date
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.fee import FeePayment
from app.models.student import Student


def calculate_student_fee_summary(
    db: Session,
    student: Student,
    batch: Batch,
    today: date | None = None,
    all_payments: list[FeePayment] | None = None,
) -> dict:
    """
    Calculates detailed payment status, last payment info, and cumulative
    overdue/pending months count and amount for a student.
    """
    if today is None:
        today = date.today()

    current_month = today.month
    current_year = today.year

    monthly_fee = int(
        student.monthly_fee
        if (student.monthly_fee is not None and student.monthly_fee > 0)
        else (batch.monthly_fee or 0)
    )

    # 1. Fetch payments if not passed
    if all_payments is None:
        payments = (
            db.query(FeePayment)
            .filter(FeePayment.student_id == student.id)
            .order_by(FeePayment.payment_date.desc(), FeePayment.id.desc())
            .all()
        )
    else:
        payments = sorted(
            [p for p in all_payments if p.student_id == student.id],
            key=lambda x: (x.payment_date or date.min, x.id or 0),
            reverse=True,
        )

    # 2. Current month payment status
    current_month_payments = [
        p for p in payments
        if p.fee_month == current_month and p.fee_year == current_year
    ]
    current_paid_amount = sum(int(p.net_payable or 0) for p in current_month_payments)
    is_current_paid = current_paid_amount >= monthly_fee

    current_paid_date = None
    if current_month_payments and current_month_payments[0].payment_date:
        current_paid_date = current_month_payments[0].payment_date.strftime("%d %b %Y")

    due_date = date(current_year, current_month, 1)
    if is_current_paid:
        payment_status = "paid"
    elif today > due_date:
        payment_status = "overdue"
    elif today == due_date:
        payment_status = "due_today"
    else:
        payment_status = "unpaid"

    # 3. Last payment ever made
    last_payment = payments[0] if payments else None
    last_paid_date = None
    last_paid_month = None
    last_payment_dict = None

    if last_payment:
        if last_payment.payment_date:
            last_paid_date = last_payment.payment_date.strftime("%d %b %Y")

        if last_payment.fee_month and 1 <= last_payment.fee_month <= 12:
            m_name = calendar.month_name[last_payment.fee_month]
            last_paid_month = f"{m_name} {last_payment.fee_year or ''}".strip()

        last_payment_dict = {
            "amount": int(last_payment.net_payable or 0),
            "fee_month": last_payment.fee_month or current_month,
            "fee_year": last_payment.fee_year or current_year,
            "paid_date": last_paid_date,
        }

    # 4. Previous month status
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    # Check join date
    join_date = student.join_date or (student.created_at.date() if student.created_at else date(current_year, current_month, 1))
    join_year_month = (join_date.year, join_date.month)
    prev_year_month = (prev_year, prev_month)

    prev_month_payments = [
        p for p in payments
        if p.fee_month == prev_month and p.fee_year == prev_year
    ]
    prev_paid_amount = sum(int(p.net_payable or 0) for p in prev_month_payments)

    if prev_year_month < join_year_month:
        previous_month_status = "not_joined"
    elif prev_paid_amount >= monthly_fee:
        previous_month_status = "paid"
    else:
        previous_month_status = "unpaid"

    # 5. Cumulative unpaid months and total pending balance
    paid_map = {}
    for p in payments:
        if p.fee_year and p.fee_month:
            k = (p.fee_year, p.fee_month)
            paid_map[k] = paid_map.get(k, 0) + int(p.net_payable or 0)

    unpaid_months_count = 0
    total_pending_amount = 0

    curr_y = join_date.year
    curr_m = join_date.month

    while (curr_y < current_year) or (curr_y == current_year and curr_m <= current_month):
        paid_for_m = paid_map.get((curr_y, curr_m), 0)
        due_for_m = max(0, monthly_fee - paid_for_m)
        if due_for_m > 0:
            unpaid_months_count += 1
            total_pending_amount += due_for_m

        if curr_m == 12:
            curr_y += 1
            curr_m = 1
        else:
            curr_m += 1

    return {
        "payment_status": payment_status,
        "amount": monthly_fee,
        "paid_date": current_paid_date,
        "last_paid_date": last_paid_date,
        "last_paid_month": last_paid_month,
        "last_payment": last_payment_dict,
        "unpaid_months_count": unpaid_months_count,
        "total_pending_amount": total_pending_amount,
        "previous_month_status": previous_month_status,
    }
