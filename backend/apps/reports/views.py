import csv
from django.http import HttpResponse
from rest_framework import views, permissions
from rest_framework.response import Response
from django.utils import timezone

from apps.accounts.permissions import IsStaff


class AdoptionReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.adoptions.models import AdoptionRecord
        from apps.adoptions.serializers import AdoptionRecordSerializer

        qs = AdoptionRecord.objects.select_related("pet", "adopter", "staff_member")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        stats = {
            "total": qs.count(),
            "completed": qs.filter(status="completed").count(),
            "scheduled": qs.filter(status="scheduled").count(),
            "cancelled": qs.filter(status="cancelled").count(),
            "returned": qs.filter(status="returned").count(),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="adoption_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Pet", "Adopter", "Status", "Date", "Staff"])
            for a in qs:
                writer.writerow([a.pet.name, a.adopter.email, a.status, a.adoption_date,
                                 a.staff_member.email if a.staff_member else ""])
            return response

        serializer = AdoptionRecordSerializer(qs[:100], many=True, context={"request": request})
        return Response({"stats": stats, "results": serializer.data})


class PetInventoryReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.pets.models import Pet
        from django.db.models import Count

        qs = Pet.objects.all()
        species = request.query_params.get("species")
        if species:
            qs = qs.filter(species=species)

        stats = {
            "total": qs.count(),
            "by_status": dict(qs.values_list("status").annotate(count=Count("id")).values_list("status", "count")),
            "by_species": dict(qs.values_list("species").annotate(count=Count("id")).values_list("species", "count")),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="pet_inventory_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Name", "Species", "Breed", "Status", "Age (months)", "Fee"])
            for p in qs:
                writer.writerow([p.name, p.species, p.breed, p.status, p.age_months, p.adoption_fee])
            return response

        return Response({"stats": stats, "total": qs.count()})

class ApplicationReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.applications.models import Application
        from django.db.models import Count

        qs = Application.objects.all()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        stats = {
            "total": qs.count(),
            "by_status": dict(qs.values_list("status").annotate(count=Count("id")).values_list("status", "count")),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="application_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["ID", "Adopter", "Pet", "Status", "Created"])
            for a in qs[:200]:
                writer.writerow([str(a.id), a.adopter.email, a.pet.name, a.status, a.created_at])
            return response

        return Response({"stats": stats, "total": qs.count()})


class PaymentReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.payments.models import Payment
        from django.db.models import Sum

        qs = Payment.objects.all()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        stats = {
            "total": qs.count(),
            "completed": qs.filter(status="completed").count(),
            "total_revenue": str(qs.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="payment_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["ID", "Application", "Amount", "Method", "Status", "Receipt", "Date"])
            for p in qs[:200]:
                writer.writerow([str(p.id), str(p.application_id), p.amount, p.method, p.status,
                                 p.receipt_number, p.created_at])
            return response

        return Response({"stats": stats})


class AdopterReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.accounts.models import User

        adopters = User.objects.filter(role="adopter")
        stats = {
            "total_adopters": adopters.count(),
            "verified": adopters.filter(is_email_verified=True).count(),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="adopter_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Email", "Name", "Verified", "Joined"])
            for u in adopters:
                writer.writerow([u.email, u.full_name, u.is_email_verified, u.date_joined])
            return response

        return Response({"stats": stats})


class HealthReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request):
        from apps.health.models import HealthRecord, Vaccination

        stats = {
            "total_health_records": HealthRecord.objects.count(),
            "total_vaccinations": Vaccination.objects.count(),
            "overdue_vaccinations": Vaccination.objects.filter(
                next_due_date__lt=timezone.now().date()
            ).count(),
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="health_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Pet", "Vaccine Name", "Administered Date", "Next Due Date", "Status"])
            for v in Vaccination.objects.select_related("pet").all()[:200]:
                is_overdue = v.next_due_date and v.next_due_date < timezone.now().date()
                status_str = "Overdue" if is_overdue else "Up to Date"
                writer.writerow([v.pet.name, v.vaccine_name, v.administered_date, v.next_due_date, status_str])
            return response

        return Response({"stats": stats})