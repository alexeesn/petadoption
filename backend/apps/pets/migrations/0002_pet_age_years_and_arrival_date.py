import django.core.validators
from django.db import migrations, models


def months_to_years(apps, schema_editor):
    """Convert the legacy `age_months` values to whole years.

    Ages that are younger than one year become 0, which the portals display as
    "Under 1 year" rather than losing the pet entirely.

    `RenameField` above has already renamed the column by the time this runs,
    so the historical model exposes `age_years` even though the stored values
    are still months. Using `age_months` here would raise AttributeError on
    any database that already contains pets.
    """
    Pet = apps.get_model("pets", "Pet")
    for pet in Pet.objects.all():
        pet.age_years = pet.age_years // 12
        pet.save(update_fields=["age_years"])


def years_to_months(apps, schema_editor):
    """Reverse of `months_to_years`; sub-year precision cannot be restored.

    Same as above: the rename is only undone after this function runs, so the
    historical model still exposes `age_years` here.
    """
    Pet = apps.get_model("pets", "Pet")
    for pet in Pet.objects.all():
        pet.age_years = pet.age_years * 12
        pet.save(update_fields=["age_years"])


class Migration(migrations.Migration):

    dependencies = [
        ("pets", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pet",
            old_name="age_months",
            new_name="age_years",
        ),
        migrations.RunPython(months_to_years, years_to_months),
        migrations.AlterField(
            model_name="pet",
            name="age_years",
            field=models.PositiveIntegerField(
                help_text="Age in years",
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(40),
                ],
            ),
        ),
        migrations.AddField(
            model_name="pet",
            name="arrival_date",
            field=models.DateField(
                blank=True,
                help_text="Date the pet arrived at the adoption center",
                null=True,
            ),
        ),
    ]