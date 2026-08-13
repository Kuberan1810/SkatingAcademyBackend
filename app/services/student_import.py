from datetime import date, datetime
from pathlib import Path
import re

from dateutil import parser as date_parser

from openpyxl import load_workbook
from docx import Document

from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.student import Student


# =========================================================
# FIELD ALIASES
# =========================================================

FIELD_ALIASES = {

    "full_name": {
        "full name",
        "student name",
        "name",
        "student full name",
    },

    "dob": {
        "dob",
        "date of birth",
        "birth date",
        "birthdate",
    },

    "gender": {
        "gender",
        "sex",
    },

    "blood_group": {
        "blood group",
        "blood",
        "blood type",
    },

    "batch": {
        "batch",
        "batch name",
        "class",
        "training batch",
    },

    "join_date": {
        "join date",
        "joining date",
        "date joined",
    },

    "parent_name": {
        "parent",
        "parent name",
        "father name",
        "mother name",
        "guardian name",
    },

    "phone_number": {
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "contact",
    },

    "emergency_contact": {
        "emergency",
        "emergency contact",
        "emergency phone",
        "emergency number",
    },

    "monthly_fee": {
        "monthly fee",
        "monthly fees",
        "fee",
        "fees",
    },

    "avatar_uri": {
        "avatar",
        "avatar uri",
        "profile image",
        "image",
        "image url",
    },
}


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(
    value,
) -> str:

    if value is None:
        return ""

    value = str(
        value
    ).strip().lower()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value


# =========================================================
# NORMALIZE HEADER
# =========================================================

def normalize_header(
    header,
) -> str | None:

    normalized = normalize_text(
        header
    )

    for field_name, aliases in FIELD_ALIASES.items():

        if normalized in aliases:
            return field_name

    return None


# =========================================================
# DATE PARSER
# =========================================================

def parse_date(
    value,
) -> date | None:

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    value = str(
        value
    ).strip()

    if not value:
        return None

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d-%m-%y",
        "%d/%m/%y",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt,
            ).date()

        except ValueError:
            continue

    try:

        return date_parser.parse(
            value,
            dayfirst=True,
        ).date()

    except Exception:
        return None


# =========================================================
# INTEGER PARSER
# =========================================================

