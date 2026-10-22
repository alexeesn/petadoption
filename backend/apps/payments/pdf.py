"""
Server-side PDF generation for the Payment Records export.

This module only renders already-persisted ``Payment`` rows into an A4 PDF; it
never changes amounts, statuses, receipt numbers, or any other payment fields
(those are owned by the payment workflows, never by reports).  Only a staff
member can trigger this through the staff-authorized export endpoint.
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

from .models import Payment

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm

# Usable width for a 210 mm A4 page with 16 mm margins on each side.
TABLE_COLUMN_WIDTHS = [28 * mm, 20 * mm, 32 * mm, 18 * mm, 20 * mm, 20 * mm, 22 * mm, 28 * mm]

TABLE_HEADERS = [
    "Receipt / Ref",
    "Pet",
    "Adopter",
    "Amount",
    "Method",
    "Status",
    "Payment date",
    "Processed by",
]

STATUS_COLOURS = {
    Payment.Status.COMPLETED: colors.HexColor("#157f4b"),
    Payment.Status.PENDING: colors.HexColor("#b7791f"),
    Payment.Status.FAILED: colors.HexColor("#b42318"),
    Payment.Status.REFUNDED: colors.HexColor("#6b7280"),
    Payment.Status.CANCELLED: colors.HexColor("#6b7280"),
}


def _cell(text, style):
    return Paragraph(escape(str(text or "—")), style)


def _money(value):
    return f"₱{value:.2f}"


def build_payment_records_pdf(payments, filters=()):
    """Render *payments* into an A4 PDF report and return the bytes.

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
            PAGE_WIDTH / 2, 10 * mm, f"Page {doc.page} · PawConnect — Payment Records"
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
        title="PawConnect - Payment Records Report",
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
            "Payment Records Report",
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
    if not payments:
        story.append(
            Paragraph(
                "No payment records match the selected filters.",
                ParagraphStyle(
                    "Empty", fontSize=10, leading=13, textColor=colors.HexColor("#6b7280")
                ),
            )
        )
    else:
        body = [[_cell(h, header_style) for h in TABLE_HEADERS]]
        for payment in payments:
            app = payment.application
            body.append([
                _cell(payment.receipt_number or payment.reference_number, cell_style),
                _cell(app.pet.name, cell_style),
                _cell(app.adopter.email, cell_style),
                _cell(_money(payment.amount), cell_style),
                _cell(payment.get_method_display(), cell_style),
                _cell(payment.get_status_display(), cell_style),
                _cell(payment.payment_date.isoformat() if payment.payment_date else "", cell_style),
                _cell(payment.processed_by.email if payment.processed_by_id else "", cell_style),
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
        for idx, payment in enumerate(payments, start=1):
            colour = STATUS_COLOURS.get(payment.status, colors.HexColor("#6b7280"))
            table.setStyle(TableStyle([("TEXTCOLOR", (5, idx), (5, idx), colour)]))
        story.append(table)

        completed_count = sum(1 for p in payments if p.status == Payment.Status.COMPLETED)
        total = sum(p.amount for p in payments if p.status == Payment.Status.COMPLETED)
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                f"Total completed payments: {escape(_money(total))} "
                f"({completed_count} records)",
                ParagraphStyle(
                    "Total", fontSize=8.5, leading=11, textColor=colors.HexColor("#374151")
                ),
            )
        )

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()