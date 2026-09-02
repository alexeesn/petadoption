from rest_framework import permissions


class IsAdopter(permissions.BasePermission):
    """Allow access only to users with adopter role."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_adopter


class IsStaff(permissions.BasePermission):
    """Allow access only to staff or admin users."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_staff_role or request.user.is_admin_role
        )


class IsAdmin(permissions.BasePermission):
    """Allow access only to admin users."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin_role


class IsOwnerOrStaff(permissions.BasePermission):
    """Object-level permission: owner of the object, or staff/admin."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff_role or request.user.is_admin_role:
            return True
        # Check if the object has a 'user' field pointing to the request user
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "adopter"):
            return obj.adopter.user == request.user
        return False


class IsAdopterOwner(permissions.BasePermission):
    """Object-level permission: the object belongs to the adopter's user account."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff_role or request.user.is_admin_role:
            return True
        if hasattr(obj, "user"):
            return obj.user == request.user
        return False
