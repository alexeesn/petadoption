# Generated migration: add region and barangay fields to AdopterProfile.
# 
# Design: The existing address fields are preserved as-is to avoid breaking
# existing user records. Two new optional fields are added:
#   - region: e.g. "National Capital Region (NCR)"
#   - barangay: e.g. "Barangay 176"
#
# The existing fields map to Philippine address hierarchy:
#   address_line1  → house number / street / purok
#   address_line2  → optional additional line
#   city           → city or municipality
#   state          → province (blank for NCR and other no-province areas)
#   zip_code       → postal code
#
# No data is migrated from old free-text values — the backend stores whatever
# the adopter selects via the cascading dropdowns.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adopters", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="adopterprofile",
            name="region",
            field=models.CharField(
                max_length=200,
                blank=True,
                help_text="Philippine region (e.g. National Capital Region, Region IV-A)",
            ),
        ),
        migrations.AddField(
            model_name="adopterprofile",
            name="barangay",
            field=models.CharField(
                max_length=200,
                blank=True,
                help_text="Barangay within the selected city or municipality",
            ),
        ),
    ]
