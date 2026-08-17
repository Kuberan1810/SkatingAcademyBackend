from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.batch import Batch
from app.models.session import Session as SessionModel
from app.models.fee import FeePayment


# =========================================================
# SEARCH CONFIG
# =========================================================

DEFAULT_LIMIT = 20
MAX_LIMIT = 50


# =========================================================
# NORMALIZE SEARCH QUERY
# =========================================================

def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


# =========================================================
# SEARCH SERVICE
# =========================================================

def global_search(
    db: Session,
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:

    query = normalize_query(query)

    if not query:
        return []

    limit = min(max(limit, 1), MAX_LIMIT)

    search_pattern = f"%{query}%"

    results: list[dict[str, Any]] = []

    # =====================================================
    # 1. STUDENTS
    # =====================================================

    students = (
        db.query(Student, Batch)
        .join(Batch, Student.batch_id == Batch.id)
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
            or_(
                Student.full_name.ilike(search_pattern),
                Student.phone_number.ilike(search_pattern),
                Student.parent_name.ilike(search_pattern),
                Batch.batch_name.ilike(search_pattern),
                Batch.location.ilike(search_pattern),
            ),
        )
        .order_by(Student.full_name.asc())
        .limit(limit)
        .all()
    )

    for student, batch in students:
        name = (student.full_name or "").lower()
        phone = (student.phone_number or "").lower()
        parent = (student.parent_name or "").lower()
        batch_name = (batch.batch_name or "").lower()
        location = (batch.location or "").lower()

        if name == query:
            score = 100
        elif name.startswith(query):
            score = 90
        elif query in name:
            score = 80
        elif query in phone:
            score = 70
        elif query in parent:
            score = 60
        elif query in batch_name:
            score = 50
        elif query in location:
            score = 40
        else:
            score = 30

        results.append(
            {
                "_score": score,
                "id": str(student.id),
                "type": "student",
                "student_id": student.id,
                "batch_id": batch.id,
                "title": student.full_name,
                "subtitle": batch.batch_name,
                "meta": student.phone_number,
                "image": student.avatar_uri,
            }
        )

    # =====================================================
    # 2. BATCHES
    # =====================================================

    batches = (
        db.query(Batch)
        .filter(
            Batch.is_active.is_(True),
            or_(
                Batch.batch_name.ilike(search_pattern),
                Batch.location.ilike(search_pattern),
                Batch.level.ilike(search_pattern),
                Batch.class_type.ilike(search_pattern),
            ),
        )
        .order_by(Batch.batch_name.asc())
        .limit(limit)
        .all()
    )

    for batch in batches:
        batch_name = (batch.batch_name or "").lower()
        location = (batch.location or "").lower()
        level = (batch.level or "").lower()
        class_type = (batch.class_type or "").lower()

        if batch_name == query:
            score = 95
        elif batch_name.startswith(query):
            score = 85
        elif query in batch_name:
            score = 75
        elif query in location:
            score = 60
        elif query in level:
            score = 50
        elif query in class_type:
            score = 40
        else:
            score = 30

        results.append(
            {
                "_score": score,
                "id": str(batch.id),
                "type": "batch",
                "student_id": None,
                "batch_id": batch.id,
                "title": batch.batch_name,
                "subtitle": batch.location,
                "meta": f"{batch.level} • {batch.class_type}",
                "image": None,
            }
        )

    # =====================================================
    # 3. FEE PAYMENTS
    # =====================================================

    payments = (
        db.query(FeePayment, Student, Batch)
        .join(Student, FeePayment.student_id == Student.id)
        .join(Batch, Student.batch_id == Batch.id)
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
            or_(
                Student.full_name.ilike(search_pattern),
                Student.phone_number.ilike(search_pattern),
                Batch.batch_name.ilike(search_pattern),
                Batch.location.ilike(search_pattern),
            ),
        )
        .order_by(FeePayment.payment_date.desc())
        .limit(limit)
        .all()
    )

    for payment, student, batch in payments:
        student_name = student.full_name or ""
        batch_name = batch.batch_name or ""
        search_student_name = student_name.lower()
        search_batch_name = batch_name.lower()

        if search_student_name == query:
            score = 65
        elif search_student_name.startswith(query):
            score = 60
        elif query in search_student_name:
            score = 55
        elif query in search_batch_name:
            score = 45
        else:
            score = 35

        try:
            fee_month_name = __import__("calendar").month_name[payment.fee_month]
        except Exception:
            fee_month_name = str(payment.fee_month)

        results.append(
            {
                "_score": score,
                "id": str(payment.id),
                "type": "payment",
                "student_id": student.id,
                "batch_id": batch.id,
                "title": student_name,
                "subtitle": f"{fee_month_name} {payment.fee_year} Fee",
                "meta": f"₹{int(payment.net_payable):,} • {payment.payment_method}",
                "image": student.avatar_uri,
            }
        )

    # =====================================================
    # 4. SESSIONS
    # =====================================================

    sessions = (
        db.query(SessionModel, Batch)
        .join(Batch, SessionModel.batch_id == Batch.id)
        .filter(
            Batch.is_active.is_(True),
            or_(
                Batch.batch_name.ilike(search_pattern),
                Batch.location.ilike(search_pattern),
            ),
        )
        .order_by(SessionModel.session_date.desc())
        .limit(limit)
        .all()
    )

    for session, batch in sessions:
        batch_name = (batch.batch_name or "").lower()
        location = (batch.location or "").lower()

        if batch_name == query:
            score = 55
        elif batch_name.startswith(query):
            score = 50
        elif query in batch_name:
            score = 45
        elif query in location:
            score = 40
        else:
            score = 30

        session_date = (
            session.session_date.strftime("%d %b %Y") if session.session_date else ""
        )
        session_status = str(session.status) if session.status else ""

        results.append(
            {
                "_score": score,
                "id": str(session.id),
                "type": "session",
                "student_id": None,
                "batch_id": batch.id,
                "title": batch.batch_name,
                "subtitle": batch.location,
                "meta": f"{session_date} • {session_status}",
                "image": None,
            }
        )

    # =====================================================
    # 5. GLOBAL RANKING
    # =====================================================

    results.sort(key=lambda item: (-item["_score"], item["title"].lower()))

    # =====================================================
    # 6. REMOVE INTERNAL SCORE & RETURN TOP RESULTS
    # =====================================================

    final_results = []
    for result in results[:limit]:
        result.pop("_score", None)
        final_results.append(result)

    return final_results