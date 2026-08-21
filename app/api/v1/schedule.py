from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db
from app.models.admin import Admin
from app.models.batch import Batch
from app.models.session import Session as SessionModel
from app.models.batch_schedule_exception import BatchScheduleException
from app.schemas.schedule import CompensationCreate, CompensationResponse

router = APIRouter(
    prefix="/schedule",
    tags=["Schedule"],
)


def find_recent_missed_training_date(
    db: Session,
    batch: Batch,
    reference_date: date,
    lookback_days: int = 30,
) -> date | None:
    """
    Finds the most recent scheduled training day for this batch
    where no session was conducted.
    """
    batch_days = {
        str(d).strip().lower()
        for d in (batch.training_days or [])
        if d
    }

    if not batch_days:
        return None

    weekday_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    for offset in range(1, lookback_days + 1):
        candidate_date = reference_date - timedelta(days=offset)
        candidate_day_name = weekday_names[candidate_date.weekday()]

        if candidate_day_name in batch_days:
            # Check if a session was conducted for this batch on candidate_date
            session_exists = (
                db.query(SessionModel)
                .filter(
                    SessionModel.batch_id == batch.id,
                    SessionModel.session_date == candidate_date,
                )
                .first()
            ) is not None

            if not session_exists:
                return candidate_date

    return None


@router.post(
    "/compensation",
    response_model=CompensationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_compensation_schedule(
    data: CompensationCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    # 1. Verify batch exists and is active
    batch = (
        db.query(Batch)
        .filter(
            Batch.id == data.batch_id,
            Batch.is_active.is_(True),
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or inactive",
        )

    # 2. Verify dates are different if original_date is provided
    if data.original_date is not None and data.original_date == data.compensation_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Compensation date must be different from original date",
        )

    # 3. Check duplicate approved compensation schedule for same batch and compensation_date
    existing_exception = (
        db.query(BatchScheduleException)
        .filter(
            BatchScheduleException.batch_id == data.batch_id,
            BatchScheduleException.compensation_date == data.compensation_date,
            BatchScheduleException.status == "APPROVED",
        )
        .first()
    )

    if existing_exception is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An approved compensation/extra class is already scheduled for this batch on this date",
        )

    # 4. Auto-detect missed training date if original_date was not provided
    resolved_original_date = data.original_date
    if resolved_original_date is None:
        resolved_original_date = find_recent_missed_training_date(
            db=db,
            batch=batch,
            reference_date=data.compensation_date,
        )

    # 5. Default reason if not provided
    resolved_reason = data.reason
    if not resolved_reason:
        if resolved_original_date:
            resolved_reason = f"Compensation for missed class on {resolved_original_date.strftime('%d %b %Y')}"
        else:
            resolved_reason = "Extra Class"

    # 6. Create record
    schedule_exception = BatchScheduleException(
        batch_id=data.batch_id,
        original_date=resolved_original_date,
        compensation_date=data.compensation_date,
        reason=resolved_reason,
        status="APPROVED",
        created_by=current_admin.id,
    )

    db.add(schedule_exception)
    db.commit()
    db.refresh(schedule_exception)

    return {
        "status": "success",
        "message": "Compensation/Extra class scheduled successfully",
        "data": {
            "id": schedule_exception.id,
            "batch_id": batch.id,
            "batch_name": batch.batch_name,
            "original_date": schedule_exception.original_date,
            "compensation_date": schedule_exception.compensation_date,
            "reason": schedule_exception.reason,
            "status": schedule_exception.status,
        },
    }


@router.get(
    "/missed-classes/{batch_id}",
)
def get_missed_classes(
    batch_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    batch = (
        db.query(Batch)
        .filter(
            Batch.id == batch_id,
            Batch.is_active.is_(True),
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or inactive",
        )

    batch_days = {
        str(d).strip().lower()
        for d in (batch.training_days or [])
        if d
    }

    weekday_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    today = date.today()
    missed_list = []

    # Look back over the past 30 days
    for offset in range(1, 31):
        candidate_date = today - timedelta(days=offset)
        candidate_day_name = weekday_names[candidate_date.weekday()]

        if candidate_day_name in batch_days:
            session_exists = (
                db.query(SessionModel)
                .filter(
                    SessionModel.batch_id == batch.id,
                    SessionModel.session_date == candidate_date,
                )
                .first()
            ) is not None

            if not session_exists:
                # Check if a compensation was already scheduled for this original date
                already_compensated = (
                    db.query(BatchScheduleException)
                    .filter(
                        BatchScheduleException.batch_id == batch.id,
                        BatchScheduleException.original_date == candidate_date,
                        BatchScheduleException.status == "APPROVED",
                    )
                    .first()
                ) is not None

                missed_list.append({
                    "date": candidate_date.isoformat(),
                    "date_formatted": candidate_date.strftime("%d %b %Y"),
                    "day": candidate_date.strftime("%A"),
                    "already_compensated": already_compensated,
                })

    return {
        "status": "success",
        "message": "Missed classes fetched successfully",
        "data": {
            "batch_id": batch.id,
            "batch_name": batch.batch_name,
            "missed_classes": missed_list,
        }
    }

