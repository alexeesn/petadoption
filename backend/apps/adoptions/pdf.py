"""
Server-side PDF generation for the Adoption Records export.

Mirrors the payment records exporter (``apps.payments.pdf``): renders already
persisted ``AdoptionRecord`` rows into an A4 PDF.  This module only *reads*
records — it never creates, completes, returns, or cancels adoptions, and it
never generates or modifies permanent transaction IDs (those are owned by the
adoption completion service).
"""
import io
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import AdoptionRecord

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm

# Usable width for a 210 mm A4 page with 16 mm margins on each side.
TABLE_COLUMN_WIDTHS = [30 * mm, 20 * mm, 32 * mm, 18 * mm, 24 * mm, 24 * mm, 20 * mm]

TABLE_HEADERS = [
    "Transaction ID",
    "Pet",
    "Adopter",
    "Status",
    "Completed",
    "Completed by",
    "Appointment",
]

STATUS_COLOURS = {
    AdoptionRecord.Status.SCHEDULED: colors.HexColor("#1d4ed8"),
    AdoptionRecord.Status.COMPLETED: colors.HexColor("#157f4b"),
    AdoptionRecord.Status.CANCELLED: colors.HexColor("#6b7280"),
    AdoptionRecord.Status.RETURNED: colors.HexColor("#7e22ce"),
}


def _cell(text, style):
    return Paragraph(escape(str(text or "—")), style)


def _short_id(value):
    value = str(value)
    return f"{value[:8]}…" if len(value) > 8 else value


def _completed_label(record):
    """Human-readable completion stamp, only for completed records."""
    if record.status != AdoptionRecord.Status.COMPLETED:
        return ""
    if record.completed_at:
        return timezone.localtime(record.completed_at).strftime("%Y-%m-%d %H:%M")
    if record.completed_date:
        return record.completed_date.isoformat()
    return ""


def build_adoption_records_pdf(records, filters=()):
    """Render *records* into an A4 PDF report and return the bytes.

    ``filters`` is an optional iterable of short human-readable strings that
    describe the active export filters (e.g. ``["Status: completed"]``); they
    are printed under the heading so the report always states what it covers.
    """
    cell_style = ParagraphStyle(
        "PdfCell",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.black,
    )
    header_style = ParagraphStyle(
        "PdfHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    def _page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawCentredString(
            PAGE_WIDTH / 2, 10 * mm, f"Page {doc.page} · PawConnect — Adoption Records"
        )
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="PawConnect - Adoption Records Report",
        author="PawConnect Staff Portal",
    )

    generated = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")

    story = []
    story.append(
        Paragraph(
            "PawConnect",
            ParagraphStyle(
                "Title", fontName="Helvetica-Bold", fontSize=19, leading=24,
                textColor=colors.HexColor("#1f2937"),
            ),
        )
    )
    story.append(
        Paragraph(
            "Adoption Records Report",
            ParagraphStyle(
                "Heading", fontName="Helvetica-Bold", fontSize=13, leading=17,
                spaceAfter=2, textColor=colors.HexColor("#374151"),
            ),
        )
    )
    story.append(
        Paragraph(
            f"Generated on {escape(generated)}",
            ParagraphStyle(
                "Meta", fontSize=8.5, leading=11, textColor=colors.HexColor("#6b7280")
            ),
        )
    )
    if filters:
        story.append(
            Paragraph(
                f"Filters: {'; '.join(escape(f) for f in filters)}",
                ParagraphStyle(
                    "MetaF", fontSize=8.5, leading=11, textColor=colors.HexColor("#6b7280")
                ),
            )
        )
    story.append(Spacer(1, 4 * mm))
    if not records:
        story.append(
            Paragraph(
                "No adoption records match the selected filters.",
                ParagraphStyle(
                    "Empty", fontSize=10, leading=13, textColor=colors.HexColor("#6b7280")
                ),
            )
        )
    else:
        body = [[_cell(h, header_style) for h in TABLE_HEADERS]]
        for record in records:
            completed = record.status == AdoptionRecord.Status.COMPLETED
            body.append([
                _cell(record.transaction_id, cell_style),
                _cell(f"{record.pet.name}\n({_short_id(record.pet_id)})", cell_style),
                _cell(f"{record.adopter.email}\n({_short_id(record.adopter_id)})", cell_style),
                _cell(record.get_status_display(), cell_style),
                _cell(_completed_label(record), cell_style),
                _cell(
                    record.staff_member.email if completed and record.staff_member_id else "",
                    cell_style,
                ),
                _cell(
                    record.appointment.requested_date.isoformat()
                    if record.appointment_id and record.appointment
                    else "",
                    cell_style,
                ),
            ])

        table = Table(body, colWidths=TABLE_COLUMN_WIDTHS, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5),
            ("TOPPADDING", (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        for idx, record in enumerate(records, start=1):
            colour = STATUS_COLOURS.get(record.status, colors.HexColor("#6b7280"))
            table.setStyle(TableStyle([("TEXTCOLOR", (3, idx), (3, idx), colour)]))
        story.append(table)

        counts = {value: 0 for value in AdoptionRecord.Status.values}
        for record in records:
            counts[record.status] += 1
        labels = dict(AdoptionRecord.Status.choices)
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                f"Total adoption records: {len(records)} (" +
                "; ".join(f"{labels[s]}: {counts[s]}" for s in counts) + ")",
                ParagraphStyle(
                    "Total", fontSize=8.5, leading=11, textColor=colors.HexColor("#374151")
                ),
            )
        )

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()



