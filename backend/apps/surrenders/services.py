import json
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.notifications.models import create_notification
from apps.pets.models import Pet
from .models import SurrenderEvent, SurrenderRequest
from .emails import send_surrender_update_email


def today():
    return timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()


def record_event(request, actor, action, previous="", note="", internal_notes=""):
    SurrenderEvent.objects.create(request=request, actor=actor, action=action, previous_status=previous,
                                  new_status=request.status, note=note, internal_notes=internal_notes,
                                  intake_date=request.intake_date)
    AuditLog.objects.create(user=actor, action=f"surrender_{action}", model_name="SurrenderRequest", object_id=str(request.pk),
                            previous_value=previous, new_value=json.dumps({"status": request.status, "intake_date": str(request.intake_date or ""), "pet": str(request.pet_id or "")}))


def notify_owner(request, title, message, *, email_message=None):
    create_notification(request.owner, title, message, "surrender", f"/surrenders/{request.pk}")
    email = request.owner.email
    url = f"{settings.ADOPTER_PORTAL_URL}/surrenders/{request.pk}"
    body = f"{message}\n\nTrack your request: {url}"
    # Capture the event's public details now, before any later transition can
    # mutate this model. Private review notes/photos are never email context.
    context = {
        "title": title, "owner_name": request.owner.full_name or request.owner.email,
        "pet_name": request.pet_name, "request_id": str(request.pk), "request_url": url,
        "status": request.status, "status_label": request.get_status_display(),
        "message": message if email_message is None else email_message,
        "intake_date": request.intake_date, "intake_instructions": request.intake_instructions,
    }
    transaction.on_commit(lambda: send_surrender_update_email(email, title, body, context))


def notify_staff(request, title):
    for staff in User.objects.filter(role__in=["staff", "admin"], is_active=True):
        create_notification(staff, title, f"Surrender request for {request.pet_name} needs attention.", "surrender", f"/surrenders/{request.pk}")


def review(request, actor, data):
    transitions = {
        "submitted": {"needs_information", "waitlisted", "intake_scheduled", "declined"},
        "needs_information": {"waitlisted", "intake_scheduled", "declined"},
        "waitlisted": {"needs_information", "intake_scheduled", "declined"},
        "intake_scheduled": {"needs_information", "waitlisted", "intake_scheduled", "declined"},
    }
    target = data["status"]
    if target not in transitions.get(request.status, set()):
        raise ValidationError({"status": "This request cannot move to that status."})
    if target == "intake_scheduled":
        date = data.get("intake_date")
        instructions = data.get("intake_instructions", "").strip()
        if not date or date < today():
            raise ValidationError({"intake_date": "Choose today or a future date."})
        if not instructions:
            raise ValidationError({"intake_instructions": "Provide the center location and intake requirements."})
        if request.status == target and date == request.intake_date and instructions == request.intake_instructions:
            raise ValidationError({"intake_date": "Change the date or instructions to reschedule this intake."})
        request.intake_date, request.intake_instructions = date, instructions
    else:
        request.intake_date, request.intake_instructions = None, ""
    previous = request.status
    request.status = target
    request.save()
    record_event(request, actor, "reviewed", previous, data["note"], data["internal_notes"])
    message = f"Your surrender request for {request.pet_name}: {request.get_status_display()}. {data['note']}"
    if request.intake_date:
        message += f" Intake date: {request.intake_date}. {request.intake_instructions} Scheduling is not final acceptance; keep the pet in your care until handover."
    notify_owner(request, "Surrender request updated", message, email_message=data["note"])


def confirm_intake(request, actor, data):
    if request.status != SurrenderRequest.Status.INTAKE_SCHEDULED:
        raise ValidationError({"status": "Only a scheduled intake can be confirmed as received."})
    if request.intake_date > today():
        raise ValidationError({"intake_date": "The intake date has not arrived. Reschedule first if needed."})
    if data["confirmed"] is not True:
        raise ValidationError({"confirmed": "Confirm physical receipt of the pet and the owner's handover consent."})
    pet = Pet.objects.create(name=request.pet_name, species=request.species, breed=request.breed,
                             gender=request.gender, age_years=request.age_years, age_months=request.age_months,
                             arrival_date=today(), status=data["pet_status"])
    previous = request.status
    request.status = SurrenderRequest.Status.RECEIVED
    request.pet = pet
    request.received_at = timezone.now()
    request.received_by = actor
    request.save()
    record_event(request, actor, "received", previous, "The center received the pet and confirmed the handover.")
    AuditLog.objects.create(user=actor, action="pet_intake", model_name="Pet", object_id=str(pet.pk), new_value=pet.status)
    notify_owner(request, "Pet received by the center", f"The center has received {request.pet_name}. Your surrender request is complete.")
