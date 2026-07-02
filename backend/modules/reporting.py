"""
modules/reporting.py
====================
Reporting module for the calibration application.

Responsibilities
----------------
1. gather_report_data  — orchestrates all six database calls into one ReportData object.
2. generate_pdf_report — builds a ReportLab PDF certificate and streams it.
3. generate_excel_report — builds an openpyxl workbook certificate and streams it.
4. write_audit_entry   — records a generation event to the audit log via database.py.

Rules enforced throughout
--------------------------
* Black and white only in PDF — no colour anywhere.
* Font is Helvetica (ReportLab built-in); no external font files required.
* All tables have black borders.
* Page numbers appear in the footer of every PDF page.
* If assets/logo.png exists it is drawn in the PDF header; if absent it is
  silently skipped — no exception is raised.
* Report files are never stored on the server: file is generated, streamed,
  then deleted via a background task attached to the FileResponse.
* Sessions with status REJECTED raise ValueError before any file is created.
* All database access goes through functions imported from database.py.
* No calculation logic and no validation logic live in this module.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from database import (
    get_readings,               # readings table
    get_calibration_reference,  # calibration_reference table
    get_session,                # calibration_sessions table
    get_instrument,             # instruments table
    get_master_instrument,      # master_instruments table
    get_uncertainty_budget,     # uncertainty_budgets table
    insert_audit_log,           # audit_log table
)

logger = logging.getLogger(__name__)

# ─── Module-level constants ────────────────────────────────────────────────────

PAGE_WIDTH, PAGE_HEIGHT = A4
LOGO_PATH = Path("assets/logo.png")

LEFT_MARGIN = 20 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 38 * mm
BOTTOM_MARGIN = 25 * mm

BLACK = colors.black
WHITE = colors.white

FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"

THIN_BORDER = 0.5


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — DATA GATHERING
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReportData:
    """Typed container for every field a calibration certificate must render.

    Produced exclusively by gather_report_data and consumed by
    generate_pdf_report, generate_excel_report, and write_audit_entry.
    Field names mirror the database column names from the spec so that a
    renamed column causes a visible KeyError in gather_report_data rather
    than a silent None in a rendered cell.

    Attributes:
        session_id: Primary key of the calibration session.
        session_status: Uppercased status string from calibration_sessions.
        certificate_number: Unique certificate identifier from calibration_reference.
        date_of_calibration: Date the calibration was performed.
        cal_due_date: Next calibration due date.
        item_received_date: Date the instrument was received by the lab.
        date_of_issue: Date this certificate was issued.
        customer_name: Name of the customer organisation.
        customer_address: Full postal address of the customer.
        instrument_name: Human-readable name of the instrument under test.
        instrument_make: Manufacturer name.
        instrument_model: Model designation.
        instrument_serial_number: Serial number of the instrument under test.
        instrument_tag_number: Site tag or asset number.
        temperature_c: Ambient temperature in degrees Celsius during calibration.
        humidity_pct: Relative humidity percentage during calibration.
        master_name: Name of the reference / master instrument.
        master_serial_number: Serial number of the master instrument.
        master_traceability_chain: Documented traceability chain string.
        master_claimed_cmc: Claimed calibration and measurement capability.
        readings: Ordered list of per-point measurement dicts.
        type_a_value: Type A uncertainty evaluation result.
        u_std: Standard uncertainty.
        u_res: Resolution uncertainty contribution.
        u_hys: Hysteresis uncertainty contribution.
        u_zero: Zero / offset uncertainty contribution.
        u_temp: Temperature uncertainty contribution.
        cmc: CMC uncertainty contribution.
        combined_uncertainty: Combined standard uncertainty.
        expanded_uncertainty: Expanded uncertainty.
        k_value: Coverage factor k.
        final_applied_uncertainty: Final uncertainty value stated on certificate.
    """

    session_id: str
    session_status: str

    # calibration_reference
    certificate_number: str | None
    date_of_calibration: Any
    cal_due_date: Any
    item_received_date: Any
    date_of_issue: Any
    customer_name: str | None
    customer_address: str | None

    # instruments
    instrument_name: str | None
    instrument_make: str | None
    instrument_model: str | None
    instrument_serial_number: str | None
    instrument_tag_number: str | None

    # environmental conditions from calibration_sessions
    temperature_c: Any
    humidity_pct: Any

    # master_instruments
    master_name: str | None
    master_serial_number: str | None
    master_traceability_chain: str | None
    master_claimed_cmc: Any

    # readings — order preserved from the database call
    readings: list[dict[str, Any]] = field(default_factory=list)

    # uncertainty_budgets — spec field names used verbatim
    type_a_value: Any = None
    u_std: Any = None
    u_res: Any = None
    u_hys: Any = None
    u_zero: Any = None
    u_temp: Any = None
    cmc: Any = None
    combined_uncertainty: Any = None
    expanded_uncertainty: Any = None
    k_value: Any = None
    final_applied_uncertainty: Any = None


def gather_report_data(session_id: str) -> ReportData:
    """Fetch and assemble all data required to render a calibration certificate.

    Makes one call per source table through database.py. No calculation or
    validation logic runs here; values are mapped directly from database
    records into a ReportData instance.

    The REJECTED status guard lives here so that both renderers are protected
    by calling this single function rather than each implementing their own check.

    Args:
        session_id: UUID of the calibration session to report on.

    Returns:
        ReportData: Fully populated instance ready for a renderer.

    Raises:
        ValueError: If no session exists for session_id, or if the session
            status is REJECTED.
        RuntimeError: If a required database record is absent.
    """
    # Fetched first because status determines whether any further work proceeds.
    session_record = get_session(session_id)
    if session_record is None:
        raise ValueError(f"No calibration session found for session_id={session_id}.")

    session_status = str(session_record.get("status", "")).upper()

    # Raising here means neither PDF nor Excel generation can bypass this rule.
    if session_status == "REJECTED":
        raise ValueError(
            f"Session {session_id} has status REJECTED. "
            "Certificate generation is not permitted for rejected sessions."
        )

    # calibration_reference
    certificate_record = get_calibration_reference(session_id)
    if certificate_record is None:
        raise RuntimeError(f"No calibration_reference record found for session_id={session_id}.")

    # instruments — instrument_id is stored on the session record
    instrument_id = session_record.get("instrument_id")
    instrument_record = get_instrument(instrument_id)
    if instrument_record is None:
        raise RuntimeError(f"No instruments record found for instrument_id={instrument_id}.")

    # readings — empty list is valid for a draft session
    readings_rows: list[dict[str, Any]] = get_readings(session_id) or []

    # uncertainty_budgets
    uncertainty_record = get_uncertainty_budget(session_id)
    if uncertainty_record is None:
        raise RuntimeError(f"No uncertainty_budgets record found for session_id={session_id}.")

    # master_instruments — linked via calibration_sessions.master_instrument_id
    master_instrument_id = session_record.get("master_instrument_id")
    master_record = {}
    if master_instrument_id:
        master_record = get_master_instrument(master_instrument_id) or {}
    else:
        logger.warning(
            "Session %s has no master_instrument_id set; certificate will be "
            "generated with blank master instrument fields.",
            session_id,
        )

    return ReportData(
        session_id=session_id,
        session_status=session_status,

        certificate_number=certificate_record.get("certificate_number"),
        date_of_calibration=certificate_record.get("date_of_calibration"),
        cal_due_date=certificate_record.get("cal_due_date"),
        item_received_date=certificate_record.get("item_received_date"),
        date_of_issue=certificate_record.get("date_of_issue"),
        customer_name=certificate_record.get("customer_name"),
        customer_address=certificate_record.get("customer_address"),

        instrument_name=instrument_record.get("name"),
        instrument_make=instrument_record.get("make"),
        instrument_model=instrument_record.get("model"),
        instrument_serial_number=instrument_record.get("serial_number"),
        instrument_tag_number=instrument_record.get("tag_number"),

        # Environmental conditions are stored on the calibration session
        temperature_c=session_record.get("temperature_c"),
        humidity_pct=session_record.get("humidity_pct"),

        master_name=master_record.get("name"),
        master_serial_number=master_record.get("serial_number"),
        master_traceability_chain=master_record.get("traceability_chain"),
        master_claimed_cmc=master_record.get("claimed_cmc"),

        readings=readings_rows,

        type_a_value=uncertainty_record.get("type_a_value"),
        u_std=uncertainty_record.get("u_std"),
        u_res=uncertainty_record.get("u_res"),
        u_hys=uncertainty_record.get("u_hys"),
        u_zero=uncertainty_record.get("u_zero"),
        u_temp=uncertainty_record.get("u_temp"),
        cmc=uncertainty_record.get("cmc"),
        combined_uncertainty=uncertainty_record.get("combined_uncertainty"),
        expanded_uncertainty=uncertainty_record.get("expanded_uncertainty"),
        k_value=uncertainty_record.get("k_value"),
        final_applied_uncertainty=uncertainty_record.get("final_applied_uncertainty"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PDF GENERATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _format_date(raw_date: Any) -> str:
    """Format a date value to a human-readable string for certificate display.

    Args:
        raw_date: A datetime, date, ISO string, or None.

    Returns:
        str: Formatted string such as "15 Jun 2025", or "—" for None.
    """
    if raw_date is None:
        return "\u2014"
    if isinstance(raw_date, str):
        try:
            raw_date = datetime.fromisoformat(raw_date)
        except ValueError:
            return str(raw_date)
    return raw_date.strftime("%d %b %Y")


def _safe_str(value: Any) -> str:
    """Return value as a string, substituting an em-dash for None.

    Args:
        value: Any value from a ReportData field.

    Returns:
        str: String representation, or "—" when value is None.
    """
    return "\u2014" if value is None else str(value)


def _build_paragraph_styles() -> dict[str, ParagraphStyle]:
    """Return named ParagraphStyle objects for PDF certificate sections.

    Returns:
        dict[str, ParagraphStyle]: Mapping of style name to ParagraphStyle.
    """
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CertTitle",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=18,
            alignment=1,
            textColor=BLACK,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            spaceBefore=6,
            spaceAfter=3,
            textColor=BLACK,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName=FONT_NORMAL,
            fontSize=8,
            leading=11,
            textColor=BLACK,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=11,
            textColor=BLACK,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontName=FONT_OBLIQUE,
            fontSize=7,
            leading=9,
            alignment=1,
            textColor=BLACK,
        ),
    }


def _black_table_style(has_header_row: bool = True) -> TableStyle:
    """Return a TableStyle with black borders and optional bold header row.

    Args:
        has_header_row: When True, applies a black-filled header row with
            white bold text.

    Returns:
        TableStyle: Configured instance.
    """
    light_grey = colors.Color(0.93, 0.93, 0.93)

    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
        ("GRID", (0, 0), (-1, -1), THIN_BORDER, BLACK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, light_grey]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    if has_header_row:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), BLACK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, light_grey]),
        ]

    return TableStyle(commands)


def _kv_table_style() -> TableStyle:
    """Return a TableStyle for two-column label/value pair tables.

    Returns:
        TableStyle: Configured instance.
    """
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
            ("FONTNAME", (1, 0), (1, -1), FONT_NORMAL),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 11),
            ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
            ("BOX", (0, 0), (-1, -1), THIN_BORDER, BLACK),
            ("INNERGRID", (0, 0), (-1, -1), THIN_BORDER, BLACK),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )


def _build_kv_table(
    pairs: list[tuple[str, str]],
    styles: dict[str, ParagraphStyle],
    col_widths: list[float],
) -> Table:
    """Build a two-column label/value Table from a list of (label, value) pairs.

    Args:
        pairs: Sequence of (label_string, value_string) tuples.
        styles: Style dict from _build_paragraph_styles.
        col_widths: Two-element list of column widths in points.

    Returns:
        Table: Formatted ReportLab Table.
    """
    table_data = [
        [
            Paragraph(label, styles["body_bold"]),
            Paragraph(value, styles["body"]),
        ]
        for label, value in pairs
    ]
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(_kv_table_style())
    return table


def _build_header_footer_callback(
    certificate_number: str,
    total_pages_ref: list,
):
    """Return an onPage callback that draws the PDF header and footer.

    Args:
        certificate_number: Certificate number shown in the header.
        total_pages_ref: Single-element list updated to the true page count
            after the first build pass completes.

    Returns:
        Callable: The on_page function to register with SimpleDocTemplate.
    """

    def on_page(canvas_obj, doc):
        canvas_obj.saveState()

        header_baseline = PAGE_HEIGHT - 10 * mm

        if LOGO_PATH.exists():
            try:
                canvas_obj.drawImage(
                    str(LOGO_PATH),
                    LEFT_MARGIN,
                    header_baseline - 12 * mm,
                    width=28 * mm,
                    height=12 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                # A corrupt or unsupported logo must never abort the certificate.
                logger.warning(
                    "Logo exists at %s but could not be drawn; skipping.",
                    LOGO_PATH,
                    exc_info=True,
                )

        canvas_obj.setFont(FONT_BOLD, 14)
        canvas_obj.setFillColor(BLACK)
        canvas_obj.drawCentredString(
            PAGE_WIDTH / 2, header_baseline - 5 * mm, "CALIBRATION CERTIFICATE"
        )
        canvas_obj.setFont(FONT_NORMAL, 8)
        canvas_obj.drawCentredString(
            PAGE_WIDTH / 2,
            header_baseline - 11 * mm,
            f"Certificate No: {certificate_number}",
        )

        canvas_obj.setStrokeColor(BLACK)
        canvas_obj.setLineWidth(0.75)
        canvas_obj.line(
            LEFT_MARGIN,
            PAGE_HEIGHT - TOP_MARGIN + 4 * mm,
            PAGE_WIDTH - RIGHT_MARGIN,
            PAGE_HEIGHT - TOP_MARGIN + 4 * mm,
        )

        footer_y = BOTTOM_MARGIN - 7 * mm
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(LEFT_MARGIN, BOTTOM_MARGIN - 2 * mm, PAGE_WIDTH - RIGHT_MARGIN, BOTTOM_MARGIN - 2 * mm)

        canvas_obj.setFont(FONT_OBLIQUE, 7)
        canvas_obj.drawString(
            LEFT_MARGIN,
            footer_y,
            "This certificate is valid only when reproduced in its entirety.",
        )
        canvas_obj.drawRightString(
            PAGE_WIDTH - RIGHT_MARGIN,
            footer_y,
            f"Page {doc.page} of {total_pages_ref[0]}",
        )

        canvas_obj.restoreState()

    return on_page


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PDF GENERATION
# ══════════════════════════════════════════════════════════════════════════════


def generate_pdf_report(session_id: str) -> FileResponse:
    """Generate a PDF calibration certificate for the given session.

    Args:
        session_id: UUID of the calibration session.

    Returns:
        FileResponse: Streaming PDF attachment.

    Raises:
        ValueError: When the session does not exist or has status REJECTED.
        RuntimeError: When a required database record is missing.
    """
    report_data = gather_report_data(session_id)

    styles = _build_paragraph_styles()
    usable_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    label_col_narrow = 50 * mm
    label_col_wide = 70 * mm

    total_pages_ref: list[int | str] = ["?"]

    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf", prefix=f"cal_cert_{session_id}_"
    )
    temp_path = temp_file.name
    temp_file.close()

    try:
        doc = SimpleDocTemplate(
            temp_path,
            pagesize=A4,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
        )

        on_page = _build_header_footer_callback(
            certificate_number=_safe_str(report_data.certificate_number),
            total_pages_ref=total_pages_ref,
        )

        story = _build_pdf_story(report_data, styles, usable_width, label_col_narrow, label_col_wide)

        # First pass establishes page count.
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        total_pages_ref[0] = doc.page

        # Second pass so all footers show the correct total.
        story = _build_pdf_story(report_data, styles, usable_width, label_col_narrow, label_col_wide)
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

        safe_cert_number = "".join(
            ch for ch in _safe_str(report_data.certificate_number)
            if ch.isalnum() or ch in ("-", "_")
        )
        download_filename = f"CalibrationCertificate_{safe_cert_number}.pdf"

        return FileResponse(
            path=temp_path,
            media_type="application/pdf",
            filename=download_filename,
            background=_DeleteFileAfterResponse(temp_path),
        )

    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def _build_pdf_story(
    report_data: ReportData,
    styles: dict[str, ParagraphStyle],
    usable_width: float,
    label_col_narrow: float,
    label_col_wide: float,
) -> list:
    """Build the ordered list of Platypus flowables for the certificate.

    Args:
        report_data: Populated ReportData instance.
        styles: Paragraph style dict from _build_paragraph_styles.
        usable_width: Printable width in points.
        label_col_narrow: Width in points for narrow label columns.
        label_col_wide: Width in points for wide label columns.

    Returns:
        list: Ordered list of ReportLab Platypus flowables.
    """
    value_col_narrow = usable_width - label_col_narrow
    value_col_wide = usable_width - label_col_wide
    story = []

    def heading(text: str):
        story.append(Paragraph(text, styles["section_heading"]))

    def spacer():
        story.append(Spacer(1, 3 * mm))

    # Certificate details
    heading("Certificate Details")
    story.append(
        _build_kv_table(
            [
                ("Certificate No.:", _safe_str(report_data.certificate_number)),
                ("Date of Calibration:", _format_date(report_data.date_of_calibration)),
                ("Calibration Due Date:", _format_date(report_data.cal_due_date)),
                ("Item Received:", _format_date(report_data.item_received_date)),
                ("Date of Issue:", _format_date(report_data.date_of_issue)),
                ("Customer Name:", _safe_str(report_data.customer_name)),
                ("Customer Address:", _safe_str(report_data.customer_address)),
            ],
            styles,
            [label_col_narrow, value_col_narrow],
        )
    )

    # Instrument under test
    spacer()
    heading("Instrument Under Test")
    story.append(
        _build_kv_table(
            [
                ("Instrument Name:", _safe_str(report_data.instrument_name)),
                ("Make:", _safe_str(report_data.instrument_make)),
                ("Model:", _safe_str(report_data.instrument_model)),
                ("Serial Number:", _safe_str(report_data.instrument_serial_number)),
                ("Tag Number:", _safe_str(report_data.instrument_tag_number)),
            ],
            styles,
            [label_col_narrow, value_col_narrow],
        )
    )

    # Environmental conditions
    spacer()
    heading("Environmental Conditions at Time of Calibration")
    story.append(
        _build_kv_table(
            [
                ("Temperature (°C):", _safe_str(report_data.temperature_c)),
                ("Relative Humidity (%):", _safe_str(report_data.humidity_pct)),
            ],
            styles,
            [label_col_narrow, value_col_narrow],
        )
    )

    # Master instrument
    spacer()
    heading("Reference / Master Instrument")
    story.append(
        _build_kv_table(
            [
                ("Instrument Name:", _safe_str(report_data.master_name)),
                ("Serial Number:", _safe_str(report_data.master_serial_number)),
                ("Traceability Chain:", _safe_str(report_data.master_traceability_chain)),
                ("Claimed CMC:", _safe_str(report_data.master_claimed_cmc)),
            ],
            styles,
            [label_col_narrow, value_col_narrow],
        )
    )

    # Calibration readings
    spacer()
    heading("Calibration Readings")

    readings_header = [
        "Nominal Value",
        "Ascending\nMeasured",
        "Descending\nMeasured",
        "Mean Error",
        "Hysteresis",
    ]
    readings_table_data = [readings_header] + [
        [
            _safe_str(row.get("nominal_value")),
            _safe_str(row.get("measured_value_up")),      # matches database column
            _safe_str(row.get("measured_value_down")),    # matches database column
            _safe_str(row.get("mean_error")),
            _safe_str(row.get("hysteresis")),
        ]
        for row in report_data.readings
    ]
    col_w = usable_width / len(readings_header)
    readings_table = Table(
        readings_table_data,
        colWidths=[col_w] * len(readings_header),
        repeatRows=1,
    )
    readings_table.setStyle(_black_table_style(has_header_row=True))
    story.append(readings_table)

    # Uncertainty budget
    spacer()
    heading("Measurement Uncertainty Budget")
    story.append(
        _build_kv_table(
            [
                ("Type A Uncertainty (u_A):", _safe_str(report_data.type_a_value)),
                ("Standard Uncertainty (u_std):", _safe_str(report_data.u_std)),
                ("Resolution Uncertainty (u_res):", _safe_str(report_data.u_res)),
                ("Hysteresis Uncertainty (u_hys):", _safe_str(report_data.u_hys)),
                ("Zero Uncertainty (u_zero):", _safe_str(report_data.u_zero)),
                ("Temperature Uncertainty (u_temp):", _safe_str(report_data.u_temp)),
                ("CMC:", _safe_str(report_data.cmc)),
                ("Combined Uncertainty (u_c):", _safe_str(report_data.combined_uncertainty)),
                ("Expanded Uncertainty (U):", _safe_str(report_data.expanded_uncertainty)),
                ("Coverage Factor (k):", _safe_str(report_data.k_value)),
                ("Final Applied Uncertainty:", _safe_str(report_data.final_applied_uncertainty)),
            ],
            styles,
            [label_col_wide, value_col_wide],
        )
    )

    # Compliance statement
    spacer()
    heading("Compliance Statement")
    compliance_data = [
        [
            Paragraph("Compliance Status:", styles["body_bold"]),
            Paragraph(_safe_str(report_data.session_status), styles["body_bold"]),
        ]
    ]
    compliance_table = Table(compliance_data, colWidths=[label_col_wide, value_col_wide])
    compliance_table.setStyle(_kv_table_style())
    story.append(compliance_table)

    # Signature block
    spacer()
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BLACK))
    story.append(Spacer(1, 3 * mm))

    sig_data = [
        [
            Paragraph("Authorised Signatory", styles["body_bold"]),
            Paragraph("", styles["body"]),
            Paragraph("Date", styles["body_bold"]),
        ],
        ["", "", ""],
    ]
    sig_table = Table(sig_data, colWidths=[80 * mm, 20 * mm, usable_width - 100 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
                ("LINEBELOW", (0, 1), (0, 1), THIN_BORDER, BLACK),
                ("LINEBELOW", (2, 1), (2, 1), THIN_BORDER, BLACK),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.append(sig_table)

    return story


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — EXCEL GENERATION
# ══════════════════════════════════════════════════════════════════════════════


def generate_excel_report(session_id: str) -> FileResponse:
    """Generate an Excel calibration certificate for the given session.

    Args:
        session_id: UUID of the calibration session.

    Returns:
        FileResponse: Streaming .xlsx attachment.

    Raises:
        ValueError: When the session does not exist or has status REJECTED.
        RuntimeError: When a required database record is missing.
    """
    report_data = gather_report_data(session_id)

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Calibration Certificate"

    thin_side = Side(border_style="thin", color="000000")
    all_borders = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    title_font = Font(name="Calibri", bold=True, size=14, color="000000")
    section_font = Font(name="Calibri", bold=True, size=10, color="000000")
    label_font = Font(name="Calibri", bold=True, size=9, color="000000")
    value_font = Font(name="Calibri", size=9, color="000000")
    header_font = Font(name="Calibri", bold=True, size=9, color="FFFFFF")

    black_fill = PatternFill(fill_type="solid", fgColor="000000")
    grey_fill = PatternFill(fill_type="solid", fgColor="D9D9D9")

    LAST_COLUMN = 6

    def write_title(row_num: int, text: str) -> None:
        """Write a bold centred title merged across all columns.

        Args:
            row_num: 1-indexed worksheet row.
            text: Title text.
        """
        cell = worksheet.cell(row=row_num, column=1, value=text)
        cell.font = title_font
        cell.alignment = center_align
        worksheet.merge_cells(
            start_row=row_num, start_column=1, end_row=row_num, end_column=LAST_COLUMN
        )
        worksheet.row_dimensions[row_num].height = 24

    def write_section_heading(row_num: int, text: str) -> None:
        """Write a grey-filled section heading merged across all columns.

        Args:
            row_num: 1-indexed worksheet row.
            text: Heading text.
        """
        worksheet.merge_cells(
            start_row=row_num, start_column=1, end_row=row_num, end_column=LAST_COLUMN
        )
        for col in range(1, LAST_COLUMN + 1):
            cell = worksheet.cell(row=row_num, column=col)
            cell.fill = grey_fill
            cell.border = all_borders
        heading_cell = worksheet.cell(row=row_num, column=1, value=text)
        heading_cell.font = section_font
        heading_cell.alignment = left_align

    def write_label_value(row_num: int, label: str, value: Any) -> None:
        """Write a bold label in column A and its value merged across B-F.

        Args:
            row_num: 1-indexed worksheet row.
            label: Field label string.
            value: Field value; None is rendered as an empty string.
        """
        label_cell = worksheet.cell(row=row_num, column=1, value=label)
        label_cell.font = label_font
        label_cell.border = all_borders
        label_cell.alignment = left_align

        display_value = "" if value is None else str(value)
        worksheet.merge_cells(
            start_row=row_num, start_column=2, end_row=row_num, end_column=LAST_COLUMN
        )
        for col in range(2, LAST_COLUMN + 1):
            cell = worksheet.cell(row=row_num, column=col)
            cell.border = all_borders
        value_cell = worksheet.cell(row=row_num, column=2, value=display_value)
        value_cell.font = value_font
        value_cell.alignment = left_align

    def write_table_header(row_num: int, column_labels: list[str]) -> None:
        """Write a black-filled header row with white bold text.

        Args:
            row_num: 1-indexed worksheet row.
            column_labels: Ordered column label strings.
        """
        for col_index, label_text in enumerate(column_labels, start=1):
            cell = worksheet.cell(row=row_num, column=col_index, value=label_text)
            cell.font = header_font
            cell.fill = black_fill
            cell.alignment = center_align
            cell.border = all_borders

    def write_data_row(row_num: int, values: list[Any]) -> None:
        """Write a plain data row with borders across all provided columns.

        Args:
            row_num: 1-indexed worksheet row.
            values: Ordered cell values.
        """
        for col_index, cell_value in enumerate(values, start=1):
            cell = worksheet.cell(
                row=row_num,
                column=col_index,
                value="" if cell_value is None else cell_value,
            )
            cell.font = value_font
            cell.alignment = left_align
            cell.border = all_borders

    worksheet.column_dimensions["A"].width = 36
    worksheet.column_dimensions["B"].width = 20
    worksheet.column_dimensions["C"].width = 20
    worksheet.column_dimensions["D"].width = 20
    worksheet.column_dimensions["E"].width = 20
    worksheet.column_dimensions["F"].width = 20

    current_row = 1

    write_title(current_row, "CALIBRATION CERTIFICATE")
    current_row += 2

    write_section_heading(current_row, "Certificate Details")
    current_row += 1

    for label, value in [
        ("Certificate No.", report_data.certificate_number),
        ("Date of Calibration", _format_date(report_data.date_of_calibration)),
        ("Calibration Due Date", _format_date(report_data.cal_due_date)),
        ("Item Received Date", _format_date(report_data.item_received_date)),
        ("Date of Issue", _format_date(report_data.date_of_issue)),
        ("Customer Name", report_data.customer_name),
        ("Customer Address", report_data.customer_address),
    ]:
        write_label_value(current_row, label, value)
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Instrument Under Test")
    current_row += 1

    for label, value in [
        ("Instrument Name", report_data.instrument_name),
        ("Make", report_data.instrument_make),
        ("Model", report_data.instrument_model),
        ("Serial Number", report_data.instrument_serial_number),
        ("Tag Number", report_data.instrument_tag_number),
    ]:
        write_label_value(current_row, label, value)
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Environmental Conditions")
    current_row += 1

    for label, value in [
        ("Temperature (°C)", report_data.temperature_c),
        ("Relative Humidity (%)", report_data.humidity_pct),
    ]:
        write_label_value(current_row, label, value)
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Reference / Master Instrument")
    current_row += 1

    for label, value in [
        ("Instrument Name", report_data.master_name),
        ("Serial Number", report_data.master_serial_number),
        ("Traceability Chain", report_data.master_traceability_chain),
        ("Claimed CMC", report_data.master_claimed_cmc),
    ]:
        write_label_value(current_row, label, value)
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Calibration Readings")
    current_row += 1

    write_table_header(
        current_row,
        ["Nominal Value", "Ascending Measured", "Descending Measured", "Mean Error", "Hysteresis"],
    )
    current_row += 1

    for reading_row in report_data.readings:
        write_data_row(
            current_row,
            [
                reading_row.get("nominal_value"),
                reading_row.get("measured_value_up"),      # matches database column
                reading_row.get("measured_value_down"),    # matches database column
                reading_row.get("mean_error"),
                reading_row.get("hysteresis"),
            ],
        )
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Measurement Uncertainty Budget")
    current_row += 1

    for label, value in [
        ("Type A Uncertainty (u_A)", report_data.type_a_value),
        ("Standard Uncertainty (u_std)", report_data.u_std),
        ("Resolution Uncertainty (u_res)", report_data.u_res),
        ("Hysteresis Uncertainty (u_hys)", report_data.u_hys),
        ("Zero Uncertainty (u_zero)", report_data.u_zero),
        ("Temperature Uncertainty (u_temp)", report_data.u_temp),
        ("CMC", report_data.cmc),
        ("Combined Uncertainty (u_c)", report_data.combined_uncertainty),
        ("Expanded Uncertainty (U)", report_data.expanded_uncertainty),
        ("Coverage Factor (k)", report_data.k_value),
        ("Final Applied Uncertainty", report_data.final_applied_uncertainty),
    ]:
        write_label_value(current_row, label, value)
        current_row += 1

    current_row += 1

    write_section_heading(current_row, "Compliance Statement")
    current_row += 1

    label_cell = worksheet.cell(row=current_row, column=1, value="Compliance Status")
    label_cell.font = label_font
    label_cell.border = all_borders
    label_cell.alignment = left_align

    worksheet.merge_cells(
        start_row=current_row, start_column=2, end_row=current_row, end_column=LAST_COLUMN
    )
    for col in range(2, LAST_COLUMN + 1):
        worksheet.cell(row=current_row, column=col).border = all_borders
    compliance_value_cell = worksheet.cell(
        row=current_row, column=2, value=_safe_str(report_data.session_status)
    )
    compliance_value_cell.font = Font(name="Calibri", bold=True, size=9, color="000000")
    compliance_value_cell.alignment = left_align

    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".xlsx", prefix=f"cal_cert_{session_id}_"
    )
    temp_path = temp_file.name
    temp_file.close()

    try:
        workbook.save(temp_path)

        safe_cert_number = "".join(
            ch for ch in _safe_str(report_data.certificate_number)
            if ch.isalnum() or ch in ("-", "_")
        )
        download_filename = f"CalibrationCertificate_{safe_cert_number}.xlsx"

        return FileResponse(
            path=temp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=download_filename,
            background=_DeleteFileAfterResponse(temp_path),
        )

    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════════════


def write_audit_entry(
    session_id: str,
    report_format: str,
    user_id: str,
) -> None:
    """Record a certificate generation event to the audit log.

    Args:
        session_id: UUID of the calibration session that was reported on.
        report_format: Format string indicating the output type, e.g. "PDF" or "EXCEL".
        user_id: UUID of the user who triggered the download.

    Returns:
        None

    Raises:
        RuntimeError: If the database write fails.
    """
    audit_payload = {
        "user_id": user_id,                                         # matches audit_log.user_id
        "action": f"CERTIFICATE_GENERATED_{report_format.upper()}", # matches audit_log.action
        "table_affected": "calibration_sessions",                   # matches audit_log.table_affected
        "record_id": session_id,                                    # matches audit_log.record_id
    }

    insert_audit_log(audit_payload)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════


class _DeleteFileAfterResponse:
    """Starlette background task that deletes a temp file after the response is sent.

    Args:
        file_path: Absolute path of the file to delete.
    """

    def _init_(self, file_path: str) -> None:
        self._file_path = file_path

    async def _call_(self) -> None:
        """Delete the file; log a warning on failure without raising.

        Returns:
            None
        """
        try:
            if os.path.exists(self._file_path):
                os.unlink(self._file_path)
        except OSError:
            logger.warning(
                "Failed to delete temporary report file: %s",
                self._file_path,
                exc_info=True,
            )