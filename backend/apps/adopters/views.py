from rest_framework import generics, permissions
from rest_framework.response import Response
from .models import AdopterProfile
from .serializers import AdopterProfileSerializer, AdopterProfileUpdateSerializer
from apps.accounts.permissions import IsAdopter, IsStaff


class AdopterProfileView(generics.RetrieveUpdateAPIView):
    """Adopter can view/edit own profile. Staff can view all."""
    serializer_class = AdopterProfileSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdopter()]

    def get_object(self):
        profile, _ = AdopterProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return AdopterProfileSerializer
        return AdopterProfileUpdateSerializer

    def update(self, request, *args, **kwargs):
        """
        Persist changes using the write serializer, then return the full read
        serializer so the response always includes computed fields such as
        profile_is_complete, user_email, user_name, and timestamps.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = AdopterProfileUpdateSerializer(
            instance, data=request.data, partial=partial
        )
        write_serializer.is_valid(raise_exception=True)
        self.perform_update(write_serializer)
        read_serializer = AdopterProfileSerializer(instance, context={"request": request})
        return Response(read_serializer.data)


class AdopterListView(generics.ListAPIView):
    """Staff/Admin: list all adopters."""
    serializer_class = AdopterProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_queryset(self):
        return AdopterProfile.objects.select_related("user").order_by("user__email").all()


class AdopterDetailView(generics.RetrieveAPIView):
    """Staff/Admin: view a specific adopter."""
    serializer_class = AdopterProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    queryset = AdopterProfile.objects.select_related("user").order_by("user__email").all()

