"""Server-rendered exports of the complete filtered operational report."""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from .documents import download_details, name, styles, text


def build_operational_pdf(definition, rows, stats, filters, user):
    style = styles()
    cell = ParagraphStyle('OperationalCell', parent=style['small'], fontSize=7, leading=10, spaceAfter=0)
    header = ParagraphStyle('OperationalHeader', parent=cell, textColor=colors.white, fontName='PawConnectBold')
    story = [Paragraph('PawConnect', style['title']), Paragraph(text(definition.title), style['name']), Paragraph(text(definition.description), style['small'])]
    story += [Paragraph(text(label), style['small']) for label in filters]
    story += [Paragraph(text(' | '.join(f"{s['label']}: {s['value']}" for s in stats)), style['small']), *download_details(user), Spacer(1, 5 * mm)]
    table_data = [[Paragraph(text(column['label']), header) for column in definition.columns]]
    for row in rows:
        table_data.append([Paragraph(text(row.get(column['key'])), cell) for column in definition.columns])
    if len(table_data) == 1:
        story.append(Paragraph('No matching records.', style['body']))
    else:
        table = LongTable(table_data, colWidths=[265 * mm / len(definition.columns)] * len(definition.columns), repeatRows=1, splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#203B30')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#CFD8D0')), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
        story.append(table)
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=f'PawConnect - {definition.title}', author=name(user))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('PawConnectRegular', 7)
        canvas.drawRightString(281 * mm, 9 * mm, f'Page {doc.page}')
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
