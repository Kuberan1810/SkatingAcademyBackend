from datetime import date, datetime, time
import calendar
import csv
from io import BytesIO, StringIO

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from fastapi.responses import StreamingResponse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin
from app.models.student import Student
from app.models.batch import Batch
from app.models.session import Session as SessionModel
from app.models.attendance import Attendance
from app.models.fee import FeePayment


router = APIRouter(
    prefix="/reports",
    tags=["Report Exports"],
)


# =========================================================
# HELPERS
# =========================================================


def format_date(value):

    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime(
            "%d %b %Y %I:%M %p"
        )

    if isinstance(value, date):
        return value.strftime(
            "%d %b %Y"
        )

    return str(value)


def calculate_age(dob):

    if not dob:
        return None

    today = date.today()

    age = (
        today.year
        - dob.year
        - (
            (today.month, today.day)
            < (dob.month, dob.day)
        )
    )

    return age


def month_name(month):

    if month is None:
        return ""

    if 1 <= month <= 12:
        return calendar.month_name[month]

    return ""


def get_next_month(year, month):

    if month == 12:

        return date(
            year + 1,
            1,
            1,
        )

    return date(
        year,
        month + 1,
        1,
    )


# =========================================================
# GENERIC EXCEL EXPORT
# =========================================================


def create_excel(
    sheets: dict,
):

    from openpyxl import Workbook

    from openpyxl.styles import (
        Font,
        Alignment,
    )

    from openpyxl.utils import (
        get_column_letter,
    )

    workbook = Workbook()

    first_sheet = True

    for sheet_name, rows in sheets.items():

        if first_sheet:

            worksheet = workbook.active

            worksheet.title = sheet_name

            first_sheet = False

        else:

            worksheet = (
                workbook.create_sheet(
                    sheet_name
                )
            )

        if not rows:

            worksheet["A1"] = (
                "No data available"
            )

            continue

        headers = list(
            rows[0].keys()
        )

        # -------------------------------------------------
        # HEADERS
        # -------------------------------------------------

        for column_index, header in enumerate(
            headers,
            start=1,
        ):

            cell = worksheet.cell(
                row=1,
                column=column_index,
            )

            cell.value = header

            cell.font = Font(
                bold=True
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        # -------------------------------------------------
        # DATA
        # -------------------------------------------------

        for row_index, row in enumerate(
            rows,
            start=2,
        ):

            for column_index, header in enumerate(
                headers,
                start=1,
            ):

                worksheet.cell(
                    row=row_index,
                    column=column_index,
                ).value = row.get(
                    header,
                    "",
                )

        # -------------------------------------------------
        # FREEZE
        # -------------------------------------------------

        worksheet.freeze_panes = "A2"

        # -------------------------------------------------
        # WIDTH
        # -------------------------------------------------

        for column_cells in (
            worksheet.columns
        ):

            max_length = 0

            column_letter = (
                get_column_letter(
                    column_cells[0].column
                )
            )

            for cell in column_cells:

                length = len(
                    str(
                        cell.value
                        or ""
                    )
                )

                max_length = max(
                    max_length,
                    length,
                )

            worksheet.column_dimensions[
                column_letter
            ].width = min(
                max(
                    max_length + 2,
                    12,
                ),
                40,
            )

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    return output


# =========================================================
# GENERIC CSV EXPORT
# =========================================================


def create_csv(rows):

    output = StringIO()

    if not rows:

        output.write(
            "No data available\n"
        )

    else:

        writer = csv.DictWriter(
            output,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()

        writer.writerows(rows)

    output.seek(0)

    return output


# =========================================================
# GENERIC PDF EXPORT
# =========================================================


def create_pdf(
    title,
    rows,
):

    from reportlab.lib import colors

    from reportlab.lib.pagesizes import (
        A4,
        landscape,
    )

    from reportlab.lib.styles import (
        getSampleStyleSheet,
    )

    from reportlab.lib.units import mm

    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    styles = (
        getSampleStyleSheet()
    )

    story = []

    story.append(
        Paragraph(
            title,
            styles["Title"],
        )
    )

    story.append(
        Spacer(
            1,
            5 * mm,
        )
    )

    if not rows:

        story.append(
            Paragraph(
                "No data available",
                styles["Normal"],
            )
        )

        document.build(story)

        output.seek(0)

        return output

    headers = list(
        rows[0].keys()
    )

    from reportlab.lib.styles import ParagraphStyle

    num_cols = max(len(headers), 1)
    col_width = (281 * mm) / num_cols

    header_cell_style = ParagraphStyle(
        "GenericHeaderCell",
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.5,
        textColor=colors.white,
        alignment=1,
    )

    cell_style = ParagraphStyle(
        "GenericBodyCell",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#1F2937"),
        alignment=1,
    )

    table_data = [
        [
            Paragraph(str(h), header_cell_style)
            for h in headers
        ]
    ]

    for row in rows:
        table_data.append(
            [
                Paragraph(
                    str(
                        row.get(
                            header,
                            "",
                        )
                    )[:100],
                    cell_style,
                )
                for header in headers
            ]
        )

    table = Table(
        table_data,
        colWidths=[col_width] * num_cols,
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#111827"
                    ),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#CBD5E1"),
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2.5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2.5,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor(
                            "#F9FAFB"
                        ),
                    ],
                ),
            ]
        )
    )

    story.append(table)

    document.build(story)

    output.seek(0)

    return output


