"""Atomic center-custody death reporting and administrator corrections."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.applications.models import Application
from apps.appointments.eligibility import philippine_today
from apps.appointments.models import Appointment
from apps.appointments.services import audit, close_pending_reschedules, notify_adopter
from apps.adoptions.models import AdoptionRecord
from apps.notifications.models import create_notification
from apps.payments.models import Payment
from .models import Pet, PetDeathRecord

DEATH_CANCELLATION_REASON = "The pet passed away while in the center's care. This cancellation is unrelated to your eligibility as an adopter."


def lock_application_pet(application):
    """All pet-changing adoption paths lock pet first, then application."""
    pet_id = Application.objects.values_list("pet_id", flat=True).get(pk=application.pk)
    return Pet.objects.select_for_update(no_key=True).get(pk=pet_id)


@transaction.atomic
def record_pet_death(pet_id, actor, data):
    if not (actor.is_staff_role or actor.is_admin_role):
        raise PermissionDenied("Only staff or administrators may record a pet death.")
    pet = Pet.objects.select_for_update(no_key=True).get(pk=pet_id)
    if pet.status == Pet.Status.DECEASED:
        return pet  # A retry preserves the first report and side effects.
    if pet.status == Pet.Status.ADOPTED or pet.adoption_records.filter(status="completed").exists():
        raise ValidationError({"pet": "This pet is no longer in center custody. A post-adoption death must not change the completed adoption."})
    if data["death_date"] > philippine_today():
        raise ValidationError({"death_date": "Date of death cannot be in the future."})
    custody_start = pet.arrival_date
    latest_return = pet.adoption_records.filter(status="returned", return_date__isnull=False).order_by("-return_date").first()
    if latest_return and (not custody_start or latest_return.return_date > custody_start):
        custody_start = latest_return.return_date
    if custody_start and data["death_date"] < custody_start:
        raise ValidationError({"death_date": "Date of death cannot precede the pet's arrival or latest return to the center."})

    death = PetDeathRecord.objects.create(pet=pet, recorded_by=actor, **data)
    old_status = pet.status
    pet.status = Pet.Status.DECEASED
    pet.save(update_fields=["status", "updated_at"])
    audit(actor, "pet_death_recorded", death, "", f"{death.death_date}: {death.cause}")
    audit(actor, "pet_status_change", pet, old_status, "deceased")
    now = timezone.now()
    # Lock even historical applications: appointment/payment actions serialize
    # on these rows and must finish before their related records are closed.
    applications = list(Application.objects.select_for_update().filter(pet=pet).order_by("pk"))
    affected = []
    for application in applications:
        scheduled = list(AdoptionRecord.objects.select_for_update().filter(application=application, status="scheduled"))
        if application.status not in Application.ACTIVE_STATUSES and not scheduled:
            continue
        previous = application.status
        if previous in Application.ACTIVE_STATUSES:
            application.status = Application.Status.CANCELLED
            application.cancellation_reason = DEATH_CANCELLATION_REASON
            application.cancelled_at = now
            application.death_record = death
            application.save(update_fields=["status", "cancellation_reason", "cancelled_at", "death_record", "updated_at"])
            audit(actor, "status_change", application, previous, "cancelled: pet deceased")
            affected.append(application)
        for record in scheduled:
            record.status = AdoptionRecord.Status.CANCELLED
            record.cancellation_reason = DEATH_CANCELLATION_REASON
            record.cancelled_at = now
            record.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])
            audit(actor, "adoption_cancelled", record, "scheduled", "cancelled: pet deceased")
        for appointment in Appointment.objects.select_for_update().filter(application=application, status__in=Appointment.ACTIVE_STATUSES):
            previous_visit = appointment.status
            appointment.status = Appointment.Status.CANCELLED
            appointment.rejection_reason = DEATH_CANCELLATION_REASON
            appointment.reviewed_by, appointment.reviewed_at = actor, now
            appointment.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"])
            audit(actor, "appointment_cancelled", appointment, previous_visit, "cancelled: pet deceased")
        close_pending_reschedules(application, actor, DEATH_CANCELLATION_REASON)
        for payment in Payment.objects.select_for_update().filter(application=application, status__in=["pending", "completed"]):
            payment.death_review_required = True
            payment.death_review_note = "Pet death recorded. Review this payment and any applicable refund with the adopter. No automatic refund has been issued."
            payment.save(update_fields=["death_review_required", "death_review_note", "updated_at"])
            audit(actor, "payment_death_review_required", payment, "", "Staff payment review required; financial history retained.")
    for application in affected:
        notify_adopter(application, "An update about your adoption application", (
            f"We're sorry to share that {pet.name} has passed away while in the center's care. "
            "Your application and any upcoming visit have been cancelled. "
            "Please contact the center for assistance, including any payment concerns."
        ), notification_type="application", email_template="emails/pet_death_update.html")
    for staff in User.objects.filter(role__in=["staff", "admin"], is_active=True):
        create_notification(staff, "Pet death recorded", f"{pet.name} is marked Deceased. Affected applications and visits were closed. Review any flagged payments.", "pet", f"/pets?scope=history&status=deceased&pet={pet.pk}")
    return pet


@transaction.atomic
def correct_pet_death(pet_id, actor, reason):
    if not actor.is_admin_role:
        raise PermissionDenied("Only administrators may correct a death entry.")
    pet = Pet.objects.select_for_update().get(pk=pet_id)
    death = pet.death_records.select_for_update().filter(corrected_at__isnull=True).first()
    if not death or pet.status != Pet.Status.DECEASED:
        raise ValidationError({"pet": "This pet has no active death entry to correct."})
    death.corrected_at, death.corrected_by, death.correction_reason = timezone.now(), actor, reason
    death.save(update_fields=["corrected_at", "corrected_by", "correction_reason"])
    pet.status = Pet.Status.FOR_ASSESSMENT
    pet.save(update_fields=["status", "updated_at"])
    audit(actor, "pet_death_corrected", death, "active death entry", reason)
    audit(actor, "pet_status_change", pet, "deceased", "for_assessment: death entry corrected")
    for application in death.affected_applications.all():
        notify_adopter(application, "Correction to a pet update", f"The previous death notice for {pet.name} was entered in error and has been corrected by an administrator. Your application remains closed. Please contact the center for assistance.", notification_type="application", email_template="emails/pet_death_correction.html")
    return pet
