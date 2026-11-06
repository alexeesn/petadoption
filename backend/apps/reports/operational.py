"""Read-only operational reports sharing one filtered source for tables/exports."""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import csv
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, views
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.permissions import IsStaff
from apps.adopters.models import IdentityVerification
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.appointments.models import Appointment, RescheduleRequest
from apps.payments.models import Payment
from apps.pets.models import Pet, PetDeathRecord
from apps.surrenders.models import SurrenderRequest

PHT = ZoneInfo("Asia/Manila")


@dataclass
class Definition:
    title: str
    description: str
    queryset: object
    columns: tuple
    row: object
    dates: dict
    statuses: tuple
    search: tuple
    metrics: tuple = ()
    species: str = ""
    pet: str = ""
    adopter: str = ""
    default_status: str = ""
    extra_filters: dict = field(default_factory=dict)


def col(key, label, kind="text"):
    return {"key": key, "label": label, "kind": kind}


def person(user):
    return user.full_name or user.email if user else ""


def payment_review(payment):
    return "required" if payment.death_review_required else "resolved" if payment.death_review_note else "not_required"


def definitions():
    return {
        "surrenders": Definition(
            "Surrender and Intake", "Current request status and confirmed center intake. Scheduling is not receipt of a pet.",
            SurrenderRequest.objects.select_related("owner", "pet", "received_by"),
            (col("pet_name", "Pet"), col("owner", "Owner"), col("email", "Owner email"), col("status", "Request status", "status"), col("submitted", "Submitted", "datetime"), col("intake_date", "Intake date", "date"), col("received", "Received", "datetime"), col("pet_status", "Current pet status", "status")),
            lambda x: {"pet_name": x.pet_name, "owner": person(x.owner), "email": x.owner.email, "status": x.status, "submitted": x.created_at, "intake_date": x.intake_date, "received": x.received_at, "pet_status": x.pet.status if x.pet else "", "pet_id": x.pet_id},
            {"submitted": ("created_at", "Request submitted date"), "intake": ("intake_date", "Scheduled intake date"), "received": ("received_at", "Actual received date")},
            tuple(SurrenderRequest.Status.choices), ("pet_name", "owner__email", "owner__first_name", "owner__last_name"),
            (("received", "Received", Q(status="received")), ("scheduled", "Intake scheduled", Q(status="intake_scheduled")), ("waitlisted", "Waitlisted", Q(status="waitlisted"))), species="species", pet="pet_id", adopter="owner_id",
        ),
        "pet-deaths": Definition(
            "Pet Deaths and Corrections", "Uncorrected death entries are counted as deaths. Corrected entries remain historical and are counted separately.",
            PetDeathRecord.objects.select_related("pet", "recorded_by", "corrected_by"),
            (col("pet_name", "Pet"), col("death_date", "Death date", "date"), col("cause", "Cause / Unknown"), col("status", "Entry status", "status"), col("recorded_by", "Recorded by"), col("corrected_at", "Corrected", "datetime"), col("correction_reason", "Correction reason")),
            lambda x: {"pet_name": x.pet.name, "death_date": x.death_date, "cause": x.cause, "status": "corrected" if x.corrected_at else "active", "recorded_by": person(x.recorded_by), "corrected_at": x.corrected_at, "correction_reason": x.correction_reason, "pet_id": x.pet_id},
            {"death": ("death_date", "Actual death date"), "recorded": ("recorded_at", "Death entry recorded date"), "corrected": ("corrected_at", "Correction date")},
            (("active", "Uncorrected death entries"), ("corrected", "Corrected entries")), ("pet__name", "cause", "recorded_by__email"),
            (("deaths", "Uncorrected deaths", Q(corrected_at__isnull=True)), ("corrected", "Corrected entries", Q(corrected_at__isnull=False))), species="pet__species", pet="pet_id", default_status="active",
        ),
        "verifications": Definition(
            "Adopter Verification", "Latest saved verification status per adopter. Resubmissions update the same verification record.",
            IdentityVerification.objects.select_related("profile__user", "reviewed_by"),
            (col("adopter", "Adopter"), col("email", "Email"), col("status", "Verification status", "status"), col("submitted", "Latest submission", "datetime"), col("reviewed", "Reviewed", "datetime"), col("reviewer", "Reviewer")),
            lambda x: {"adopter": person(x.profile.user), "email": x.profile.user.email, "status": x.status, "submitted": x.submitted_at, "reviewed": x.reviewed_at, "reviewer": person(x.reviewed_by)},
            {"submitted": ("submitted_at", "Latest submission date"), "reviewed": ("reviewed_at", "Review date"), "created": ("created_at", "Record created date")},
            tuple(IdentityVerification.Status.choices), ("profile__user__email", "profile__user__first_name", "profile__user__last_name"),
            (("pending", "Pending review", Q(status="pending_review")), ("verified", "Verified", Q(status="verified")), ("rejected", "Rejected", Q(status="rejected"))), adopter="profile__user_id",
        ),
        "appointments": Definition(
            "Visit Appointments", "Visit outcomes, including cancellations and no-shows. Historical visits are retained.",
            Appointment.objects.select_related("pet", "adopter"),
            (col("pet_name", "Pet"), col("adopter", "Adopter"), col("email", "Email"), col("status", "Visit status", "status"), col("visit_date", "Visit date", "date"), col("requested", "Requested", "datetime")),
            lambda x: {"pet_name": x.pet.name, "adopter": person(x.adopter), "email": x.adopter.email, "status": x.status, "visit_date": x.requested_date, "requested": x.created_at, "pet_id": x.pet_id},
            {"visit": ("requested_date", "Visit date"), "requested": ("created_at", "Appointment requested date")},
            tuple(Appointment.Status.choices), ("pet__name", "adopter__email", "adopter__first_name", "adopter__last_name"),
            (("confirmed", "Confirmed", Q(status="confirmed")), ("no_show", "No-shows", Q(status="no_show")), ("cancelled", "Cancelled", Q(status="cancelled"))), species="pet__species", pet="pet_id", adopter="adopter_id",
        ),
        "reschedules": Definition(
            "Reschedule Requests", "Requested visit changes and staff decisions; an approved reschedule is not an additional adoption.",
            RescheduleRequest.objects.select_related("application__pet", "application__adopter", "reviewed_by"),
            (col("pet_name", "Pet"), col("email", "Adopter email"), col("original_date", "Original visit", "date"), col("requested_date", "Proposed visit", "date"), col("status", "Decision", "status"), col("requested", "Request submitted", "datetime"), col("reviewer", "Reviewer")),
            lambda x: {"pet_name": x.application.pet.name, "email": x.application.adopter.email, "original_date": x.original_date, "requested_date": x.requested_date, "status": x.status, "requested": x.created_at, "reviewer": person(x.reviewed_by), "pet_id": x.application.pet_id},
            {"requested": ("created_at", "Reschedule request date"), "visit": ("requested_date", "Proposed visit date"), "reviewed": ("reviewed_at", "Decision date")},
            tuple(RescheduleRequest.Status.choices), ("application__pet__name", "application__adopter__email"),
            (("pending", "Pending", Q(status="pending")), ("approved", "Approved", Q(status="approved")), ("rejected", "Rejected", Q(status="rejected"))), species="application__pet__species", pet="application__pet_id", adopter="application__adopter_id",
        ),
        "adoptions": Definition(
            "Adoption Lifecycle", "Scheduled, completed, cancelled and returned records. A returned adoption retains its original completion reference.",
            AdoptionRecord.objects.select_related("pet", "adopter", "application"),
            (col("pet_name", "Pet"), col("email", "Adopter email"), col("status", "Adoption status", "status"), col("scheduled", "Scheduled", "date"), col("completed", "Completed", "date"), col("returned", "Returned", "date"), col("cancelled", "Cancelled", "datetime"), col("reference", "Transaction reference"), col("reason", "Return / cancellation reason")),
            lambda x: {"pet_name": x.pet.name, "email": x.adopter.email, "status": x.status, "scheduled": x.adoption_date, "completed": x.completed_date, "returned": x.return_date, "cancelled": x.cancelled_at, "reference": x.transaction_id or "", "reason": x.return_reason if x.status == "returned" else x.cancellation_reason if x.status == "cancelled" else "", "pet_id": x.pet_id},
            {"scheduled": ("adoption_date", "Scheduled adoption date"), "completed": ("completed_date", "Actual completion date"), "returned": ("return_date", "Actual return date"), "cancelled": ("cancelled_at", "Cancellation date"), "created": ("created_at", "Record created date")},
            tuple(AdoptionRecord.Status.choices), ("pet__name", "adopter__email", "transaction_id"),
            (("completed", "Completed", Q(status="completed")), ("returned", "Returned", Q(status="returned")), ("cancelled", "Cancelled", Q(status="cancelled"))), species="pet__species", pet="pet_id", adopter="adopter_id",
        ),
        "payments": Definition(
            "Payments and Reviews", "Financial status and death-related review flags are separate. Resolving a review does not issue a refund.",
            Payment.objects.select_related("application__pet", "application__adopter"),
            (col("pet_name", "Pet"), col("email", "Adopter email"), col("amount", "Amount (PHP)", "money"), col("status", "Payment status", "status"), col("review_status", "Death-related review", "status"), col("payment_date", "Payment date", "date"), col("receipt", "Receipt")),
            lambda x: {"pet_name": x.application.pet.name, "email": x.application.adopter.email, "amount": x.amount, "status": x.status, "review_status": payment_review(x), "payment_date": x.payment_date, "receipt": x.receipt_number, "pet_id": x.application.pet_id},
            {"payment": ("payment_date", "Actual payment date"), "created": ("created_at", "Payment recorded date"), "updated": ("updated_at", "Last payment update date")},
            tuple(Payment.Status.choices), ("application__pet__name", "application__adopter__email", "receipt_number"),
            (("review_required", "Review required", Q(death_review_required=True)), ("refunded", "Refunded", Q(status="refunded"))), species="application__pet__species", pet="application__pet_id", adopter="application__adopter_id",
            extra_filters={"review_status": (("required", "Review required"), ("resolved", "Review resolved"), ("not_required", "No death-related review"))},
        ),
        "pets": Definition(
            "Pet Inventory", "Current inventory includes adopted, inactive and deceased pets retained in History.",
            Pet.objects.all(),
            (col("pet_name", "Pet"), col("species", "Species", "status"), col("breed", "Breed"), col("status", "Current status", "status"), col("arrival", "Arrived", "date"), col("age", "Recorded age")),
            lambda x: {"pet_name": x.name, "species": x.species, "breed": x.breed, "status": x.status, "arrival": x.arrival_date, "age": x.formatted_age, "pet_id": x.pk},
            {"arrival": ("arrival_date", "Actual arrival date"), "created": ("created_at", "Pet record created date")},
            tuple(Pet.Status.choices), ("name", "breed"),
            (("available", "Available", Q(status="available")), ("adopted", "Adopted", Q(status="adopted")), ("deceased", "Deceased", Q(status="deceased"))), species="species", pet="id",
        ),
        "applications": Definition(
            "Applications", "Current application outcomes, including cancellations following a pet death. These are not adopter rejections.",
            Application.objects.select_related("pet", "adopter", "death_record"),
            (col("pet_name", "Pet"), col("email", "Adopter email"), col("status", "Application status", "status"), col("submitted", "Submitted", "datetime"), col("cancelled", "Cancelled", "datetime"), col("reason", "Cancellation / rejection reason"), col("death_notice", "Death notice", "status")),
            lambda x: {"pet_name": x.pet.name, "email": x.adopter.email, "status": x.status, "submitted": x.created_at, "cancelled": x.cancelled_at, "reason": x.cancellation_reason if x.status == "cancelled" else x.rejection_reason if x.status == "rejected" else "", "death_notice": "corrected" if x.death_record_id and x.death_record.corrected_at else "recorded" if x.death_record_id else "not_applicable", "pet_id": x.pet_id},
            {"submitted": ("created_at", "Application submitted date"), "cancelled": ("cancelled_at", "Cancellation date")},
            tuple(Application.Status.choices), ("pet__name", "adopter__email", "adopter__first_name", "adopter__last_name"),
            (("approved", "Approved", Q(status="approved")), ("rejected", "Rejected", Q(status="rejected")), ("cancelled_death", "Cancelled after death notice", Q(status="cancelled", death_record__isnull=False))), species="pet__species", pet="pet_id", adopter="adopter_id",
        ),
    }


