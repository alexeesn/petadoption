def display_name(value):
    """Capitalize lowercase name parts while preserving intentional casing."""
    return " ".join(part.title() if part.islower() else part for part in str(value or "").split())