def parse_integer(
    value,
) -> int | None:

    if value is None:
        return None

    if isinstance(
        value,
        int,
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        return int(value)

    value = str(
        value
    ).strip()

    if not value:
        return None

    value = re.sub(
        r"[₹,\s]",
        "",
        value,
    )

    try:
        return int(
            float(value)
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


# =========================================================
# PHONE NORMALIZER
# =========================================================

def normalize_phone(
    value,
) -> str | None:

    if value is None:
        return None

    value = str(
        value
    ).strip()

    if not value:
        return None

    # Keep only numbers
    value = re.sub(
        r"\D",
        "",
        value,
    )

    # Remove India country code
    if value.startswith(
        "91"
    ) and len(value) == 12:

        value = value[2:]

    return value


# =========================================================
# EXCEL PARSER
# =========================================================

def parse_excel(
    file_path: str,
) -> list[dict]:

    workbook = load_workbook(
        file_path,
        data_only=True,
    )

    worksheet = workbook.active

    rows = list(
        worksheet.iter_rows(
            values_only=True
        )
    )

    if not rows:
        return []

    headers = rows[0]

    normalized_headers = []

    for header in headers:

        normalized_headers.append(
            normalize_header(
                header
            )
        )

    records = []

    for row_number, row in enumerate(
        rows[1:],
        start=2,
    ):

        # Skip completely empty rows

        if not any(
            value is not None
            and str(value).strip()
            for value in row
        ):
            continue

        record = {
            "row_number": row_number
        }

        for index, value in enumerate(
            row
        ):

            if index >= len(
                normalized_headers
            ):
                continue

            field_name = (
                normalized_headers[index]
            )

            if field_name is None:
                continue

            record[
                field_name
            ] = value

        records.append(
            record
        )

    return records


# =========================================================
# CSV PARSER
# =========================================================

def parse_csv(
    file_path: str,
) -> list[dict]:

    import csv

    records = []

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row_number, row in enumerate(
            reader,
            start=2,
        ):

            record = {
                "row_number":
                    row_number
            }

            for key, value in row.items():

                field_name = (
                    normalize_header(
                        key
                    )
                )

                if field_name:

                    record[
                        field_name
                    ] = value

            records.append(
                record
            )

    return records


# =========================================================
# DOCX PARSER
# =========================================================

def parse_docx(
    file_path: str,
) -> list[dict]:

    document = Document(
        file_path
    )

    text_lines = []

    for paragraph in (
        document.paragraphs
    ):

        text = (
            paragraph.text
            .strip()
        )

        if text:
            text_lines.append(
                text
            )

    # ---------------------------------------------
    # Check tables first
    # ---------------------------------------------

    records = []

    for table in document.tables:

        table_rows = []

        for row in table.rows:

            values = [
                cell.text.strip()
                for cell in row.cells
            ]

            table_rows.append(
                values
            )

        if len(table_rows) < 2:
            continue

        headers = [
            normalize_header(
                header
            )
            for header in table_rows[0]
        ]

        for row_number, row in enumerate(
            table_rows[1:],
            start=2,
        ):

            record = {
                "row_number":
                    row_number
            }

            for index, value in enumerate(
                row
            ):

                if index >= len(
                    headers
                ):
                    continue

                field_name = (
                    headers[index]
                )

                if field_name:

                    record[
                        field_name
                    ] = value

            records.append(
                record
            )

    if records:
        return records

    # ---------------------------------------------
    # Key : Value document
    # ---------------------------------------------

    data = {}

    for line in text_lines:

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        field_name = (
            normalize_header(
                key
            )
        )

        if field_name:

            data[
                field_name
            ] = value.strip()

    if data:

        return [
            {
                "row_number": 1,
                **data,
            }
        ]

    return []


# =========================================================
# TXT PARSER
# =========================================================

def parse_txt(
    file_path: str,
) -> list[dict]:

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
    ) as file:

        text = file.read()

    data = {}

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        field_name = (
            normalize_header(
                key
            )
        )

        if field_name:

            data[
                field_name
            ] = value.strip()

    if not data:
        return []

    return [
        {
            "row_number": 1,
            **data,
        }
    ]


# =========================================================
# FILE DISPATCHER
# =========================================================

def parse_file(
    file_path: str,
):

    extension = (
        Path(file_path)
        .suffix
        .lower()
    )

    if extension == ".xlsx":

        return parse_excel(
            file_path
        )

    if extension == ".csv":

        return parse_csv(
            file_path
        )

    if extension == ".docx":

        return parse_docx(
            file_path
        )

    if extension == ".txt":

        return parse_txt(
            file_path
        )

    raise ValueError(
        "Unsupported file type. "
        "Use XLSX, CSV, DOCX or TXT."
    )


# =========================================================
# BATCH MATCHING
# =========================================================

def find_batch(
    db: Session,
    batch_id: int | None = None,
    batch_name: str | None = None,
):
    # 1. Batch ID is the primary lookup
    if batch_id is not None:
        batch = (
            db.query(Batch)
            .filter(
                Batch.id == batch_id,
                Batch.is_active.is_(True),
            )
            .first()
        )

        if batch:
            return batch

    # 2. Fallback to batch name
    if batch_name:
        batch = (
            db.query(Batch)
            .filter(
                Batch.batch_name == batch_name,
                Batch.is_active.is_(True),
            )
            .first()
        )

        if batch:
            return batch

    return None


# =========================================================
# DUPLICATE CHECK
# =========================================================

def find_duplicate_student(
    db: Session,
    phone_number: str | None,
    full_name: str | None,
    dob: date | None,
):

    if phone_number:

        existing = (
            db.query(Student)
            .filter(
                Student.phone_number
                == phone_number
            )
            .first()
        )

        if existing:
            return existing

    if full_name and dob:

        existing = (
            db.query(Student)
            .filter(
                Student.full_name.ilike(
                    full_name
                ),
                Student.dob == dob,
            )
            .first()
        )

        if existing:
            return existing

    return None


# =========================================================
# NORMALIZE RECORD
# =========================================================

def normalize_record(
    raw: dict,
    db: Session,
):

    errors = []
    warnings = []

    row_number = int(
        raw.get(
            "row_number",
            1,
        )
    )

    full_name = (
        str(
            raw.get(
                "full_name",
                ""
            )
        ).strip()
        if raw.get(
            "full_name"
        ) is not None
        else None
    )

    dob = parse_date(
        raw.get(
            "dob"
        )
    )

    gender = (
        str(
            raw.get(
                "gender"
            )
        ).strip()
        if raw.get(
            "gender"
        ) is not None
        else None
    )

    blood_group = (
        str(
            raw.get(
                "blood_group"
            )
        ).strip()
        if raw.get(
            "blood_group"
        ) is not None
        else None
    )

    batch_name = (
        str(
            raw.get(
                "batch"
            )
        ).strip()
        if raw.get(
            "batch"
        ) is not None
        else None
    )

    join_date = parse_date(
        raw.get(
            "join_date"
        )
    )

    parent_name = (
        str(
            raw.get(
                "parent_name"
            )
        ).strip()
        if raw.get(
            "parent_name"
        ) is not None
        else None
    )

    phone_number = normalize_phone(
        raw.get(
            "phone_number"
        )
    )

    emergency_contact = normalize_phone(
        raw.get(
            "emergency_contact"
        )
    )

    monthly_fee = parse_integer(
        raw.get(
            "monthly_fee"
        )
    )

    avatar_uri = (
        str(
            raw.get(
                "avatar_uri"
            )
        ).strip()
        if raw.get(
            "avatar_uri"
        ) is not None
        else None
    )

    # =====================================================
    # REQUIRED FIELD VALIDATION
    # =====================================================

    if not full_name:

        errors.append(
            "Full name is required"
        )

    if not dob:

        errors.append(
            "Valid date of birth is required"
        )

    if not gender:

        errors.append(
            "Gender is required"
        )

    if not batch_name:

        errors.append(
            "Batch is required"
        )

    if not join_date:

        errors.append(
            "Valid join date is required"
        )

    if not parent_name:

        errors.append(
            "Parent name is required"
        )

    if not phone_number:

        errors.append(
            "Phone number is required"
        )

    elif len(
        phone_number
    ) != 10:

        errors.append(
            "Phone number must contain 10 digits"
        )

    if not emergency_contact:

        errors.append(
            "Emergency contact is required"
        )

    elif len(
        emergency_contact
    ) != 10:

        errors.append(
            "Emergency contact must contain 10 digits"
        )

    if monthly_fee is None:

        errors.append(
            "Monthly fee is required"
        )

    elif monthly_fee <= 0:

        errors.append(
            "Monthly fee must be greater than 0"
        )

    # =====================================================
    # BATCH
    # =====================================================

    batch = None

    if batch_name:

        batch = find_batch(
            db,
            batch_name
        )

        if batch is None:

            errors.append(
                f"Batch '{batch_name}' "
                "was not found"
            )

    # =====================================================
    # DUPLICATE
    # =====================================================

    duplicate = find_duplicate_student(
        db,
        phone_number,
        full_name,
        dob,
    )

    if duplicate:

        warnings.append(
            (
                f"Possible duplicate student. "
                f"Existing student ID: "
                f"{duplicate.id}"
            )
        )

    # =====================================================
    # AGE
    # =====================================================

    if dob:

        today = date.today()

        age = (
            today.year
            - dob.year
            - (
                (
                    today.month,
                    today.day
                )
                < (
                    dob.month,
                    dob.day
                )
            )
        )

        if age < 3:

            errors.append(
                "Student age must be at least 3 years"
            )

    # =====================================================
    # GENDER
    # =====================================================

    valid_genders = {
        "male",
        "female",
        "other",
    }

    if gender:

        if normalize_text(
            gender
        ) not in valid_genders:

            errors.append(
                "Invalid gender. "
                "Use Male, Female or Other"
            )

    # =====================================================
    # BLOOD GROUP
    # =====================================================

    valid_blood_groups = {
        "a+",
        "a-",
        "b+",
        "b-",
        "ab+",
        "ab-",
        "o+",
        "o-",
    }

    if blood_group:

        if normalize_text(
            blood_group
        ) not in valid_blood_groups:

            errors.append(
                "Invalid blood group"
            )

    # =====================================================
    # STATUS
    # =====================================================

    if errors:

        status = "invalid"

    elif warnings:

        status = "warning"

    else:

        status = "valid"

    return {
        "row_number": row_number,

        "full_name": full_name,

        "dob": dob,

        "gender": gender,

        "blood_group": blood_group,

        "batch_id": (
            batch.id
            if batch
            else None
        ),

        "batch_name": (
            batch.batch_name
            if batch
            else batch_name
        ),

        "join_date": join_date,

        "parent_name": parent_name,

        "phone_number": phone_number,

        "emergency_contact":
            emergency_contact,

        "monthly_fee":
            monthly_fee,

        "avatar_uri":
            avatar_uri,

        "status":
            status,

        "errors":
            errors,

        "warnings":
            warnings,
    }