def build_single_adoption_pdf(record):
    """Render a single AdoptionRecord into an A4 PDF."""
    cell_style = ParagraphStyle(
        "PdfCell", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.black,
    )
    label_style = ParagraphStyle(
        "PdfLabel", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#374151"),
    )

    def _page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, "PawConnect \u2014 Adoption Record")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title="PawConnect - Adoption Record",
        author="PawConnect Staff Portal",
    )
    generated = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
    story = []
    story.append(Paragraph("PawConnect", ParagraphStyle(
        "SingleTitle", fontName="Helvetica-Bold", fontSize=19, leading=24,
        textColor=colors.HexColor("#1f2937"),
    )))
    story.append(Paragraph("Adoption Record", ParagraphStyle(
        "SingleHeading", fontName="Helvetica-Bold", fontSize=13, leading=17,
        spaceAfter=2, textColor=colors.HexColor("#374151"),
    )))
    story.append(Paragraph(f"Generated on {escape(generated)}", ParagraphStyle(
        "SingleMeta", fontSize=8.5, leading=11, textColor=colors.HexColor("#6b7280"),
    )))
    story.append(Spacer(1, 5 * mm))

    rows = [
        ("Transaction ID", str(record.transaction_id or "\u2014")),
        ("Pet", record.pet.name),
        ("Adopter", record.adopter.email),
        ("Status", record.get_status_display()),
        ("Completed", _completed_label(record) or "\u2014"),
        ("Completed By", record.staff_member.email if record.status == AdoptionRecord.Status.COMPLETED and record.staff_member_id else "\u2014"),
        ("Appointment Date", record.appointment.requested_date.isoformat() if record.appointment_id and record.appointment else "\u2014"),
        ("Adoption Date", record.adoption_date.isoformat() if record.adoption_date else "\u2014"),
        ("Notes", record.notes or "\u2014"),
    ]
    tdata = [[_cell(k, label_style), _cell(v, cell_style)] for k, v in rows]
    table = Table(tdata, colWidths=[50 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def build_single_adoption_pdf(record):
    """Render a single AdoptionRecord into an A4 PDF document.

    Only contains the selected completed adoption and its real persisted details.
    """
    cell_style = ParagraphStyle(
        "PdfCell",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
    )
    label_style = ParagraphStyle(
        "PdfLabel",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )

    def _page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, "PawConnect — Adoption Record Certificate")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"PawConnect - Adoption Record {record.transaction_id or record.id}",
        author="PawConnect Staff Portal",
    )
    generated = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
    story = [
        Paragraph(
            "PawConnect",
            ParagraphStyle(
                "Title",
                fontName="Helvetica-Bold",
                fontSize=19,
                leading=24,
                textColor=colors.HexColor("#1f2937"),
            ),
        ),
        Paragraph(
            "Official Adoption Record",
            ParagraphStyle(
                "Heading",
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=17,
                spaceAfter=2,
                textColor=colors.HexColor("#374151"),
            ),
        ),
        Paragraph(
            f"Generated on {escape(generated)}",
            ParagraphStyle(
                "Meta", fontSize=8.5, leading=11, textColor=colors.HexColor("#6b7280")
            ),
        ),
        Spacer(1, 5 * mm),
    ]

    pet_name = f"{record.pet.name} ({record.pet.species.capitalize()})" if (record.pet) else "—"
    adopter_name = getattr(record.adopter, "full_name", "") or record.adopter.email
    adopter_str = f"{adopter_name} ({record.adopter.email})" if record.adopter else "—"
    app_ref = f"{str(record.application_id)[:8]}…" if record.application_id else "—"
    completed_str = _completed_label(record) or "—"
    staff_str = record.staff_member.email if record.staff_member else "—"
    appt_str = (
        record.appointment.requested_date.isoformat()
        if (record.appointment_id and record.appointment)
        else "—"
    )
    adoption_date_str = record.adoption_date.isoformat() if record.adoption_date else "—"

    rows = [
        ("Transaction ID", record.transaction_id or "—"),
        ("Adoption Status", record.get_status_display()),
        ("Pet", pet_name),
        ("Adopter", adopter_str),
        ("Application Reference", app_ref),
        ("Adoption Date", adoption_date_str),
        ("Finalized / Completed", completed_str),
        ("Handled By Staff", staff_str),
        ("Appointment Visit Date", appt_str),
        ("Notes", record.notes or "—"),
    ]
    tdata = [[_cell(k, label_style), _cell(v, cell_style)] for k, v in rows]
    table = Table(tdata, colWidths=[50 * mm, 120 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()