class ReportFilters(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    date_basis = serializers.CharField(required=False)
    status = serializers.CharField(required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)
    species = serializers.ChoiceField(choices=["", *Pet.Species.values], required=False)
    pet = serializers.UUIDField(required=False)
    adopter = serializers.UUIDField(required=False)
    review_status = serializers.ChoiceField(choices=["", "required", "resolved", "not_required"], required=False)
    export = serializers.ChoiceField(choices=["csv", "pdf"], required=False)

    def validate(self, data):
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise serializers.ValidationError({"date_to": "End date must be on or after start date."})
        return data


def metadata(key, definition):
    return {"key": key, "title": definition.title, "description": definition.description, "columns": definition.columns,
            "date_bases": [{"value": k, "label": v[1]} for k, v in definition.dates.items()],
            "statuses": [{"value": k, "label": v} for k, v in definition.statuses], "default_status": definition.default_status,
            "supports_species": bool(definition.species),
            "extra_filters": {k: [{"value": value, "label": label} for value, label in choices] for k, choices in definition.extra_filters.items()}}


def filtered(definition, data):
    qs = definition.queryset
    basis = data.get("date_basis", next(iter(definition.dates)))
    if basis not in definition.dates:
        raise serializers.ValidationError({"date_basis": "Choose a supported date basis."})
    lookup, label = definition.dates[basis]
    field = qs.model._meta.get_field(lookup)
    for key, operator in (("date_from", "gte"), ("date_to", "lte")):
        if key in data:
            # DateTimeField ranges use Philippine calendar dates, not UTC dates.
            if field.get_internal_type() == "DateTimeField":
                from django.db.models.functions import TruncDate
                qs = qs.annotate(report_date=TruncDate(lookup, tzinfo=PHT)).filter(**{f"report_date__{operator}": data[key]})
            else:
                qs = qs.filter(**{f"{lookup}__{operator}": data[key]})
    status = data.get("status", definition.default_status)
    if status and status not in dict(definition.statuses):
        raise serializers.ValidationError({"status": "Choose a supported report status."})
    if status:
        qs = qs.filter(corrected_at__isnull=(status == "active")) if qs.model is PetDeathRecord else qs.filter(status=status)
    for key, target in (("species", definition.species), ("pet", definition.pet), ("adopter", definition.adopter)):
        if data.get(key):
            if not target:
                raise serializers.ValidationError({key: "This filter is not available for this report."})
            qs = qs.filter(**{target: data[key]})
    if data.get("search"):
        search = Q()
        for target in definition.search:
            search |= Q(**{f"{target}__icontains": data["search"]})
        qs = qs.filter(search)
    if data.get("review_status"):
        if qs.model is not Payment:
            raise serializers.ValidationError({"review_status": "Only payment reports support this filter."})
        qs = qs.filter({"required": Q(death_review_required=True), "resolved": Q(death_review_required=False) & ~Q(death_review_note=""), "not_required": Q(death_review_required=False, death_review_note="")}[data["review_status"]])
    return qs.order_by(f"-{lookup}", "-pk"), label


def value_json(value):
    if isinstance(value, datetime):
        return timezone.localtime(value, PHT).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else None


def row_json(definition, obj):
    return {"id": str(obj.pk), **{key: value_json(value) for key, value in definition.row(obj).items()}}


def summary(definition, qs):
    counts = qs.order_by().aggregate(total=Count("pk"), **{key: Count("pk", filter=condition) for key, _, condition in definition.metrics})
    result = [{"key": "total", "label": "Matching records", "value": counts["total"], "kind": "number"}]
    result += [{"key": key, "label": label, "value": counts[key], "kind": "number"} for key, label, _ in definition.metrics]
    if qs.model is Payment:
        amount = qs.filter(status="completed").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        result.append({"key": "completed_amount", "label": "Completed amount (PHP)", "value": f"{amount:.2f}", "kind": "money"})
    return result


def csv_cell(value):
    # Quoting alone does not stop spreadsheet applications executing formulas.
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


class OperationalReportsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request, report_type=None):
        reports = definitions()
        if report_type is None:
            return Response({"reports": [metadata(key, definition) for key, definition in reports.items()]})
        definition = reports.get(report_type)
        if definition is None:
            raise Http404("Report not found.")
        serializer = ReportFilters(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        qs, date_basis = filtered(definition, data)
        stats = summary(definition, qs)
        if data.get("export"):
            labels = [f"Date basis: {date_basis}", f"Date range: {data.get('date_from', 'Any')} to {data.get('date_to', 'Any')}"]
            labels += [f"{key.replace('_', ' ').title()}: {value}" for key, value in data.items() if key not in ("date_from", "date_to", "date_basis", "status", "export") and value]
            selected_status = data.get("status", definition.default_status)
            labels.append(f"Status: {dict(definition.statuses).get(selected_status, 'All statuses')}")
            if data["export"] == "pdf":
                from .operational_pdf import build_operational_pdf
                payload = build_operational_pdf(definition, (row_json(definition, obj) for obj in qs.iterator()), stats, labels, request.user)
                response = HttpResponse(payload, content_type="application/pdf")
            else:
                response = HttpResponse(content_type="text/csv; charset=utf-8")
                response.write('\ufeff')
                writer = csv.writer(response)
                writer.writerow([column["label"] for column in definition.columns])
                for obj in qs.iterator():
                    row = row_json(definition, obj)
                    writer.writerow([csv_cell(row.get(column["key"])) for column in definition.columns])
            response["Content-Disposition"] = f'attachment; filename="pawconnect-{report_type}-report.{data["export"]}"'
            response["Cache-Control"] = "private, no-store"
            return response
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        response = paginator.get_paginated_response([row_json(definition, obj) for obj in page])
        response.data.update({"report": metadata(report_type, definition), "date_basis": date_basis, "stats": stats})
        response["Cache-Control"] = "private, no-store"
        return response
