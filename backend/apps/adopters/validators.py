from datetime import date
from zoneinfo import ZoneInfo

from django.utils import timezone


def birthday_error(value):
    """A saved adopter birthday must establish adulthood in Philippine time."""
    if value is None:
        return "Date of birth is required."
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return "Enter a valid date of birth."
    today = timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()
    if value > today:
        return "Date of birth cannot be in the future."
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 18:
        return "You must be at least 18 years old."
    try:
        earliest = today.replace(year=today.year - 120)
    except ValueError:
        earliest = today.replace(year=today.year - 120, day=28)
    if value < earliest:
        return "Date of birth must be within the last 120 years."
    return None
