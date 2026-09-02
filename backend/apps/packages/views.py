from rest_framework import viewsets, permissions
from .models import AdoptionPackage
from .serializers import PackageSerializer
from apps.accounts.permissions import IsStaff


class PackageViewSet(viewsets.ModelViewSet):
    queryset = AdoptionPackage.objects.all()
    serializer_class = PackageSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsStaff()]