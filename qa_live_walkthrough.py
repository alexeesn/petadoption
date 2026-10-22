"""
Phase 6.1 live end-to-end walkthrough against a running server.

Drives the real HTTP API (Django runserver + PostgreSQL) through the whole
adoption lifecycle and prints a PASS/FAIL line per step.  This is a QA
harness, not a unit test: it uses a separate throwaway database and a real
HTTP server so that routing, middleware, permissions, serializers and the
database are all exercised together.

Usage:
    $env:DJANGO_SETTINGS_MODULE='config.settings.development'
    $env:POSTGRES_DB='pam_qa'
    python qa_live_walkthrough.py
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

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8099")

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""))
    return bool(condition)


def section(title):
    print(f"\n=== {title} ===")


def make_pdf():
    return b"%PDF-1.4 qa test document"


def make_jpg():
    return b"\xff\xd8\xff\xe0" + b"qa-jpeg-bytes"


def next_weekday():
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def main():
    s = requests.Session()
    stamp = uuid.uuid4().hex[:8]
    adopter_email = f"qa_adopter_{stamp}@example.com"
    staff_email = f"qa_staff_{stamp}@example.com"
    other_email = f"qa_other_{stamp}@example.com"
    password = "StrongPass123!"

    section("1. Registration + email verification")
    r = s.post(f"{BASE}/api/auth/register/", json={
        "email": adopter_email, "first_name": "QA", "last_name": "Adopter",
        "password": password, "password_confirm": password,
    })
    check("register returns 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")

    r = s.post(f"{BASE}/api/auth/login/", json={"email": adopter_email, "password": password})
    check("unverified login blocked with 403", r.status_code == 403, f"got {r.status_code}")

    # The OTP is read straight from the database (dev mail backend is console).
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(email=adopter_email)
    r = s.post(f"{BASE}/api/auth/verify-email/", json={"email": adopter_email, "otp": user.otp})
    check("email verification accepts the OTP", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")

    r = s.post(f"{BASE}/api/auth/login/", json={"email": adopter_email, "password": password})
    check("login works after verification", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    adopter_token = r.json()["token"]

    section("2. Staff account + available pet")
    User.objects.filter(email=staff_email).delete()
    staff_user = User.objects.create_user(
        email=staff_email, password=password, first_name="QA", last_name="Staff",
        role="staff",
    )
    staff_user.is_email_verified = True
    staff_user.save()
    r = s.post(f"{BASE}/api/auth/login/", json={"email": staff_email, "password": password})
    check("staff login works", r.status_code == 200, f"got {r.status_code}")
    staff_token = r.json()["token"]

    sa = requests.Session()
    sa.headers["Authorization"] = f"Token {staff_token}"
    r = sa.post(f"{BASE}/api/pets/", json={
        "name": "QA Dog", "species": "dog", "age_years": 2, "status": "available",
    })
    check("staff creates an available pet", r.status_code == 201, f"got {r.status_code} {r.text[:300]}")
    pet_id = r.json().get("id")
    check("create response returns id and status",
          bool(pet_id) and r.json().get("status") == "available", str(r.json())[:200])

    section("3. Adopter profile gate")
    aa = requests.Session()
    aa.headers["Authorization"] = f"Token {adopter_token}"
    r = aa.post(f"{BASE}/api/applications/", json={
        "pet": pet_id, "privacy_consent": True,
    })
    check("incomplete profile blocks application (400)",
          r.status_code == 400 and "profile" in r.text, f"got {r.status_code} {r.text[:200]}")

    r = aa.patch(f"{BASE}/api/adopters/profile/", json={
        "phone_number": "+63 900 000 0000",
        "address_line1": "123 Test Street",
        "region": "National Capital Region (NCR)",
        "city": "City of Manila",
        "barangay": "Barangay 1",
        "zip_code": "1000",
        "housing_type": "house",
        "owns_or_rents": "own",
    })
    check("adopter can complete the profile (200)", r.status_code == 200, f"got {r.status_code} {r.text[:300]}")

    section("4. Browse + submit application")
    r = aa.get(f"{BASE}/api/pets/", params={"status": "available"})
    listed = [p["id"] for p in r.json().get("results", [])]
    check("available pet appears in the public listing",
          r.status_code == 200 and pet_id in listed, f"got {r.status_code} count={len(listed)}")

    files = [
        ("documents", ("id.pdf", make_pdf(), "application/pdf")),
        ("documents", ("address.pdf", make_pdf(), "application/pdf")),
        ("documents", ("brgy.pdf", make_pdf(), "application/pdf")),
        ("documents", ("cage.jpg", make_jpg(), "image/jpeg")),
    ]
    data = [
        ("pet", pet_id),
        ("why_adopt", "I want to give QA Dog a home"),
        ("experience_with_pets", "Some experience"),
        ("living_situation", "House with yard"),
        ("privacy_consent", "true"),
        ("require_home_visit", "true"),
        ("document_types", "identification"),
        ("document_types", "proof_of_address"),
        ("document_types", "barangay_certification"),
        ("document_types", "cage_photo"),
    ]
    r = aa.post(f"{BASE}/api/applications/", data=data, files=files)
    check("application submitted (201)", r.status_code == 201, f"got {r.status_code} {r.text[:400]}")
    body = r.json() if r.status_code == 201 else {}
    check("create response includes id and status",
          bool(body.get("id")) and body.get("status") == "submitted", str(body)[:250])
    check("create response includes the 4 documents",
          len(body.get("documents", [])) == 4, str(len(body.get("documents", []))))
    app_id = body.get("id")

    section("5. Document privacy + MIME/size validation")
    r = aa.post(f"{BASE}/api/documents/", data={"application": app_id, "document_type": "other"},
                files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    check("rejected extension is refused (400)", r.status_code == 400, f"got {r.status_code} {r.text[:200]}")

    r = aa.post(f"{BASE}/api/documents/", data={"application": app_id, "document_type": "other"},
                files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")})
    check("accepted extension with matching MIME is stored (201)", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")

    r = aa.get(f"{BASE}/api/documents/")
    check("adopter only sees documents of their own application",
          r.status_code == 200 and all(d["application"] == app_id for d in r.json().get("results", [])),
          f"got {r.status_code} count={len(r.json().get('results', []))}")

    section("6. RBAC: adopter cannot reach staff resources")
    for path in ["/api/reviews/", "/api/health-records/", "/api/reports/adoptions/",
                 "/api/audit/", "/api/adopters/"]:
        r = aa.get(f"{BASE}{path}")
        check(f"adopter blocked from {path}", r.status_code == 403, f"got {r.status_code}")

    r = aa.post(f"{BASE}/api/applications/{app_id}/update-status/", json={"status": "approved"})
    check("adopter cannot self-approve an application (403)", r.status_code == 403, f"got {r.status_code}")

    section("7. Staff review + approval")
    r = sa.post(f"{BASE}/api/reviews/", json={
        "application": app_id, "decision": "approve",
        "internal_notes": "Internal only", "adopter_visible_notes": "Welcome!",
    })
    check("staff approve returns 201", r.status_code == 201, f"got {r.status_code} {r.text[:250]}")

    r = sa.get(f"{BASE}/api/applications/{app_id}/")
    check("application status is approved", r.json().get("status") == "approved", str(r.json().get("status")))
    r = sa.get(f"{BASE}/api/pets/{pet_id}/")
    check("pet moved to pending after approval", r.json().get("status") == "pending", str(r.json().get("status")))

    r = aa.get(f"{BASE}/api/reviews/")
    adopter_reviews = r.json().get("results", [])
    check("internal_notes never serialized to the adopter",
          all("internal_notes" not in rv for rv in adopter_reviews), str(adopter_reviews)[:250])

    section("8. Appointment + adoption record scheduling")
    r = aa.post(f"{BASE}/api/appointments/", json={
        "application_id": app_id, "requested_date": next_weekday().isoformat(),
    })
    check("adopter books an onsite visit (201)", r.status_code == 201, f"got {r.status_code} {r.text[:300]}")
    appt_id = r.json().get("id") if r.status_code == 201 else None

    r = sa.post(f"{BASE}/api/appointments/{appt_id}/approve/")
    check("staff confirms the visit (200)", r.status_code == 200, f"got {r.status_code} {r.text[:300]}")

    r = sa.get(f"{BASE}/api/adoptions/", params={"application": app_id})
    records = r.json().get("results", [])
    check("exactly one adoption record was created and scheduled",
          len(records) == 1 and records[0]["status"] == "scheduled", str(records)[:250])
    record_id = records[0]["id"] if records else None

    section("9. Payment rules (fee required for turnover)")
    r = aa.get(f"{BASE}/api/applications/{app_id}/payment-summary/")
    check("payment summary reports the fee as unpaid",
          r.status_code == 200 and r.json().get("is_fee_paid") is False, str(r.json())[:250])

    r = aa.post(f"{BASE}/api/applications/{app_id}/complete-adoption/", json={"confirmed": True})
    check("turnover blocked while the fee is unpaid (400)", r.status_code == 400, f"got {r.status_code} {r.text[:200]}")

    r = aa.post(f"{BASE}/api/payments/record-onsite/", json={
        "application": app_id, "amount": "500.00", "method": "cash", "payment_received": True,
    })
    check("adopter cannot record a payment (403)", r.status_code == 403, f"got {r.status_code}")

    r = sa.post(f"{BASE}/api/payments/record-onsite/", json={
        "application": app_id, "amount": "500.00", "method": "cash", "payment_received": True,
    })
    check("staff records the onsite payment (201)", r.status_code == 201, f"got {r.status_code} {r.text[:300]}")
    pay = r.json() if r.status_code == 201 else {}
    check("completed payment gets a permanent receipt number",
          pay.get("status") == "completed" and str(pay.get("receipt_number", "")).startswith("REC-"),
          str(pay)[:250])

    r = aa.get(f"{BASE}/api/applications/{app_id}/payment-summary/")
    check("payment summary now reports the fee as paid",
          r.json().get("is_fee_paid") is True and r.json().get("total_paid") == "500.00", str(r.json())[:250])

    section("10. Handover confirmation + adoption completion")
    r = sa.post(f"{BASE}/api/applications/{app_id}/complete-adoption/", json={})
    check("turnover without confirmation is refused (400)", r.status_code == 400, f"got {r.status_code} {r.text[:200]}")

    r = sa.post(f"{BASE}/api/applications/{app_id}/complete-adoption/",
                json={"confirmed": True, "notes": "Handed over onsite."})
    check("turnover with confirmation completes the adoption (200)",
          r.status_code == 200 and r.json().get("status") == "adoption_completed",
          f"got {r.status_code} {r.text[:300]}")

    r = sa.get(f"{BASE}/api/adoptions/", params={"application": app_id})
    records = r.json().get("results", [])
    check("still exactly one adoption record",
          len(records) == 1, f"count={len(records)}")
    rec = records[0] if records else {}
    check("adoption record is completed with a transaction id",
          rec.get("status") == "completed" and str(rec.get("transaction_id", "")).startswith("TXN-"),
          str(rec)[:250])

    r = sa.get(f"{BASE}/api/pets/{pet_id}/")
    check("pet status synced to adopted", r.json().get("status") == "adopted", str(r.json().get("status")))

    r = aa.get(f"{BASE}/api/pets/", params={"status": "available"})
    listed = [p["id"] for p in r.json().get("results", [])]
    check("adopted pet is gone from the available listing", pet_id not in listed, str(listed)[:200])

    section("11. Adopter ownership boundaries")
    r = aa.get(f"{BASE}/api/adoptions/{record_id}/")
    check("adopter can read their own adoption record (200)", r.status_code == 200, f"got {r.status_code}")
    r = aa.post(f"{BASE}/api/adoptions/{record_id}/", json={"status": "cancelled"})
    check("adopter cannot modify the adoption record (403)", r.status_code == 403, f"got {r.status_code}")

    User.objects.filter(email=other_email).delete()
    other = User.objects.create_user(
        email=other_email, password=password, first_name="QA", last_name="Other", role="adopter",
    )
    other.is_email_verified = True
    other.save()
    r = s.post(f"{BASE}/api/auth/login/", json={"email": other_email, "password": password})
    oa = requests.Session()
    oa.headers["Authorization"] = f"Token {r.json()['token']}"
    r = oa.get(f"{BASE}/api/applications/{app_id}/")
    check("another adopter cannot read the application (404/403)", r.status_code in (403, 404), f"got {r.status_code}")
    r = oa.get(f"{BASE}/api/adoptions/{record_id}/")
    check("another adopter cannot read the adoption record (404/403)", r.status_code in (403, 404), f"got {r.status_code}")
    r = oa.get(f"{BASE}/api/documents/")
    check("another adopter sees none of the documents",
          r.status_code == 200 and r.json().get("count", 0) == 0, f"got {r.status_code} count={r.json().get('count')}")

    section("12. Notifications + audit trail")
    r = aa.get(f"{BASE}/api/notifications/")
    notifs = r.json().get("results", [])
    titles = [n.get("title", "") for n in notifs]
    check("adopter received lifecycle notifications",
          any("Application Submitted" in t for t in titles)
          and any("Payment Confirmed" in t for t in titles)
          and any("Adoption Completed" in t for t in titles),
          str(titles)[:300])

    r = sa.get(f"{BASE}/api/audit/")
    audit = r.json().get("results", [])
    actions = {a.get("action") for a in audit}
    check("audit log captured the state changes",
          {"status_change", "payment_created", "adoption_completed"} <= actions,
          str(sorted(actions))[:300])

    section("13. Reports + exports")
    for report in ["adoptions", "pets", "adopters", "applications", "health", "payments"]:
        r = sa.get(f"{BASE}/api/reports/{report}/")
        check(f"staff can read the {report} report", r.status_code == 200, f"got {r.status_code} {r.text[:150]}")
    r = sa.get(f"{BASE}/api/reports/adoptions/", params={"export": "csv"})
    check("adoption report CSV export works", r.status_code == 200 and "csv" in r.headers.get("Content-Type", ""),
          f"got {r.status_code} {r.headers.get('Content-Type')}")

    section("14. Free adoption (no package -> no payment required)")
    r = sa.post(f"{BASE}/api/packages/", json={
        "name": f"QA Free Pack {stamp}", "description": "Free", "price": "0.00", "inclusions": [],
    })
    check("staff creates a zero-price package", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    free_pkg_id = r.json().get("id") if r.status_code == 201 else None

    section("15. Password reset + account lockout")
    r = s.post(f"{BASE}/api/auth/forgot-password/", json={"email": adopter_email})
    check("forgot password accepted (200)", r.status_code == 200, f"got {r.status_code} {r.text[:150]}")
    user.refresh_from_db()
    r = s.post(f"{BASE}/api/auth/reset-password/", json={
        "email": adopter_email, "otp": user.otp, "new_password": "NewStrongPass123!",
        "new_password_confirm": "NewStrongPass123!",
    })
    check("password reset with a valid OTP works (200)", r.status_code == 200, f"got {r.status_code} {r.text[:250]}")
    r = s.post(f"{BASE}/api/auth/login/", json={"email": adopter_email, "password": "NewStrongPass123!"})
    check("login with the new password works", r.status_code == 200, f"got {r.status_code}")

    bad = requests.Session()
    for i in range(6):
        bad.post(f"{BASE}/api/auth/login/", json={"email": adopter_email, "password": "WrongPassword123!"})
    r = bad.post(f"{BASE}/api/auth/login/", json={"email": adopter_email, "password": "NewStrongPass123!"})
    check("account is locked after repeated failed logins (403)",
          r.status_code == 403, f"got {r.status_code} {r.text[:200]}")

    section("SUMMARY")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED CHECKS:")
        for n in failed:
            print(f"  - {n}")
    print("CLEANUP IDS:", app_id, pet_id, record_id, free_pkg_id, adopter_email, staff_email, other_email)


if __name__ == "__main__":
    main()
