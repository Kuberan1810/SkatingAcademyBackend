from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from docx import Document
from openpyxl import load_workbook
from PIL import Image, ImageOps
import pytesseract

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.student import Student


# =========================================================
# TESSERACT OCR
# =========================================================

TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_PATH
    )

# =========================================================
# SUPPORTED FILE TYPES
# =========================================================

SUPPORTED_EXTENSIONS = {
    ".xlsx",
    ".csv",
    ".docx",
    ".txt",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


# =========================================================
# FIELD ALIASES
# =========================================================

FIELD_ALIASES = {

    # Student
    "full name": "full_name",
    "fullname": "full_name",
    "full_name": "full_name",
    "name": "full_name",
    "student name": "full_name",
    "student_name": "full_name",

    # DOB
    "dob": "dob",
    "date of birth": "dob",
    "dateofbirth": "dob",
    "date_of_birth": "dob",

    # Gender
    "gender": "gender",
    "sex": "gender",

    # Blood group
    "blood group": "blood_group",
    "bloodgroup": "blood_group",
    "blood_group": "blood_group",

    # Batch ID
    "batch id": "batch_id",
    "batchid": "batch_id",
    "batch_id": "batch_id",

    # Batch name
    "batch name": "batch_name",
    "batchname": "batch_name",
    "batch_name": "batch_name",
    "batch": "batch_name",

    # Join date
    "join date": "join_date",
    "joindate": "join_date",
    "join_date": "join_date",

    # Parent
    "parent name": "parent_name",
    "parentname": "parent_name",
    "parent_name": "parent_name",
    "guardian name": "parent_name",

    # Phone
    "phone number": "phone_number",
    "phonenumber": "phone_number",
    "phone_number": "phone_number",
    "phone": "phone_number",
    "mobile": "phone_number",

    # Emergency
    "emergency contact": "emergency_contact",
    "emergencycontact": "emergency_contact",
    "emergency_contact": "emergency_contact",
    "emergency phone": "emergency_contact",

    # Fee
    "monthly fee": "monthly_fee",
    "monthlyfee": "monthly_fee",
    "monthly_fee": "monthly_fee",
    "fee": "monthly_fee",

    # Avatar
    "avatar uri": "avatar_uri",
    "avatar_uri": "avatar_uri",
    "avatar": "avatar_uri",
}


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(value: Any) -> str:

    if value is None:
        return ""

    return str(value).strip()


def normalize_key(value: Any) -> str:

    value = clean_text(
        value
    ).lower()

    value = value.replace(
        "_",
        " ",
    )

    value = value.replace(
        "-",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def map_field_name(
    value: Any,
) -> str | None:

    return FIELD_ALIASES.get(
        normalize_key(value)
    )


# =========================================================
# DATE
# =========================================================

def parse_date_value(
    value: Any,
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

    value = clean_text(value)

    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt,
            ).date()

        except ValueError:
            pass

    return None


# =========================================================
# INTEGER
# =========================================================

def parse_int_value(
    value: Any,
) -> int | None:

    if value is None:
        return None

    text = clean_text(value)

    if not text:
        return None

    text = re.sub(
        r"[₹,\s]",
        "",
        text,
    )

    try:
        return int(
            float(text)
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


# =========================================================
# PHONE
# =========================================================

def clean_phone(
    value: Any,
) -> str:

    value = clean_text(
        value
    )

    return re.sub(
        r"[^\d+]",
        "",
        value,
    )


# =========================================================
# FIND BATCH
# =========================================================

def find_batch(
    db: Session,
    batch_id: int | str | None = None,
    batch_name: str | None = None,
) -> Batch | None:

    # -----------------------------------------------------
    # 1. BATCH ID
    # -----------------------------------------------------

    normalized_batch_id = None

    if batch_id not in (
        None,
        "",
    ):

        try:

            normalized_batch_id = int(
                float(
                    str(
                        batch_id
                    ).strip()
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            normalized_batch_id = None

    # -----------------------------------------------------
    # IMPORTANT
    #
    # ONLY INTEGER goes into Batch.id
    #
    # Never:
    # Batch.id == "Sunday batch"
    # -----------------------------------------------------

    if (
        normalized_batch_id
        is not None
    ):

        batch = (
            db.query(Batch)
            .filter(
                Batch.id
                == normalized_batch_id,

                Batch.is_active.is_(True),
            )
            .first()
        )

        if batch is not None:
            return batch

    # -----------------------------------------------------
    # 2. BATCH NAME
    # -----------------------------------------------------

    if batch_name:

        name = clean_text(
            batch_name
        )

        if name:

            batch = (
                db.query(Batch)
                .filter(
                    Batch.batch_name.ilike(
                        name
                    ),

                    Batch.is_active.is_(True),
                )
                .first()
            )

            if batch is not None:
                return batch

    return None


# =========================================================
# BATCH VALUE FIX
# =========================================================

def fix_batch_values(
    batch_id: Any,
    batch_name: Any,
):

    batch_id = clean_text(
        batch_id
    )

    batch_name = clean_text(
        batch_name
    )

    # Expected:
    #
    # batch_id   = 9
    # batch_name = Sunday batch
    #
    # Possible bad parser:
    #
    # batch_id   = Sunday batch
    # batch_name = 9
    #
    # Automatically swap.

    id_is_numeric = bool(
        batch_id
        and re.fullmatch(
            r"\d+(?:\.0+)?",
            batch_id,
        )
    )

    name_is_numeric = bool(
        batch_name
        and re.fullmatch(
            r"\d+(?:\.0+)?",
            batch_name,
        )
    )

    if (
        not id_is_numeric
        and name_is_numeric
    ):

        batch_id, batch_name = (
            batch_name,
            batch_id,
        )

    return (
        batch_id or None,
        batch_name or None,
    )


# =========================================================
# NORMALIZE RECORD
# =========================================================

def normalize_record(
    record: dict[str, Any],
    db: Session,
) -> dict[str, Any]:

    errors = []
    warnings = []

    # -----------------------------------------------------
    # Normalize field names
    # -----------------------------------------------------

    normalized = {}

    for raw_key, value in record.items():

        field_name = map_field_name(
            raw_key
        )

        if field_name:

            normalized[
                field_name
            ] = value

    # -----------------------------------------------------
    # Student values
    # -----------------------------------------------------

    full_name = clean_text(
        normalized.get(
            "full_name"
        )
    )

    gender = clean_text(
        normalized.get(
            "gender"
        )
    ).title()

    blood_group = (
        clean_text(
            normalized.get(
                "blood_group"
            )
        ).upper()
        or None
    )

    parent_name = clean_text(
        normalized.get(
            "parent_name"
        )
    )

    phone_number = clean_phone(
        normalized.get(
            "phone_number"
        )
    )

    emergency_contact = clean_phone(
        normalized.get(
            "emergency_contact"
        )
    )

    avatar_uri = (
        clean_text(
            normalized.get(
                "avatar_uri"
            )
        )
        or None
    )

    # -----------------------------------------------------
    # Dates
    # -----------------------------------------------------

    dob = parse_date_value(
        normalized.get(
            "dob"
        )
    )

    join_date = parse_date_value(
        normalized.get(
            "join_date"
        )
    )

    # -----------------------------------------------------
    # Batch
    # -----------------------------------------------------

    batch_id_raw, batch_name_raw = (
        fix_batch_values(
            normalized.get(
                "batch_id"
            ),

            normalized.get(
                "batch_name"
            ),
        )
    )

    # Batch ID optional.
    # Batch Name alone works.

    batch = find_batch(
        db=db,
        batch_id=batch_id_raw,
        batch_name=batch_name_raw,
    )

    # -----------------------------------------------------
    # Resolved batch
    # -----------------------------------------------------

    if batch is None:

        errors.append(
            (
                f"Batch '{batch_name_raw}' "
                f"/ ID '{batch_id_raw}' "
                "was not found or inactive"
            )
        )

        resolved_batch_id = None

        resolved_batch_name = (
            batch_name_raw
            or None
        )

    else:

        resolved_batch_id = (
            batch.id
        )

        resolved_batch_name = (
            batch.batch_name
        )

        # If both values supplied,
        # make sure they match.

        if batch_id_raw:

            try:

                given_batch_id = int(
                    float(
                        str(
                            batch_id_raw
                        )
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                given_batch_id = None

            if (
                given_batch_id
                is not None
                and given_batch_id
                != batch.id
            ):

                errors.append(
                    (
                        f"Batch ID "
                        f"{given_batch_id} "
                        f"does not match "
                        f"batch '{batch.batch_name}'"
                    )
                )

    # -----------------------------------------------------
    # Monthly Fee
    # -----------------------------------------------------

    monthly_fee = parse_int_value(
        normalized.get(
            "monthly_fee"
        )
    )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if not full_name:

        errors.append(
            "Full name is required"
        )

    if dob is None:

        errors.append(
            "Valid date of birth is required"
        )

    if gender not in {
        "Male",
        "Female",
        "Other",
    }:

        errors.append(
            "Gender must be Male, Female, or Other"
        )

    if blood_group:

        if blood_group not in {
            "A+",
            "A-",
            "B+",
            "B-",
            "AB+",
            "AB-",
            "O+",
            "O-",
        }:

            errors.append(
                "Invalid blood group"
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
        re.sub(
            r"\D",
            "",
            phone_number,
        )
    ) < 10:

        errors.append(
            "Phone number must contain at least 10 digits"
        )

    if not emergency_contact:

        errors.append(
            "Emergency contact is required"
        )

    elif len(
        re.sub(
            r"\D",
            "",
            emergency_contact,
        )
    ) < 10:

        errors.append(
            "Emergency contact must contain at least 10 digits"
        )

    if (
        monthly_fee is None
        or monthly_fee <= 0
    ):

        errors.append(
            "Monthly fee must be greater than 0"
        )

    # -----------------------------------------------------
    # JOIN DATE
    #
    # If missing → today
    # -----------------------------------------------------

    if join_date is None:

        join_date = date.today()

        warnings.append(
            "Join date was not provided. "
            "Today's date was used."
        )

    # -----------------------------------------------------
    # Duplicate preview warning
    # -----------------------------------------------------

    if phone_number:

        duplicate = (
            db.query(Student)
            .filter(
                Student.phone_number
                == phone_number
            )
            .first()
        )

        if duplicate:

            warnings.append(
                (
                    "Student already exists "
                    "with this phone number"
                )
            )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    if errors:

        record_status = (
            "invalid"
        )

    elif warnings:

        record_status = (
            "warning"
        )

    else:

        record_status = (
            "valid"
        )

    # -----------------------------------------------------
    # Final normalized data
    # -----------------------------------------------------

    return {

        "full_name":
            full_name,

        "dob":
            dob,

        "gender":
            gender,

        "blood_group":
            blood_group,

        "batch_id":
            resolved_batch_id,

        "batch_name":
            resolved_batch_name,

        "join_date":
            join_date,

        "parent_name":
            parent_name,

        "phone_number":
            phone_number,

        "emergency_contact":
            emergency_contact,

        "monthly_fee":
            monthly_fee,

        "avatar_uri":
            avatar_uri,

        "status":
            record_status,

        "errors":
            errors,

        "warnings":
            warnings,
    }


# =========================================================
# XLSX
# =========================================================

def parse_xlsx(
    file_path: str,
):

    workbook = load_workbook(
        filename=file_path,
        data_only=True,
    )

    sheet = workbook.active

    rows = list(
        sheet.iter_rows(
            values_only=True
        )
    )

    if not rows:
        return []

    headers = [
        clean_text(value)
        for value in rows[0]
    ]

    records = []

    for row in rows[1:]:

        if not any(
            value not in (
                None,
                "",
            )
            for value in row
        ):
            continue

        record = {}

        for index, value in enumerate(
            row
        ):

            if (
                index
                < len(headers)
                and headers[index]
            ):

                record[
                    headers[index]
                ] = value

        records.append(
            record
        )

    return records


# =========================================================
# CSV
# =========================================================

def parse_csv(
    file_path: str,
):

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = (
            csv.DictReader(file)
        )

        return [
            dict(row)
            for row in reader
            if any(
                clean_text(value)
                for value
                in row.values()
            )
        ]


# =========================================================
# DOCX
# =========================================================

def parse_docx(
    file_path: str,
):

    document = Document(
        file_path
    )

    # First: actual table
    for table in document.tables:

        if not table.rows:
            continue

        headers = [
            clean_text(
                cell.text
            )
            for cell
            in table.rows[0].cells
        ]

        records = []

        for row in table.rows[1:]:

            values = [
                clean_text(
                    cell.text
                )
                for cell
                in row.cells
            ]

            if not any(values):
                continue

            record = {}

            for index, value in enumerate(
                values
            ):

                if (
                    index
                    < len(headers)
                    and headers[index]
                ):

                    record[
                        headers[index]
                    ] = value

            records.append(
                record
            )

        if records:

            return records

    # Otherwise paragraphs
    text = "\n".join(
        paragraph.text
        for paragraph
        in document.paragraphs
        if paragraph.text.strip()
    )

    return parse_text_records(
        text
    )


# =========================================================
# TEXT
# =========================================================

def parse_text_records(
    text: str,
):

    text = (
        text
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    lines = [
        line.strip()
        for line
        in text.split("\n")
    ]

    lines = [
        line
        for line
        in lines
        if line
    ]

    if not lines:
        return []

    # -----------------------------------------------------
    # Excel pasted as TAB-separated
    # -----------------------------------------------------

    first_parts = re.split(
        r"\t+|\|",
        lines[0],
    )

    mapped_headers = [
        map_field_name(
            item
        )
        for item
        in first_parts
    ]

    if (
        len(mapped_headers)
        >= 5
        and sum(
            item is not None
            for item
            in mapped_headers
        )
        >= 5
    ):

        records = []

        for line in lines[1:]:

            parts = re.split(
                r"\t+|\|",
                line,
            )

            if len(parts) < 5:
                continue

            record = {}

            for index, value in enumerate(
                parts
            ):

                if (
                    index
                    >= len(
                        mapped_headers
                    )
                ):
                    break

                field_name = (
                    mapped_headers[index]
                )

                if field_name:

                    record[
                        field_name
                    ] = value.strip()

            if record:

                records.append(
                    record
                )

        if records:

            return records

    # -----------------------------------------------------
    # Key/value blocks
    # -----------------------------------------------------

    records = []

    current = {}

    field_pattern = re.compile(
        r"^\s*(.+?)\s*[:=]\s*(.*?)\s*$"
    )

    for line in lines:

        # Student 1 / Student 2
        if re.match(
            r"^student\s*\d+",
            line,
            re.IGNORECASE,
        ):

            if current:

                records.append(
                    current
                )

                current = {}

            continue

        match = (
            field_pattern.match(
                line
            )
        )

        if match:

            raw_key = (
                match.group(1)
                .strip()
            )

            raw_value = (
                match.group(2)
                .strip()
            )

            field_name = (
                map_field_name(
                    raw_key
                )
            )

            if field_name:

                current[
                    field_name
                ] = raw_value

    if current:

        records.append(
            current
        )

    return records


def parse_txt(
    file_path: str,
):

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
    ) as file:

        return parse_text_records(
            file.read()
        )


# =========================================================
# IMAGE OCR
# =========================================================

def preprocess_image(
    image: Image.Image,
):

    image = image.convert(
        "L"
    )

    image = ImageOps.autocontrast(
        image
    )

    width, height = (
        image.size
    )

    if width < 1600:

        scale = (
            1600 / width
        )

        image = image.resize(
            (
                int(
                    width * scale
                ),
                int(
                    height * scale
                ),
            )
        )

    return image


def parse_image(
    file_path: str,
):

    try:

        image = Image.open(
            file_path
        )

    except Exception as exc:

        raise ValueError(
            f"Unable to open image: {exc}"
        ) from exc

    image = preprocess_image(
        image
    )

    try:

        text = (
            pytesseract
            .image_to_string(
                image,
                config="--psm 6",
            )
        )

    except Exception as exc:

        raise ValueError(
            (
                "OCR failed. "
                "Install Tesseract OCR "
                "and add it to PATH. "
                f"Details: {exc}"
            )
        ) from exc

    if not text.strip():

        raise ValueError(
            "No readable student data found in image"
        )

    return parse_text_records(
        text
    )


# =========================================================
# PDF
# =========================================================

def parse_pdf(
    file_path: str,
):

    if PdfReader is None:

        raise ValueError(
            "PDF support requires pypdf. "
            "Run: pip install pypdf"
        )

    reader = PdfReader(
        file_path
    )

    pages = []

    for page in reader.pages:

        text = (
            page.extract_text()
            or ""
        )

        if text.strip():

            pages.append(
                text
            )

    text = "\n".join(
        pages
    )

    if not text.strip():

        raise ValueError(
            "No text could be extracted from PDF. "
            "For scanned PDFs, upload the page as PNG/JPG."
        )

    return parse_text_records(
        text
    )


# =========================================================
# MAIN PARSER
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
        return parse_xlsx(
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

    if extension in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        return parse_image(
            file_path
        )

    if extension == ".pdf":
        return parse_pdf(
            file_path
        )

    raise ValueError(
        "Unsupported file type. "
        "Supported: XLSX, CSV, DOCX, TXT, PDF, "
        "JPG, JPEG, PNG, WEBP"
    )