from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("adoptions", "0004_adoptionrecord_cancellation_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="adoptionrecord",
            name="cancelled_at",
            field=models.DateTimeField(
                blank=True, null=True, help_text="When the adoption was cancelled"
            ),
        ),
        migrations.AddField(
            model_name="adoptionrecord",
            name="return_date",
            field=models.DateField(
                blank=True, null=True, help_text="Date the pet was actually returned"
            ),
        ),
        migrations.AddField(
            model_name="adoptionrecord",
            name="returned_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="When the completed adoption was recorded as returned",
            ),
        ),
    ]