# =========================================================
# STUDENT PDF EXPORT
# =========================================================


def create_student_pdf(
    batch_name: str,
    location: str,
    status_filter: str | None,
    students_data: list[dict],
    is_multi_batch: bool = False,
    batches_data: dict | None = None,
):

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import (
        A4,
        landscape,
    )
    from reportlab.lib.styles import (
        getSampleStyleSheet,
        ParagraphStyle,
    )
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#111827"),
        spaceAfter=0,
    )

    batch_banner_style = ParagraphStyle(
        "BatchBanner",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E3A8A"),
    )

    header_cell_style = ParagraphStyle(
        "HeaderCell",
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.5,
        textColor=colors.white,
        alignment=1,
    )

    cell_style = ParagraphStyle(
        "BodyCell",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#1F2937"),
        alignment=1,
    )

    cell_style_left = ParagraphStyle(
        "BodyCellLeft",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#1F2937"),
        alignment=0,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#374151"),
    )

    meta_value_style = ParagraphStyle(
        "MetaValue",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#111827"),
    )

    meta_value_highlight = ParagraphStyle(
        "MetaValueHighlight",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1D4ED8"),
    )

    story = []

    # 1. Header Title
    story.append(
        Paragraph("Student Report", title_style)
    )
    story.append(Spacer(1, 2.5 * mm))

    # 2. Metadata / Summary Card
    total_students = len(students_data)
    active_count = sum(
        1
        for s in students_data
        if str(s.get("status", "")).upper() == "ACTIVE"
    )
    inactive_count = total_students - active_count

    filter_text = (
        status_filter.upper()
        if status_filter
        else "ALL"
    )
    today_str = date.today().strftime("%d %b %Y")

    summary_data = [
        [
            Paragraph("Batch Name:", meta_label_style),
            Paragraph(batch_name or "All Batches", meta_value_highlight),
            Paragraph("Location:", meta_label_style),
            Paragraph(
                location or ("All Locations" if is_multi_batch else "N/A"),
                meta_value_style,
            ),
            Paragraph("Generated Date:", meta_label_style),
            Paragraph(today_str, meta_value_style),
        ],
        [
            Paragraph("Status Filter:", meta_label_style),
            Paragraph(filter_text, meta_value_style),
            Paragraph("Total Students:", meta_label_style),
            Paragraph(str(total_students), meta_value_style),
            Paragraph("Active / Inactive:", meta_label_style),
            Paragraph(
                f"<font color='#047857'><b>{active_count} Active</b></font> / <font color='#B91C1C'><b>{inactive_count} Inactive</b></font>",
                meta_value_style,
            ),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[25 * mm, 65 * mm, 25 * mm, 65 * mm, 32 * mm, 65 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    story.append(summary_table)
    story.append(Spacer(1, 3.5 * mm))

    if not students_data:
        story.append(
            Paragraph(
                "No students found matching criteria",
                styles["Normal"],
            )
        )
        document.build(story)
        output.seek(0)
        return output

    # 3. Table Column Widths (Total: 277 mm)
    col_widths = [
        8 * mm,   # ID
        30 * mm,  # Student Name
        12 * mm,  # Gender
        9 * mm,   # Age
        17 * mm,  # DOB
        11 * mm,  # Blood
        17 * mm,  # Join Date
        27 * mm,  # Parent Name
        21 * mm,  # Phone
        14 * mm,  # Status
        18 * mm,  # Classes (Att/Cond)
        17 * mm,  # Monthly Fee
        17 * mm,  # Fee Status
        15 * mm,  # Paid Amt
        15 * mm,  # Pending
        17 * mm,  # Paid Date
        12 * mm,  # Method
    ]

    headers = [
        "ID",
        "Student Name",
        "Gender",
        "Age",
        "DOB",
        "Blood",
        "Join Date",
        "Parent Name",
        "Phone",
        "Status",
        "Classes<br/>(Att/Cond)",
        "Monthly<br/>Fee",
        "Fee Status",
        "Paid Amt",
        "Pending",
        "Paid Date",
        "Method",
    ]

    def build_table_for_students(student_group):
        header_row = [
            Paragraph(h, header_cell_style) for h in headers
        ]
        t_data = [header_row]

        for s in student_group:
            attended = s.get("attended", 0)
            conducted = s.get("conducted", 0)
            classes_str = f"{attended}/{conducted}"

            status_val = str(s.get("status", "ACTIVE")).upper()
            if status_val == "ACTIVE":
                status_para = Paragraph(
                    "<font color='#047857'><b>ACTIVE</b></font>",
                    cell_style,
                )
            else:
                status_para = Paragraph(
                    "<font color='#B91C1C'><b>INACTIVE</b></font>",
                    cell_style,
                )

            fee_status_val = str(s.get("fee_status", "UNPAID")).upper()
            if fee_status_val == "PAID":
                fee_color = "#047857"
            elif fee_status_val in ("OVERDUE", "UNPAID"):
                fee_color = "#B91C1C"
            elif fee_status_val == "DUE TODAY":
                fee_color = "#D97706"
            else:
                fee_color = "#374151"
            fee_status_para = Paragraph(
                f"<font color='{fee_color}'><b>{fee_status_val}</b></font>",
                cell_style,
            )

            t_data.append(
                [
                    Paragraph(str(s.get("id", "")), cell_style),
                    Paragraph(str(s.get("name", "") or "-"), cell_style_left),
                    Paragraph(str(s.get("gender", "") or "-"), cell_style),
                    Paragraph(str(s.get("age", "") if s.get("age") is not None else "-"), cell_style),
                    Paragraph(str(s.get("dob", "") or "-"), cell_style),
                    Paragraph(str(s.get("blood_group", "") or "-"), cell_style),
                    Paragraph(str(s.get("join_date", "") or "-"), cell_style),
                    Paragraph(str(s.get("parent_name", "") or "-"), cell_style_left),
                    Paragraph(str(s.get("phone", "") or "-"), cell_style),
                    status_para,
                    Paragraph(f"<b>{classes_str}</b>", cell_style),
                    Paragraph(str(s.get("monthly_fee", 0)), cell_style),
                    fee_status_para,
                    Paragraph(str(s.get("paid_amount", 0)), cell_style),
                    Paragraph(str(s.get("pending_amount", 0)), cell_style),
                    Paragraph(str(s.get("paid_date", "") or "-"), cell_style),
                    Paragraph(str(s.get("payment_method", "") or "-"), cell_style),
                ]
            )

        st = Table(
            t_data,
            colWidths=col_widths,
            repeatRows=1,
        )

        st.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#F8FAFC"),
                        ],
                    ),
                ]
            )
        )
        return st

    if is_multi_batch and batches_data:
        for b_name, b_info in batches_data.items():
            b_loc = b_info.get("location", "N/A")
            b_students = b_info.get("students", [])
            banner_text = f"<b>Batch:</b> {b_name} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Location:</b> {b_loc} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Students:</b> {len(b_students)}"
            banner_table = Table(
                [[Paragraph(banner_text, batch_banner_style)]],
                colWidths=[277 * mm],
            )
            banner_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(banner_table)
            story.append(Spacer(1, 1.5 * mm))
            story.append(build_table_for_students(b_students))
            story.append(Spacer(1, 4 * mm))
    else:
        story.append(build_table_for_students(students_data))

    document.build(story)
    output.seek(0)
    return output


