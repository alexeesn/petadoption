# Restored migration already applied to deployed databases.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="no_show_reason",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Staff note recorded when the adopter did not show up for a confirmed "
                    "visit. The adoption is not cancelled by a no-show alone."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_confirmation", "Pending Confirmation"),
                    ("confirmed", "Confirmed"),
                    ("rejected", "Rejected"),
                    ("no_show", "No-show"),
                ],
                default="pending_confirmation",
                max_length=32,
            ),
        ),
    ]
