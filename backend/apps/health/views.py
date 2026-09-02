from rest_framework import viewsets, permissions
from .models import HealthRecord, Vaccination
from .serializers import HealthRecordSerializer, VaccinationSerializer
from apps.accounts.permissions import IsStaff


class HealthRecordViewSet(viewsets.ModelViewSet):
    queryset = HealthRecord.objects.select_related("pet", "created_by").all()
    serializer_class = HealthRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class VaccinationViewSet(viewsets.ModelViewSet):
    queryset = Vaccination.objects.select_related("pet").all()
    serializer_class = VaccinationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]