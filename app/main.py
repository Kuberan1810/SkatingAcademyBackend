from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.database.session import engine

from app.api.v1.auth import router as auth_router
from app.api.v1.batches import router as batches_router
from app.api.v1.students import router as students_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.fees import router as fees_router

from app.api.v1.dashboard import (
    router as dashboard_router,
)

from app.api.v1.batches_page import (
    router as batches_page_router,
)
from app.api.v1.settings import (
    router as settings_router,
)
from app.api.v1.search import (
    router as search_router,
)
from app.api.v1.fee_export import (
    router as fee_export_router,
)
from app.api.v1.reports import (
    router as reports_router,
)
from app.api.v1.report_exports import (
    router as report_exports_router,
)

from app.api.v1.student_import import (
    router as student_import_router,
)
from app.api.v1.pending_fees import router as pending_fees_router
from app.api.v1.schedule import router as schedule_router


app = FastAPI(
    title="Skating Academy API",
    version="1.0.0",
)

# =========================================================
# CORS MIDDLEWARE CONTROL
# =========================================================

origins = [
    "http://localhost:8081",
    "http://localhost:19006",
    "http://localhost:8000",
    "http://127.0.0.1:8081",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Skating Academy Backend Running ",
        "algorithm": settings.ALGORITHM,
    }


@app.get("/health/db")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "PostgreSQL",
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }


app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    batches_router,
    prefix="/api/v1",
)

app.include_router(
    students_router,
    prefix="/api/v1",
)


app.include_router(
    sessions_router,
    prefix="/api/v1",
)

app.include_router(
    attendance_router,
    prefix="/api/v1",
)

app.include_router(
    fees_router,
    prefix="/api/v1",
)
app.include_router(
    fee_export_router,
    prefix="/api/v1",
)

app.include_router(
    pending_fees_router,
    prefix="/api/v1",
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
)

app.include_router(
    batches_page_router,
    prefix="/api/v1",
)


app.include_router(
    settings_router,
    prefix="/api/v1",
)


app.include_router(
    search_router,
    prefix="/api/v1",
)


app.include_router(
    reports_router,
    prefix="/api/v1",
)

app.include_router(
    report_exports_router,
    prefix="/api/v1",
)

app.include_router(
    student_import_router,
    prefix="/api/v1",
)

app.include_router(
    schedule_router,
    prefix="/api/v1",
)



