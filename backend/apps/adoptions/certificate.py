"""A letter-style certificate of one completed adoption."""
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import mm

from apps.reports.documents import (
    Signatures, build_letter, date_label, name, rule, section, styles, text,
)


def build_single_adoption_pdf(record):
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
        timestamp = timezone.localtime(record.completed_at).strftime('%d %B %Y, %H:%M %Z')
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
    return build_letter(story, 'Certificate of Adoption', reference)
