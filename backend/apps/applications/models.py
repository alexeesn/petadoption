import uuid
from django.db import models
from django.conf import settings


class Application(models.Model):
    """Adoption application submitted by an adopter."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        PENDING_DOCUMENTS = "pending_documents", "Pending Documents"
        ADDITIONAL_INFO_REQUESTED = "additional_info_requested", "Additional Info Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        ADOPTION_COMPLETED = "adoption_completed", "Adoption Completed"

    # Valid status transitions
    VALID_TRANSITIONS = {
        "draft": ["submitted", "cancelled"],
        "submitted": ["under_review", "cancelled"],
        "under_review": ["pending_documents", "additional_info_requested", "approved", "rejected"],
        "pending_documents": ["under_review", "cancelled"],
        "additional_info_requested": ["under_review", "cancelled"],
        "approved": ["adoption_completed"],
        "rejected": [],
        "cancelled": [],
        "adoption_completed": [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adopter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    pet = models.ForeignKey(
        "pets.Pet", on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    why_adopt = models.TextField(blank=True, help_text="Why do you want to adopt this pet?")
    experience_with_pets = models.TextField(blank=True, help_text="Describe your experience with pets")
    living_situation = models.TextField(blank=True, help_text="Describe your living situation")
    has_other_pets = models.BooleanField(default=False)
    other_pets_description = models.TextField(blank=True)
    references = models.TextField(blank=True, help_text="Personal or veterinary references")
    additional_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True, help_text="Internal staff notes - not visible to adopter")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_applications"
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Application"
        verbose_name_plural = "Applications"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["adopter", "pet"],
                condition=~models.Q(status__in=["cancelled", "rejected", "adoption_completed"]),
                name="unique_active_application_per_adopter_pet",
            )
        ]

    def __str__(self):
        return f"Application {self.id} - {self.adopter.email} -> {self.pet.name}"

    def can_transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    # ------------------------------------------------------------------
    # Persistence: auto-advance draft -> submitted on initial creation.
    #
    # Previously the draft->submitted auto-advance lived only in
    # ApplicationViewSet.perform_create, so applications created through
    # any other path (Django admin, shell, management commands, direct ORM)
    # were left permanently stuck in "draft".  Moving it here makes the
    # model the single source of truth for ALL creation paths.
    #
    # The "draft" status is still retained as a valid choice (and is in
    # VALID_TRANSITIONS) so a future save-as-draft feature can opt into it
    # explicitly.  Only the *default* creation path is auto-advanced.
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        auto_advanced = False
        if self._state.adding and self.status == self.Status.DRAFT:
            self.status = self.Status.SUBMITTED
            auto_advanced = True
        super().save(*args, **kwargs)
        if auto_advanced:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                action="status_change",
                model_name="Application",
                object_id=str(self.id),
                previous_value="draft",
                new_value="submitted",
            )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self._state.adding:
            # New object: the initial status is being set for the first time
            # (not a transition), so any valid status choice is acceptable.
            # The auto-advance to "submitted" happens in save().
            return
        # Existing object: validate the transition from the *persisted* old
        # status to the new status being saved.  We must query the DB for the
        # old value because self.status may have already been overwritten by
        # the form/view before clean() runs.
        try:
            old = self.__class__.objects.get(pk=self.pk)
        except self.__class__.DoesNotExist:
            return
        if old.status != self.status and not old.can_transition_to(self.status):
            raise ValidationError(
                f"Cannot transition from '{old.status}' to '{self.status}'."
            )
