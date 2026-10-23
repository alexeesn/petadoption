"""Letter-style receipts for one saved payment; no transaction mutations."""
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import mm

from apps.reports.documents import (
    Signatures, build_letter, date_label, name, rule, section, styles, text,
)
from .models import Payment


def build_single_receipt_pdf(payment):
    style = styles()
    application = payment.application
    adopter = application.adopter
    pet = application.pet
    paid = payment.status == Payment.Status.COMPLETED and payment.amount > 0
    title = 'Payment Receipt' if paid else 'Payment Transaction Record'
    reference = payment.receipt_number or payment.reference_number or str(payment.pk)
    amount = f'PHP {payment.amount:,.2f}'

    story = [
        Paragraph(title, style['title']),
        Paragraph(f"{'Receipt no.' if payment.receipt_number else 'Reference'} <b>{text(reference)}</b>", style['body']),
        rule(),
        Paragraph('AMOUNT RECEIVED' if paid else 'TRANSACTION AMOUNT', style['label']),
        Paragraph(text(amount), style['amount']),
        Paragraph(f'{text(payment.get_status_display())} / {text(payment.get_method_display() or "Method not recorded")} / Payment date: {text(date_label(payment.payment_date))}', style['small']),
        Spacer(1, 4 * mm),
        Paragraph(f'Dear {text(name(adopter))},', style['body']),
    ]
    if paid:
        statement = (
            f'This acknowledges receipt of <b>{text(amount)}</b> from '
            f'<b>{text(name(adopter))}</b> ({text(adopter.email)}) '
            f'in connection with the adoption application for <b>{text(pet.name)}</b>.'
        )
    else:
        statement = (
            f'This document records a <b>{text(payment.get_status_display().lower())}</b> '
            f'payment entry of <b>{text(amount)}</b> for the adoption application for '
            f'<b>{text(pet.name)}</b>, under {text(name(adopter))} ({text(adopter.email)}). '
            'It does not confirm receipt of funds.'
        )
    story.append(Paragraph(statement, style['body']))
    if payment.processed_by:
        story.append(Paragraph(
            f'The transaction was recorded by <b>{text(name(payment.processed_by))}</b>. '
            'The payment details and reference above match the saved PawConnect transaction.',
            style['body'],
        ))
    if payment.package_id:
        story.extend(section('Assigned package', text(payment.package.name)))
    if payment.notes.strip():
        story.extend(section('Transaction notes', text(payment.notes)))
    story.append(Paragraph('Please retain this document for your adoption records.', style['body']))
    story.append(Signatures(adopter, payment.processed_by, 'Adopter acknowledgment', 'Recorded by staff'))
    story.append(rule())
    references = [
        f'<b>Application reference:</b> {text(application.pk)}',
        f'<b>Payment ID:</b> {text(payment.pk)}',
    ]
    if payment.reference_number:
        references.insert(0, f'<b>Transaction reference:</b> {text(payment.reference_number)}')
    story.append(Paragraph('<br/>'.join(references), style['small']))
    return build_letter(story, title, reference)
