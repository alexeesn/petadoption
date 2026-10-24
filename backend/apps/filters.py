from rest_framework import filters, serializers


class RecordScopeFilter(filters.BaseFilterBackend):
    """Filter a permission-scoped queryset before counting and pagination."""

    def filter_queryset(self, request, queryset, view):
        scope = request.query_params.get("scope", "all")
        if scope not in ("active", "history", "all"):
            raise serializers.ValidationError({"scope": ["Choose active, history, or all."]})
        if scope == "active":
            return queryset.filter(status__in=view.active_statuses)
        if scope == "history":
            return queryset.exclude(status__in=view.active_statuses)
        return queryset
