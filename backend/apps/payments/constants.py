from decimal import Decimal
from django.conf import settings

# Central reference adoption fee for the prototype (Quezon City-based prototype).
# Stored as Decimal to ensure all monetary operations remain exact and validated.
PROTOTYPE_ADOPTION_FEE: Decimal = getattr(
    settings, "PROTOTYPE_ADOPTION_FEE", Decimal("500.00")
)