# =========================================================
# BATCH PDF EXPORT
# =========================================================


def create_batch_pdf(
    batches_data: list[dict],
    batch_filter_name: str | None = None,
) -> BytesIO:

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import (
        A4,
        landscape,
    )
    from reportlab.lib.styles import (
        getSampleStyleSheet,
        ParagraphStyle,
    )
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BatchReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#111827"),
        spaceAfter=0,
    )

    header_cell_style = ParagraphStyle(
        "BatchHeaderCell",
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.5,
        textColor=colors.white,
        alignment=1,
    )

    cell_style = ParagraphStyle(
        "BatchBodyCell",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#1F2937"),
        alignment=1,
    )

    cell_style_left = ParagraphStyle(
        "BatchBodyCellLeft",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#1F2937"),
        alignment=0,
    )

    meta_label_style = ParagraphStyle(
        "BatchMetaLabel",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#374151"),
    )

    meta_value_style = ParagraphStyle(
        "BatchMetaValue",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#111827"),
    )

    meta_value_highlight = ParagraphStyle(
        "BatchMetaValueHighlight",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1D4ED8"),
    )

    story = []

    # 1. Title
    story.append(Paragraph("Batch Report", title_style))
    story.append(Spacer(1, 2.5 * mm))

    # 2. Metadata / Summary Card
    total_batches = len(batches_data)
    total_students = sum(b.get("students", 0) for b in batches_data)
    total_revenue = sum(b.get("revenue", 0) for b in batches_data)
    total_pending = sum(b.get("pending_fee", 0) for b in batches_data)
    today_str = date.today().strftime("%d %b %Y")

    filter_text = batch_filter_name if batch_filter_name else "ALL BATCHES"

    summary_data = [
        [
            Paragraph("Batch Filter:", meta_label_style),
            Paragraph(filter_text, meta_value_highlight),
            Paragraph("Total Batches:", meta_label_style),
            Paragraph(str(total_batches), meta_value_style),
            Paragraph("Generated Date:", meta_label_style),
            Paragraph(today_str, meta_value_style),
        ],
        [
            Paragraph("Total Students:", meta_label_style),
            Paragraph(str(total_students), meta_value_style),
            Paragraph("This Month Revenue:", meta_label_style),
            Paragraph(f"<font color='#047857'><b>Rs. {total_revenue:,}</b></font>", meta_value_style),
            Paragraph("Total Pending Fees:", meta_label_style),
            Paragraph(f"<font color='#B91C1C'><b>Rs. {total_pending:,}</b></font>", meta_value_style),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[25 * mm, 65 * mm, 30 * mm, 60 * mm, 32 * mm, 65 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    story.append(summary_table)
    story.append(Spacer(1, 3.5 * mm))

    if not batches_data:
        story.append(Paragraph("No batches found matching criteria", styles["Normal"]))
        document.build(story)
        output.seek(0)
        return output

    # 3. Table Column Widths (Total: 277 mm)
    col_widths = [
        9 * mm,   # ID
        28 * mm,  # Batch Name
        24 * mm,  # Location
        16 * mm,  # Level
        17 * mm,  # Class Type
        36 * mm,  # Training Days
        18 * mm,  # Monthly Fee
        15 * mm,  # Students
        17 * mm,  # Conducted
        15 * mm,  # Present
        15 * mm,  # Absent
        18 * mm,  # Attendance %
        24 * mm,  # This Month Rev
        25 * mm,  # Pending Fees
    ]

    headers = [
        "ID",
        "Batch Name",
        "Location",
        "Level",
        "Class Type",
        "Training Days",
        "Monthly<br/>Fee",
        "Students",
        "Classes<br/>Conducted",
        "Present",
        "Absent",
        "Attendance<br/>%",
        "Month<br/>Revenue",
        "Pending<br/>Fees",
    ]

    header_row = [
        Paragraph(h, header_cell_style) for h in headers
    ]
    table_data = [header_row]

    for b in batches_data:
        days_val = b.get("training_days", "")
        if isinstance(days_val, list):
            days_str = ", ".join(days_val)
        else:
            days_str = str(days_val or "-")

        for full_day, short_day in [
            ("Monday", "Mon"), ("Tuesday", "Tue"), ("Wednesday", "Wed"),
            ("Thursday", "Thu"), ("Friday", "Fri"), ("Saturday", "Sat"), ("Sunday", "Sun")
        ]:
            days_str = days_str.replace(full_day, short_day)

        att_pct = b.get("attendance_percentage", 0)

        table_data.append(
            [
                Paragraph(str(b.get("id", "")), cell_style),
                Paragraph(str(b.get("batch_name", "") or "-"), cell_style_left),
                Paragraph(str(b.get("location", "") or "-"), cell_style_left),
                Paragraph(str(b.get("level", "") or "-"), cell_style),
                Paragraph(str(b.get("class_type", "") or "-"), cell_style),
                Paragraph(days_str, cell_style_left),
                Paragraph(str(b.get("monthly_fee", 0)), cell_style),
                Paragraph(str(b.get("students", 0)), cell_style),
                Paragraph(str(b.get("conducted", 0)), cell_style),
                Paragraph(str(b.get("present", 0)), cell_style),
                Paragraph(str(b.get("absent", 0)), cell_style),
                Paragraph(f"{att_pct:.1f}%", cell_style),
                Paragraph(f"Rs. {b.get('revenue', 0):,}", cell_style),
                Paragraph(
                    f"<font color='#B91C1C'><b>Rs. {b.get('pending_fee', 0):,}</b></font>"
                    if b.get("pending_fee", 0) > 0
                    else "Rs. 0",
                    cell_style,
                ),
            ]
        )

    batch_table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1,
    )

    batch_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F8FAFC"),
                    ],
                ),
            ]
        )
    )

    story.append(batch_table)
    document.build(story)
    output.seek(0)
    return output


