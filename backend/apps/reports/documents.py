"""Shared letterhead and typography for individual transaction documents."""
import io
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from django.utils import timezone
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate

INK = colors.HexColor('#203B30')
TEXT = colors.HexColor('#303934')
MUTED = colors.HexColor('#67716B')
RULE = colors.HexColor('#CFD8D0')
ACCENT = colors.HexColor('#A58953')
PHILIPPINE_TIMEZONE = ZoneInfo('Asia/Manila')


def philippine_now():
    return timezone.localtime(timezone.now(), PHILIPPINE_TIMEZONE)


def download_details(user, generated_at=None):
    """Attribute an export to the authenticated downloader, separate from its recorder."""
    generated_at = generated_at or philippine_now()
    role = f' ({text(user.get_role_display())})' if user else ''
    return [
        Paragraph(f'<b>Downloaded by:</b> {person(user)}{role}', styles()['small']),
        Paragraph(f'<b>Generated on:</b> {text(generated_at.strftime("%d %B %Y, %H:%M:%S"))} PHT (UTC+08:00)', styles()['small']),
    ]


def text(value):
    """Escape saved values before placing them in ReportLab paragraph markup."""
    return escape(str(value if value is not None and value != '' else 'Not recorded')).replace('\n', '<br/>')


def name(user):
    """Capitalize lowercase name parts for PDF display, retaining intentional casing."""
    if not user:
        return 'Not recorded'
    full_name = user.full_name.strip()
    if not full_name:
        return user.email
    return ' '.join(part.title() if part.islower() else part for part in full_name.split())


def person(user):
    label = text(name(user))
    if user and user.email != name(user):
        label += f'<br/>{text(user.email)}'
    return label


def date_label(value):
    if value is None:
        return 'Not recorded'
    if isinstance(value, datetime) and timezone.is_aware(value):
        value = timezone.localtime(value, PHILIPPINE_TIMEZONE)
    return value.strftime('%d %B %Y')


@lru_cache(maxsize=1)
def styles():
    # Embed the fonts shipped with ReportLab. Documents stay portable without
    # depending on Windows fonts or downloading assets at export time.
    fonts = Path(reportlab.__file__).parent / 'fonts'
    for suffix, filename in [('Regular', 'Vera.ttf'), ('Bold', 'VeraBd.ttf'), ('Italic', 'VeraIt.ttf'), ('BoldItalic', 'VeraBI.ttf')]:
        pdfmetrics.registerFont(TTFont(f'PawConnect{suffix}', str(fonts / filename)))
    pdfmetrics.registerFontFamily('PawConnectRegular', normal='PawConnectRegular', bold='PawConnectBold', italic='PawConnectItalic', boldItalic='PawConnectBoldItalic')
    base = ParagraphStyle('DocumentBody', fontName='PawConnectRegular', fontSize=10, leading=16, textColor=TEXT, spaceAfter=4 * mm, splitLongWords=True)
    return {
        'body': base,
        'label': ParagraphStyle('DocumentLabel', parent=base, fontName='PawConnectBold', fontSize=8, leading=12, textColor=MUTED, spaceAfter=2 * mm, keepWithNext=True),
        'title': ParagraphStyle('DocumentTitle', parent=base, fontName='Times-Roman', fontSize=30, leading=35, textColor=INK, spaceAfter=4 * mm),
        'name': ParagraphStyle('DocumentName', parent=base, fontName='PawConnectBold', fontSize=17, leading=24, textColor=INK, spaceAfter=2 * mm),
        'pet': ParagraphStyle('DocumentPet', parent=base, fontName='Times-Roman', fontSize=28, leading=33, textColor=INK, spaceAfter=2 * mm),
        'amount': ParagraphStyle('DocumentAmount', parent=base, fontName='PawConnectBold', fontSize=25, leading=32, textColor=INK, spaceAfter=2 * mm),
        'small': ParagraphStyle('DocumentSmall', parent=base, fontSize=8, leading=12, textColor=MUTED, spaceAfter=2 * mm),
        'signature': ParagraphStyle('DocumentSignature', parent=base, fontSize=9, leading=13, spaceAfter=0),
    }


def rule():
    return HRFlowable(width='100%', thickness=0.6, color=RULE, spaceBefore=2 * mm, spaceAfter=5 * mm)


def section(title, content):
    style = styles()
    return [Paragraph(text(title.upper()), style['label']), Paragraph(content, style['body'])]


class Signatures(Flowable):
    """Two open signature lines with wrapping, real printed names below."""
    def __init__(self, left_user, right_user, left_role, right_role):
        super().__init__()
        style = styles()
        self.names = [Paragraph(person(user), style['signature']) for user in [left_user, right_user]]
        self.roles = [Paragraph(text(role) + '<br/>Signature / date', style['small']) for role in [left_role, right_role]]

    def wrap(self, available_width, available_height):
        self.width = available_width
        self.column_width = (available_width - 16 * mm) / 2
        self.name_heights = [paragraph.wrap(self.column_width, available_height)[1] for paragraph in self.names]
        self.role_heights = [paragraph.wrap(self.column_width, available_height)[1] for paragraph in self.roles]
        self.height = 17 * mm + max(n + r for n, r in zip(self.name_heights, self.role_heights))
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.7)
        line_y = self.height - 12 * mm
        for index, x in enumerate([0, self.column_width + 16 * mm]):
            canvas.line(x, line_y, x + self.column_width, line_y)
            name_y = line_y - 3 * mm - self.name_heights[index]
            self.names[index].drawOn(canvas, x, name_y)
            self.roles[index].drawOn(canvas, x, name_y - 2 * mm - self.role_heights[index])
        canvas.restoreState()


def build_letter(story, title, reference, *, downloaded_by=None):
    """Render flowing content with a repeated letterhead and numbered footer."""
    styles()
    buffer = io.BytesIO()
    margin = 22 * mm
    width, height = A4
    generated_at = philippine_now()
    generated = generated_at.strftime('%d %b %Y, %H:%M PHT')
    story = [*story, KeepTogether([rule(), *download_details(downloaded_by, generated_at)])]

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(INK)
        canvas.setFont('PawConnectBold', 20)
        canvas.drawString(margin, height - 21 * mm, 'PawConnect')
        canvas.setFont('PawConnectRegular', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, height - 27 * mm, 'PET ADOPTION MANAGEMENT')
        canvas.setFont('PawConnectBold', 7.5)
        canvas.drawRightString(width - margin, height - 20 * mm, 'TRANSACTION DOCUMENT')
        canvas.setFont('PawConnectRegular', 8)
        canvas.drawRightString(width - margin, height - 26 * mm, f'Generated {generated}')
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1)
        canvas.line(margin, height - 33 * mm, width - margin, height - 33 * mm)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(margin, 19 * mm, width - margin, 19 * mm)
        canvas.setFont('PawConnectRegular', 7)
        footer_reference = reference if len(reference) <= 40 else reference[:37] + '...'
        canvas.drawString(margin, 14 * mm, f'PawConnect / {footer_reference}')
        canvas.drawRightString(width - margin, 14 * mm, f'Page {doc.page}')
        canvas.restoreState()

    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=margin, rightMargin=margin,
        topMargin=42 * mm, bottomMargin=26 * mm,
        title=f'PawConnect - {title} - {reference}', author=name(downloaded_by),
    )
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
