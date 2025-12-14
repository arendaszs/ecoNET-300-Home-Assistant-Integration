"""Functions used in Econet300 integration,."""

import re


def camel_to_snake(key: str) -> str:
    """Convert camel case return from API to snake case to match translations keys structure."""
    # Handle special cases first
    special_mappings = {
        "ecoSter": "ecoster",
        "ecoSOL": "ecosol",
        "ecoMAX": "ecomax",
        "ecoNET": "econet",
    }

    # Apply special mappings
    for camel_case, snake_case in special_mappings.items():
        if camel_case in key:
            key = key.replace(camel_case, snake_case)

    # Now apply the standard camel to snake conversion
    key = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", key)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", key).lower()


def generate_translation_key(name: str) -> str:
    """Convert parameter name to Home Assistant translation key."""
    # Replace common characters
    key = name.replace(" ", "_")
    key = key.replace("%", "percent")
    key = key.replace(".", "")
    key = key.replace("-", "_")
    key = key.replace("(", "")
    key = key.replace(")", "")
    key = key.replace(":", "")
    key = key.replace("'", "")
    key = key.replace('"', "")

    # Convert to lowercase
    key = key.lower()

    # Handle specific patterns: mixer 3 room therm -> mixer3_room_therm
    # Pattern: word + space + number + space + word -> word + number + underscore + word
    key = re.sub(r"(\w+)_(\d+)_(\w+)", r"\1\2_\3", key)

    # Handle other similar patterns: word + number + space + word -> word + number + underscore + word
    return re.sub(r"(\w+)(\d+)_(\w+)", r"\1\2_\3", key)


def get_parameter_type_from_category(category_name: str | None) -> str:
    """Determine parameter type (basic/service/advanced) from category name.

    Args:
        category_name: Category name from rmCatsNames (e.g., "Service Settings")

    Returns:
        'basic', 'service', or 'advanced'

    """
    if not category_name:
        return "basic"

    category_lower = category_name.lower()

    # Service categories
    if "service" in category_lower:
        return "service"

    # Advanced categories
    if "advanced" in category_lower:
        return "advanced"

    # Basic categories (user-friendly)
    return "basic"


def is_information_category(category_name: str | None) -> bool:
    """Check if category is an Information category (read-only sensor).

    Information categories should create read-only sensor entities,
    not editable number entities.

    Args:
        category_name: Category name from rmCatsNames (e.g., "Information")

    Returns:
        True if category is Information type

    """
    if not category_name:
        return False

    category_lower = category_name.lower()
    return "information" in category_lower


def is_service_or_advanced_category(category_name: str | None) -> bool:
    """Check if category requires show_service_parameters to be visible.

    Service and Advanced categories are only shown when the user enables
    show_service_parameters in the integration configuration.

    Args:
        category_name: Category name from rmCatsNames (e.g., "Service Settings")

    Returns:
        True if category is Service or Advanced type

    """
    if not category_name:
        return False

    category_lower = category_name.lower()
    return "service" in category_lower or "advanced" in category_lower


def sanitize_category_for_device_id(category_name: str) -> str:
    """Sanitize category name for use in device identifiers.

    Args:
        category_name: Category name from rmCatsNames (e.g., "Output modulation")

    Returns:
        Sanitized identifier safe for device IDs (e.g., "output_modulation")

    """
    if not category_name:
        return ""

    # Use similar logic to generate_translation_key
    key = category_name.replace(" ", "_")
    key = key.replace("%", "percent")
    key = key.replace(".", "")
    key = key.replace("-", "_")
    key = key.replace("(", "")
    key = key.replace(")", "")
    key = key.replace(":", "")
    key = key.replace("'", "")
    key = key.replace('"', "")
    key = key.replace("/", "_")
    key = key.lower()

    # Remove any remaining non-alphanumeric characters except underscore
    key = re.sub(r"[^a-z0-9_]", "", key)

    # Replace multiple underscores with single underscore
    key = re.sub(r"_+", "_", key)

    # Remove leading/trailing underscores
    return key.strip("_")
