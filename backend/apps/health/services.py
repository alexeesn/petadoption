"""
Adopter-facing pet health summary.

The complete health record (veterinarian, clinic, diagnosis, treatment, internal
notes and the dated medical history) is staff/admin-only and stays behind the
``/api/health-records/`` endpoints.  The Pet Details page in the adopter portal
only needs a short, non-sensitive summary of that same data, so the summary is
derived here from the existing HealthRecord and Vaccination models instead of
exposing the staff serializers.

Deliberately NOT part of the summary:

* ``HealthRecord.notes`` and ``HealthRecord.treatment`` - internal care notes.
* veterinarian / clinic details - operational information, not adopter-facing.

Nothing about the staff health-record API changes: this is read-only data added
to the pet detail payload.
"""
from .models import HealthRecord, Vaccination

# Most urgent first: a pet with any overdue vaccination is "overdue" overall.
VACCINATION_STATUS_PRIORITY = ("overdue", "due_soon", "up_to_date")


def build_adopter_health_summary(pet) -> dict:
    """Return the adopter-safe health summary embedded in the pet detail API.

    Always returns the same shape so the frontend never has to guess whether a
    key is present; a pet without a health record simply gets empty values.
    """
    latest_record = (
        HealthRecord.objects.filter(pet=pet)
        .order_by("-record_date", "-created_at")
        .first()
    )
    vaccination_statuses = {
        vaccination.vaccination_status
        for vaccination in Vaccination.objects.filter(pet=pet)
    }
    vaccination_status = next(
        (
            status
            for status in VACCINATION_STATUS_PRIORITY
            if status in vaccination_statuses
        ),
        None,
    )

    return {
        "has_health_record": latest_record is not None,
        "vaccination_status": vaccination_status,
        "health_status": (latest_record.diagnosis or "").strip() if latest_record else "",
        "last_checkup_date": latest_record.record_date.isoformat() if latest_record else None,
        "next_checkup_date": (
            latest_record.next_checkup_date.isoformat()
            if latest_record and latest_record.next_checkup_date
            else None
        ),
    }
