from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("adoptions", "0003_adoptionrecord_transaction_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="adoptionrecord",
            name="cancellation_reason",
            field=models.TextField(
                blank=True,
                help_text="Why the scheduled adoption was cancelled (recorded by staff)",
            ),
        ),
    ]
