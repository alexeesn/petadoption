"""
Phase 6.1 probe: does the FREE adoption path (spec AGENT-SPEC.md 6.1) still work?

Application Submitted -> Staff Review -> Approved -> Adoption Record -> Completed
with NO package and NO payment.

The backend currently gates completion on PROTOTYPE_ADOPTION_FEE, so this
script records the actual observed behaviour instead of asserting it.

Usage: python qa_free_adoption_probe.py
"""
import os
import sys
import uuid
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8099")
User = get_user_model()
PASSWORD = "StrongPass123!"


def next_weekday():
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def main():
    stamp = uuid.uuid4().hex[:8]
    a_email = f"qa_free_a_{stamp}@example.com"
    s_email = f"qa_free_s_{stamp}@example.com"

    # Staff account
    User.objects.filter(email=s_email).delete()
    su = User.objects.create_user(email=s_email, password=PASSWORD, first_name="S", last_name="T", role="staff")
    su.is_email_verified = True
    su.save()
    sa = requests.Session()
    sa.headers["Authorization"] = f"Token {sa.post(f'{BASE}/api/auth/login/', json={'email': s_email, 'password': PASSWORD}).json()['token']}"

    r = sa.post(f"{BASE}/api/pets/", json={"name": "Free Dog", "species": "dog", "age_years": 1, "status": "available"})
    pet_id = r.json()["id"]
    print("pet created:", pet_id, r.json()["status"])

    # Adopter account
    User.objects.filter(email=a_email).delete()
    au = User.objects.create_user(email=a_email, password=PASSWORD, first_name="A", last_name="T", role="adopter")
    au.is_email_verified = True
    au.save()
    aa = requests.Session()
    aa.headers["Authorization"] = f"Token {aa.post(f'{BASE}/api/auth/login/', json={'email': a_email, 'password': PASSWORD}).json()['token']}"

    r = aa.patch(f"{BASE}/api/adopters/profile/", json={
        "phone_number": "+63 900 000 0000", "address_line1": "1 Test St",
        "region": "National Capital Region (NCR)", "city": "City of Manila",
        "barangay": "Barangay 1", "zip_code": "1000",
        "housing_type": "house", "owns_or_rents": "own",
    })
    print("profile:", r.status_code)

    files = [
        ("documents", ("id.pdf", b"%PDF-1.4", "application/pdf")),
        ("documents", ("address.pdf", b"%PDF-1.4", "application/pdf")),
        ("documents", ("brgy.pdf", b"%PDF-1.4", "application/pdf")),
        ("documents", ("cage.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")),
    ]
    data = [("pet", pet_id), ("why_adopt", "free path"), ("privacy_consent", "true"),
            ("require_home_visit", "true"), ("document_types", "identification"),
            ("document_types", "proof_of_address"), ("document_types", "barangay_certification"),
            ("document_types", "cage_photo")]
    r = aa.post(f"{BASE}/api/applications/", data=data, files=files)
    app_id = r.json()["id"]
    print("application:", r.status_code, r.json()["status"])

    r = sa.post(f"{BASE}/api/reviews/", json={"application": app_id, "decision": "approve"})
    print("approve:", r.status_code, r.json().get("status"))

    r = aa.post(f"{BASE}/api/appointments/", json={"application_id": app_id, "requested_date": next_weekday().isoformat()})
    appt = r.json()["id"]
    r = sa.post(f"{BASE}/api/appointments/{appt}/approve/")
    print("appointment confirmed:", r.status_code)

    print("\n--- FREE PATH: complete with NO payment recorded ---")
    r = sa.post(f"{BASE}/api/applications/{app_id}/complete-adoption/", json={"confirmed": True})
    print("complete-adoption status:", r.status_code)
    print("body:", r.text[:400])

    print("\n--- Can a zero-amount payment be recorded to satisfy the gate? ---")
    r = sa.post(f"{BASE}/api/payments/record-onsite/", json={
        "application": app_id, "amount": "0.00", "method": "cash", "payment_received": True})
    print("record-onsite 0.00 status:", r.status_code, r.text[:200])

    print("\n--- Does a package attach to an application at all? ---")
    r = sa.get(f"{BASE}/api/applications/{app_id}/")
    print("application payload keys containing 'package':",
          [k for k in r.json() if "package" in k.lower()])
    print("\nAPP_ID", app_id, "PET_ID", pet_id)


if __name__ == "__main__":
    main()