# =========================================================
# RESPONSE FILE
# =========================================================


def export_response(
    data,
    format,
    filename,
    title,
):

    if format == "xlsx":

        output = create_excel(
            data
        )

        return StreamingResponse(
            output,
            media_type=(
                "application/"
                "vnd.openxmlformats-"
                "officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}.xlsx"'
            },
        )

    if format == "csv":

        # First sheet only
        first_rows = next(
            iter(data.values())
        )

        output = create_csv(
            first_rows
        )

        return StreamingResponse(
            iter([
                output.getvalue()
            ]),
            media_type="text/csv",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}.csv"'
            },
        )

    if format == "pdf":

        first_rows = next(
            iter(data.values())
        )

        output = create_pdf(
            title,
            first_rows,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}.pdf"'
            },
        )

    raise HTTPException(
        status_code=400,
        detail="Unsupported export format",
    )


# =========================================================
# 1. ATTENDANCE EXPORT
# =========================================================


@router.get(
    "/attendance/export"
)
def export_attendance_report(

    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
        default=None
    ),

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    format: str = Query(
        default="xlsx",
        pattern="^(xlsx|pdf|csv)$",
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    today = date.today()

    start_date = (
        from_date
        or today.replace(day=1)
    )

    end_date = (
        to_date
        or today
    )

    if start_date > end_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "from_date cannot be "
                "greater than to_date"
            ),
        )

    # -----------------------------------------------------
    # SESSIONS
    # -----------------------------------------------------

    query = (
        db.query(SessionModel)
        .filter(
            SessionModel.status
            == "COMPLETED",

            SessionModel.session_date
            >= start_date,

            SessionModel.session_date
            <= end_date,
        )
    )

    if batch_id:

        query = query.filter(
            SessionModel.batch_id
            == batch_id
        )

    sessions = (
        query
        .order_by(
            SessionModel.session_date.asc()
        )
        .all()
    )

    student_rows = []
    session_rows = []

    # -----------------------------------------------------
    # SESSION REPORT
    # -----------------------------------------------------

    for session in sessions:

        batch = (
            db.query(Batch)
            .filter(
                Batch.id
                == session.batch_id
            )
            .first()
        )

        expected = (
            db.query(
                func.count(Student.id)
            )
            .filter(
                Student.batch_id
                == session.batch_id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        present = (
            db.query(
                func.count(
                    Attendance.id
                )
            )
            .filter(
                Attendance.session_id
                == session.id,

                Attendance.status
                == "Present",
            )
            .scalar()
            or 0
        )

        absent = max(
            expected - present,
            0,
        )

        percentage = (
            round(
                (
                    present
                    / expected
                )
                * 100,
                2,
            )
            if expected
            else 0
        )

        session_rows.append(
            {
                "Session ID":
                    session.id,

                "Date":
                    format_date(
                        session.session_date
                    ),

                "Batch":
                    batch.batch_name
                    if batch
                    else "",

                "Students":
                    expected,

                "Present":
                    present,

                "Absent":
                    absent,

                "Attendance %":
                    percentage,
            }
        )

        # -------------------------------------------------
        # STUDENT-WISE
        # -------------------------------------------------

        batch_students = (
            db.query(Student)
            .filter(
                Student.batch_id
                == session.batch_id,

                Student.is_active.is_(True),
            )
            .all()
        )

        for student in batch_students:

            attendance = (
                db.query(Attendance)
                .filter(
                    Attendance.session_id
                    == session.id,

                    Attendance.student_id
                    == student.id,
                )
                .first()
            )

            status = (
                attendance.status
                if attendance
                else "Absent"
            )

            student_rows.append(
                {
                    "Session Date":
                        format_date(
                            session.session_date
                        ),

                    "Session ID":
                        session.id,

                    "Student ID":
                        student.id,

                    "Student Name":
                        student.full_name,

                    "Batch Name":
                        batch.batch_name
                        if batch
                        else "",

                    "Attendance":
                        status,
                }
            )

    return export_response(
        {
            "Attendance":
                student_rows,

            "Session Summary":
                session_rows,
        },
        format,
        "attendance-report",
        "Attendance Report",
    )


# =========================================================
# 2. REVENUE EXPORT
# =========================================================


@router.get(
    "/revenue/export"
)
def export_revenue_report(

    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
        default=None
    ),

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    payment_method: str | None = Query(
        default=None
    ),

    format: str = Query(
        default="xlsx",
        pattern="^(xlsx|pdf|csv)$",
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    query = (
        db.query(
            FeePayment,
            Student,
            Batch,
        )
        .join(
            Student,
            FeePayment.student_id
            == Student.id,
        )
        .join(
            Batch,
            Student.batch_id
            == Batch.id,
        )
        .filter(
            Student.is_active.is_(True),
            Batch.is_active.is_(True),
        )
    )

    if from_date:

        query = query.filter(
            FeePayment.payment_date
            >= datetime.combine(
                from_date,
                time.min,
            )
        )

    if to_date:

        query = query.filter(
            FeePayment.payment_date
            < datetime.combine(
                to_date,
                time.max,
            )
        )

    if batch_id:

        query = query.filter(
            Student.batch_id
            == batch_id
        )

    if payment_method:

        query = query.filter(
            FeePayment.payment_method
            == payment_method.upper()
        )

    payments = (
        query
        .order_by(
            FeePayment.payment_date.desc()
        )
        .all()
    )

    rows = []

    for payment, student, batch in payments:

        rows.append(
            {
                "Payment ID":
                    payment.id,

                "Student ID":
                    student.id,

                "Student Name":
                    student.full_name,

                "Batch Name":
                    batch.batch_name,

                "Location":
                    batch.location
                    or "",

                "Fee Month":
                    month_name(
                        payment.fee_month
                    ),

                "Fee Year":
                    payment.fee_year,

                "Amount":
                    int(
                        payment.net_payable
                        or 0
                    ),

                "Payment Method":
                    str(
                        payment.payment_method
                    ),

                "Payment Date":
                    format_date(
                        payment.payment_date
                    ),

                "Status":
                    "PAID",
            }
        )

    return export_response(
        {
            "Revenue":
                rows
        },
        format,
        "revenue-report",
        "Revenue Report",
    )


# =========================================================
# 3. STUDENT EXPORT
# =========================================================


@router.get(
    "/students/export"
)
def export_student_report(

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    status: str | None = Query(
        default=None
    ),

    format: str = Query(
        default="xlsx",
        pattern="^(xlsx|pdf|csv)$",
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    query = (
        db.query(
            Student,
            Batch,
        )
        .join(
            Batch,
            Student.batch_id
            == Batch.id,
        )
    )

    if batch_id:

        query = query.filter(
            Student.batch_id
            == batch_id
        )

    if status:

        if status.lower() == "active":

            query = query.filter(
                Student.is_active.is_(True)
            )

        elif status.lower() == "inactive":

            query = query.filter(
                Student.is_active.is_(False)
            )

    students = (
        query
        .order_by(
            Student.id.desc()
        )
        .all()
    )

    rows = []
    payment_rows = []
    pdf_student_items = []

    today = date.today()

    current_month = today.month
    current_year = today.year

    for student, batch in students:

        # -------------------------------------------------
        # COMPLETED CLASSES
        # -------------------------------------------------

        session_query = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id
                == student.batch_id,

                SessionModel.status
                == "COMPLETED",

                SessionModel.session_date
                <= today,
            )
        )

        if student.join_date:

            session_query = (
                session_query.filter(
                    SessionModel.session_date
                    >= student.join_date
                )
            )

        sessions = (
            session_query
            .all()
        )

        conducted = len(
            sessions
        )

        session_ids = [
            session.id
            for session in sessions
        ]

        if session_ids:

            attended = (
                db.query(
                    func.count(
                        Attendance.id
                    )
                )
                .filter(
                    Attendance.student_id
                    == student.id,

                    Attendance.session_id.in_(
                        session_ids
                    ),

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

        else:

            attended = 0

        absent = max(
            conducted - attended,
            0,
        )

        attendance_percentage = (
            round(
                (
                    attended
                    / conducted
                )
                * 100,
                2,
            )
            if conducted
            else 0
        )

        # -------------------------------------------------
        # CURRENT PAYMENT
        # -------------------------------------------------

        payment = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id
                == student.id,

                FeePayment.fee_month
                == current_month,

                FeePayment.fee_year
                == current_year,
            )
            .order_by(
                FeePayment.payment_date.desc()
            )
            .first()
        )

        monthly_fee = int(
            student.monthly_fee
            or batch.monthly_fee
            or 0
        )

        if payment:

            fee_status = "PAID"

            paid_amount = int(
                payment.net_payable
                or 0
            )

            paid_date = format_date(
                payment.payment_date
            )

            payment_method = str(
                payment.payment_method
            )

            pending_amount = 0

        else:

            paid_amount = 0

            paid_date = ""

            payment_method = ""

            pending_amount = monthly_fee

            due_day = 1

            due_date = date(
                current_year,
                current_month,
                due_day,
            )

            if today > due_date:

                fee_status = "OVERDUE"

            elif today == due_date:

                fee_status = "DUE TODAY"

            else:

                fee_status = "UNPAID"

        # -------------------------------------------------
        # PAYMENT HISTORY
        # -------------------------------------------------

        payments = (
            db.query(FeePayment)
            .filter(
                FeePayment.student_id
                == student.id
            )
            .order_by(
                FeePayment.payment_date.desc()
            )
            .all()
        )

        total_paid = 0

        for payment_item in payments:

            amount = int(
                payment_item.net_payable
                or 0
            )

            total_paid += amount

            payment_rows.append(
                {
                    "Payment ID":
                        payment_item.id,

                    "Student ID":
                        student.id,

                    "Student Name":
                        student.full_name,

                    "Batch Name":
                        batch.batch_name,

                    "Fee Month":
                        month_name(
                            payment_item.fee_month
                        ),

                    "Fee Year":
                        payment_item.fee_year,

                    "Amount":
                        amount,

                    "Payment Method":
                        str(
                            payment_item.payment_method
                        ),

                    "Payment Date":
                        format_date(
                            payment_item.payment_date
                        ),

                    "Status":
                        "PAID",
                }
            )

        # -------------------------------------------------
        # -------------------------------------------------
        # PDF STUDENT ITEM
        # -------------------------------------------------

        pdf_student_items.append(
            {
                "id":
                    student.id,
                "name":
                    student.full_name,
                "gender":
                    student.gender,
                "age":
                    calculate_age(
                        student.dob
                    ),
                "dob":
                    format_date(
                        student.dob
                    ),
                "blood_group":
                    student.blood_group
                    or "",
                "batch_name":
                    batch.batch_name,
                "location":
                    batch.location
                    or "",
                "join_date":
                    format_date(
                        student.join_date
                    ),
                "parent_name":
                    student.parent_name,
                "phone":
                    student.phone_number,
                "status":
                    (
                        "ACTIVE"
                        if student.is_active
                        else "INACTIVE"
                    ),
                "attended":
                    attended,
                "conducted":
                    conducted,
                "monthly_fee":
                    monthly_fee,
                "fee_status":
                    fee_status,
                "paid_amount":
                    paid_amount,
                "pending_amount":
                    pending_amount,
                "paid_date":
                    paid_date,
                "payment_method":
                    payment_method,
            }
        )

        # -------------------------------------------------
        # STUDENT ROW (FOR EXCEL / CSV)
        # -------------------------------------------------

        rows.append(
            {
                "Student ID":
                    student.id,

                "Student Name":
                    student.full_name,

                "Gender":
                    student.gender,

                "Age":
                    calculate_age(
                        student.dob
                    ),

                "DOB":
                    format_date(
                        student.dob
                    ),

                "Blood Group":
                    student.blood_group
                    or "",

                "Batch Name":
                    batch.batch_name,

                "Location":
                    batch.location
                    or "",

                "Join Date":
                    format_date(
                        student.join_date
                    ),

                "Parent Name":
                    student.parent_name,

                "Phone":
                    student.phone_number,

                "Emergency Contact":
                    student.emergency_contact,

                "Student Status":
                    (
                        "ACTIVE"
                        if student.is_active
                        else "INACTIVE"
                    ),

                "Classes Conducted":
                    conducted,

                "Classes Attended":
                    attended,

                "Classes Absent":
                    absent,

                "Classes (Att/Cond)":
                    f"{attended}/{conducted}",

                "Attendance %":
                    attendance_percentage,

                "Monthly Fee":
                    monthly_fee,

                "Current Fee Status":
                    fee_status,

                "Paid Amount":
                    paid_amount,

                "Pending Amount":
                    pending_amount,

                "Paid Date":
                    paid_date,

                "Payment Method":
                    payment_method,

                "Total Payments":
                    len(payments),

                "Total Paid":
                    total_paid,
            }
        )

    if format == "pdf":

        if batch_id:

            batch_obj = (
                db.query(Batch)
                .filter(
                    Batch.id
                    == batch_id
                )
                .first()
            )

            selected_batch_name = (
                batch_obj.batch_name
                if batch_obj
                else f"Batch {batch_id}"
            )

            selected_location = (
                batch_obj.location
                if batch_obj
                and batch_obj.location
                else ""
            )

            is_multi = False
            batch_groups = None

        else:

            unique_batches = {}

            for item in pdf_student_items:

                b_name = item.get(
                    "batch_name",
                    "",
                )

                if b_name not in unique_batches:

                    unique_batches[b_name] = {
                        "location":
                            item.get(
                                "location",
                                "",
                            ),
                        "students": [],
                    }

                unique_batches[b_name][
                    "students"
                ].append(item)

            if len(unique_batches) <= 1:

                is_multi = False

                if unique_batches:

                    selected_batch_name = list(
                        unique_batches.keys()
                    )[0]

                    selected_location = (
                        unique_batches[
                            selected_batch_name
                        ]["location"]
                    )

                else:

                    selected_batch_name = (
                        "All Batches"
                    )

                    selected_location = ""

                batch_groups = None

            else:

                is_multi = True

                selected_batch_name = (
                    f"All Batches ({len(unique_batches)})"
                )

                locs = []
                for v in unique_batches.values():
                    loc_val = (v.get("location") or "").strip()
                    if loc_val and loc_val.lower() not in [l.lower() for l in locs]:
                        locs.append(loc_val)

                selected_location = (
                    ", ".join(locs)
                    if locs
                    else "All Locations"
                )

                batch_groups = unique_batches

        output = create_student_pdf(
            batch_name=selected_batch_name,
            location=selected_location,
            status_filter=status,
            students_data=pdf_student_items,
            is_multi_batch=is_multi,
            batches_data=batch_groups,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    'attachment; filename="student-report.pdf"'
            },
        )

    return export_response(
        {
            "Students":
                rows,

            "Payment History":
                payment_rows,
        },
        format,
        "student-report",
        "Student Report",
    )


# =========================================================
# 4. BATCH EXPORT
# =========================================================


@router.get(
    "/batches/export"
)
def export_batch_report(

    batch_id: int | None = Query(
        default=None,
        gt=0,
    ),

    format: str = Query(
        default="xlsx",
        pattern="^(xlsx|pdf|csv)$",
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    query = (
        db.query(Batch)
        .filter(
            Batch.is_active.is_(True)
        )
    )

    if batch_id:

        query = query.filter(
            Batch.id
            == batch_id
        )

    batches = (
        query
        .order_by(
            Batch.batch_name.asc()
        )
        .all()
    )

    rows = []
    pdf_batch_items = []

    today = date.today()

    for batch in batches:

        # -------------------------------------------------
        # STUDENTS
        # -------------------------------------------------

        student_count = (
            db.query(
                func.count(
                    Student.id
                )
            )
            .filter(
                Student.batch_id
                == batch.id,

                Student.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # COMPLETED SESSIONS
        # -------------------------------------------------

        sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.batch_id
                == batch.id,

                SessionModel.status
                == "COMPLETED",

                SessionModel.session_date
                <= today,
            )
            .all()
        )

        conducted = len(
            sessions
        )

        session_ids = [
            session.id
            for session in sessions
        ]

        # -------------------------------------------------
        # PRESENT
        # -------------------------------------------------

        present = 0

        if session_ids:

            present = (
                db.query(
                    func.count(
                        Attendance.id
                    )
                )
                .filter(
                    Attendance.session_id.in_(
                        session_ids
                    ),

                    Attendance.status
                    == "Present",
                )
                .scalar()
                or 0
            )

        expected = (
            student_count
            * conducted
        )

        absent = max(
            expected - present,
            0,
        )

        attendance_percentage = (
            round(
                (
                    present
                    / expected
                )
                * 100,
                2,
            )
            if expected
            else 0
        )

        # -------------------------------------------------
        # CURRENT MONTH REVENUE
        # -------------------------------------------------

        current_month = today.month
        current_year = today.year

        revenue = (
            db.query(
                func.coalesce(
                    func.sum(
                        FeePayment.net_payable
                    ),
                    0,
                )
            )
            .join(
                Student,
                FeePayment.student_id
                == Student.id,
            )
            .filter(
                Student.batch_id
                == batch.id,

                FeePayment.fee_month
                == current_month,

                FeePayment.fee_year
                == current_year,
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # PENDING FEES
        # -------------------------------------------------

        batch_students = (
            db.query(Student)
            .filter(
                Student.batch_id
                == batch.id,

                Student.is_active.is_(True),
            )
            .all()
        )

        pending_fee = 0

        for student in batch_students:

            paid = (
                db.query(FeePayment.id)
                .filter(
                    FeePayment.student_id
                    == student.id,

                    FeePayment.fee_month
                    == current_month,

                    FeePayment.fee_year
                    == current_year,
                )
                .first()
            )

            if not paid:

                pending_fee += int(
                    student.monthly_fee
                    or batch.monthly_fee
                    or 0
                )

        # -------------------------------------------------
        # PDF BATCH ITEM
        # -------------------------------------------------

        pdf_batch_items.append(
            {
                "id":
                    batch.id,
                "batch_name":
                    batch.batch_name,
                "location":
                    batch.location
                    or "",
                "level":
                    batch.level
                    or "",
                "class_type":
                    batch.class_type
                    or "",
                "training_days":
                    batch.training_days,
                "monthly_fee":
                    int(
                        batch.monthly_fee
                        or 0
                    ),
                "students":
                    student_count,
                "conducted":
                    conducted,
                "present":
                    present,
                "absent":
                    absent,
                "attendance_percentage":
                    attendance_percentage,
                "revenue":
                    int(revenue),
                "pending_fee":
                    pending_fee,
            }
        )

        # -------------------------------------------------
        # ROW (FOR EXCEL / CSV)
        # -------------------------------------------------

        rows.append(
            {
                "Batch ID":
                    batch.id,

                "Batch Name":
                    batch.batch_name,

                "Location":
                    batch.location
                    or "",

                "Level":
                    batch.level
                    or "",

                "Class Type":
                    batch.class_type
                    or "",

                "Training Days": (
                    ", ".join(batch.training_days)
                    if isinstance(
                        batch.training_days,
                        list,
                    )
                    else (
                        batch.training_days
                        or ""
                    )
                ),

                "Monthly Fee":
                    int(
                        batch.monthly_fee
                        or 0
                    ),

                "Students":
                    student_count,

                "Classes Conducted":
                    conducted,

                "Attendance Present":
                    present,

                "Attendance Absent":
                    absent,

                "Attendance %":
                    attendance_percentage,

                "This Month Revenue":
                    int(revenue),

                "Pending Fees":
                    pending_fee,
            }
        )

    if format == "pdf":

        batch_filter_name = None
        if batch_id and batches:
            batch_filter_name = batches[0].batch_name

        output = create_batch_pdf(
            batches_data=pdf_batch_items,
            batch_filter_name=batch_filter_name,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    'attachment; filename="batch-report.pdf"'
            },
        )

    return export_response(
        {
            "Batches":
                rows
        },
        format,
        "batch-report",
        "Batch Report",
    )