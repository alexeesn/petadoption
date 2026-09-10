"""
Management command to transition stuck "draft" applications to "submitted".

Before the draft → submitted auto-advance was moved into Application.save()
(see models.py), applications created through non-API paths (Django shell,
direct ORM, etc.) were left permanently stuck in "draft" status with no way
for staff to advance them from the staff-portal UI.

This one-off command finds all such stuck drafts and transitions them to
"submitted", creating an AuditLog entry for each transition — matching the
pattern already used in ApplicationViewSet.perform_create.

Usage:
    python manage.py fix_draft_applications [--dry-run] [--user-id <uuid>]

The --user-id option attributes the audit-log entries and change to a
specific user (e.g. an administrator) instead of leaving the audit log user
null.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.applications.models import Application
from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Transition stuck 'draft' applications to 'submitted' with audit logging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without making changes.",
        )
        parser.add_argument(
            "--user-id",
            default=None,
            help="UUID of the user to attribute the audit-log entries to.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_id = options["user_id"]

        acting_user = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                acting_user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                raise CommandError(f"User with id {user_id} does not exist.")

        drafts = list(Application.objects.filter(status=Application.Status.DRAFT))

        if not drafts:
            self.stdout.write(self.style.SUCCESS("No draft applications found."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(drafts)} draft application(s):"
            )
        )
        for app in drafts:
            self.stdout.write(
                f"  - {app.id} (adopter={app.adopter.email}, pet={app.pet.name}, "
                f"created={app.created_at})"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        with transaction.atomic():
            for app in drafts:
                old_status = app.status
                app.status = Application.Status.SUBMITTED
                app.save(update_fields=["status", "updated_at"])
                AuditLog.objects.create(
                    user=acting_user,
                    action="status_change",
                    model_name="Application",
                    object_id=str(app.id),
                    previous_value=old_status,
                    new_value="submitted",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Transitioned {app.id}: {old_status} -> submitted"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(drafts)} application(s) transitioned to 'submitted'."
            )
        )
