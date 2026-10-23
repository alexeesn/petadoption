"""A letter-style certificate of one completed adoption."""
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import mm

from apps.reports.documents import (
    Signatures, build_letter, date_label, name, rule, section, styles, text,
    PHILIPPINE_TIMEZONE,
)


def build_single_adoption_pdf(record, *, downloaded_by=None):
    style = styles()
    pet = record.pet
    adopter = record.adopter
    reference = record.transaction_id or str(record.pk)
    completed_date = record.completed_at or record.completed_date
    profile = [pet.get_species_display()]
    if pet.breed:
        profile.append(pet.breed)
    if pet.gender != 'unknown':
        profile.append(pet.get_gender_display())
    if pet.age_years or pet.age_months:
        profile.append(pet.formatted_age)
    if pet.weight_kg is not None:
        profile.append(f'{pet.weight_kg} kg')

    story = [
        Paragraph('Certificate of Adoption', style['title']),
        Paragraph(f'Transaction reference <b>{text(reference)}</b>', style['body']),
        rule(),
        Paragraph('THIS CERTIFIES THAT', style['label']),
        Paragraph(text(name(adopter)), style['name']),
        Paragraph(text(adopter.email), style['small']),
        Spacer(1, 3 * mm),
        Paragraph('has completed the adoption of', style['body']),
        Paragraph(text(pet.name), style['pet']),
        Paragraph(text(' / '.join(profile)), style['small']),
        Spacer(1, 4 * mm),
    ]
    completion = f' on <b>{text(date_label(completed_date))}</b>' if completed_date else ''
    story.append(Paragraph(
        f'PawConnect confirms that the adoption of <b>{text(pet.name)}</b> by '
        f'<b>{text(name(adopter))}</b> was recorded as completed{completion}. '
        'This certificate documents the completed adoption transaction identified above.',
        style['body'],
    ))
    if record.staff_member:
        story.append(Paragraph(
            f'The adoption was finalized by <b>{text(name(record.staff_member))}</b>. '
            'Please retain this certificate with your adoption documents.', style['body'],
        ))

    dates = []
    if record.completed_at:
        timestamp = timezone.localtime(record.completed_at, PHILIPPINE_TIMEZONE).strftime('%d %B %Y, %H:%M PHT')
        dates.append(f'<b>Completion recorded:</b> {text(timestamp)}')
    elif record.completed_date:
        dates.append(f'<b>Completion recorded:</b> {text(date_label(record.completed_date))}')
    if record.adoption_date:
        dates.append(f'<b>Adoption date:</b> {text(date_label(record.adoption_date))}')
    if record.appointment_id:
        dates.append(f'<b>Appointment visit:</b> {text(date_label(record.appointment.requested_date))}')
    if dates:
        story.append(Paragraph('<br/>'.join(dates), style['small']))
    if record.notes.strip():
        story.extend(section('Adoption notes', text(record.notes)))
    story.append(Signatures(adopter, record.staff_member, 'Adopter acknowledgment', 'Adoption staff confirmation'))
    story.append(rule())
    story.append(Paragraph(
        f'<b>Application reference:</b> {text(record.application_id)}<br/>'
        f'<b>Adoption record ID:</b> {text(record.pk)}<br/>'
        f'<b>Pet ID:</b> {text(pet.pk)}', style['small'],
    ))
    return build_letter(story, 'Certificate of Adoption', reference, downloaded_by=downloaded_by)


def build_returned_adoption_pdf(record, *, downloaded_by=None):
    """A return acknowledgment, preserving the original completed transaction."""
    style = styles()
    reference = record.transaction_id or str(record.pk)
    story = [
        Paragraph('Adoption Return Record', style['title']),
        Paragraph(f'Transaction reference <b>{text(reference)}</b>', style['body']),
        Paragraph('<b>Current adoption status: Returned</b>', style['body']),
        rule(),
        Paragraph(text(record.pet.name), style['pet']),
        Paragraph(f'Adopter: <b>{text(name(record.adopter))}</b><br/>{text(record.adopter.email)}', style['body']),
        Paragraph(
            f'PawConnect records that <b>{text(record.pet.name)}</b> was returned to the shelter '
            f'following the completed adoption by <b>{text(name(record.adopter))}</b>. '
            'This document acknowledges the return and retains the original adoption reference.',
            style['body'],
        ),
    ]
    story.extend(section('Return details',
        f'<b>Return date:</b> {text(date_label(record.return_date))}<br/>'
        f'<b>Return recorded:</b> {text(timezone.localtime(record.returned_at, PHILIPPINE_TIMEZONE).strftime("%d %B %Y, %H:%M PHT") if record.returned_at else "Not recorded")}<br/>'
        f'<b>Reason:</b> {text(record.return_reason)}',
    ))
    story.extend(section('Original adoption',
        f'<b>Completed on:</b> {text(date_label(record.completed_at or record.completed_date))}<br/>'
        f'<b>Originally completed by:</b> {text(name(record.staff_member))}<br/>'
        f'<b>Application reference:</b> {text(record.application_id)}<br/>'
        f'<b>Adoption record ID:</b> {text(record.pk)}',
    ))
    story.extend(section('Payment history',
        'Existing payment records and receipt references are retained. '
        'Returning the pet does not automatically issue a refund. This document is not a refund receipt.',
    ))
    return build_letter(story, 'Adoption Return Record', reference, downloaded_by=downloaded_by)


def build_cancelled_adoption_pdf(record, *, downloaded_by=None):
    """A cancellation acknowledgment, separate from a completed-adoption certificate."""
    style = styles()
    reference = record.transaction_id or str(record.pk)
    cancelled = (
        timezone.localtime(record.cancelled_at, PHILIPPINE_TIMEZONE).strftime('%d %B %Y, %H:%M PHT')
        if record.cancelled_at else 'Not recorded'
    )
    story = [
        Paragraph('Adoption Cancellation Record', style['title']),
        Paragraph(f'Adoption reference <b>{text(reference)}</b>', style['body']),
        Paragraph('<b>Current adoption status: Cancelled</b>', style['body']),
        rule(),
        Paragraph(text(record.pet.name), style['pet']),
        Paragraph(f'Adopter: <b>{text(name(record.adopter))}</b><br/>{text(record.adopter.email)}', style['body']),
        Paragraph(
            f'PawConnect records that the scheduled adoption of <b>{text(record.pet.name)}</b> '
            f'by <b>{text(name(record.adopter))}</b> was cancelled. '
            'This document acknowledges the cancellation of that scheduled adoption.',
            style['body'],
        ),
    ]
    story.extend(section('Cancellation details',
        f'<b>Cancellation recorded:</b> {text(cancelled)}<br/>'
        f'<b>Reason:</b> {text(record.cancellation_reason)}',
    ))
    story.extend(section('Original schedule',
        f'<b>Scheduled adoption date:</b> {text(date_label(record.adoption_date))}<br/>'
        f'<b>Scheduling staff:</b> {text(name(record.staff_member))}<br/>'
        f'<b>Application reference:</b> {text(record.application_id)}<br/>'
        f'<b>Adoption record ID:</b> {text(record.pk)}',
    ))
    story.extend(section('Payment history',
        'Existing payment records and receipt references are retained. '
        'Cancellation does not issue a refund. This document is not a payment or refund receipt.',
    ))
    return build_letter(story, 'Adoption Cancellation Record', reference, downloaded_by=downloaded_by)
