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


def extract_device_group_from_name(
    name: str | None, for_information: bool = False
) -> tuple[int | None, str | None]:
    """Extract device group from parameter name using heuristics.

    Analyzes parameter names to determine the most appropriate device grouping
    based on keywords like "mixer 1", "lambda", "boiler", "HUW", etc.

    This helps correctly group parameters that may be miscategorized in the
    ecoNET rmStructure data (e.g., mixer parameters under "Chimney sweep mode").

    Args:
        name: Parameter name (e.g., "Heating curve. mixer 2", "Lambda sensor")
        for_information: If True, returns Information-type categories for sensors
                        If False, returns Settings-type categories for numbers

    Returns:
        Tuple of (category_index, category_name) for the matched device group,
        or (None, None) if no specific device pattern is found.

    Category indices (from rmCatsNames):
        - Settings: 2=Boiler, 3=HUW, 5-8=Mixer 1-4, 32=Buffer, 43=Lambda
        - Information: 16-19=Information mixer 1-4

    """
    if not name:
        return None, None

    name_lower = name.lower()

    # Check for mixer patterns (highest priority for mixer-specific params)
    # Matches: "mixer 1", "mixer1", "Mixer 2", etc.
    mixer_match = re.search(r"mixer\s*(\d+)", name_lower)
    if mixer_match:
        mixer_num = int(mixer_match.group(1))
        if 1 <= mixer_num <= 4:
            if for_information:
                # Information mixer devices are at index 16-19
                return 15 + mixer_num, f"Information mixer {mixer_num}"
            # Mixer settings are at index 5-8
            return 4 + mixer_num, f"Mixer {mixer_num} settings"

    # Check for lambda sensor
    if "lambda" in name_lower:
        return 43, "Lambda sensor"

    # Check for HUW (Hot Utility Water / DHW)
    # Case-insensitive check for "huw" or "dhw"
    if "huw" in name_lower or "dhw" in name_lower:
        return 3, "HUW settings"

    # Check for buffer
    if "buffer" in name_lower:
        return 32, "Buffer settings"

    # Check for boiler/burner/feed/feeder/fan/blow-in/air/fuel (all part of boiler system)
    if any(
        keyword in name_lower
        for keyword in [
            "boiler",
            "burner",
            "feed",
            "feeder",
            "fan",
            "blow",
            "air",
            "fuel",
        ]
    ):
        return 2, "Boiler settings"

    return None, None


def is_binary_enum(enum_values: list[str] | None) -> bool:
    """Check if enum represents a binary ON/OFF type switch.

    Binary enums have exactly 2 values representing ON/OFF states.
    Note: Only checks the first 2 values since enum.values may have
    incorrect mappings from the API.

    Args:
        enum_values: List of enum option strings (e.g., ["OFF", "ON"])

    Returns:
        True if first 2 enum values represent binary state patterns

    """
    if not enum_values or len(enum_values) < 2:
        return False

    # Take only first 2 values (min/max determines actual option count)
    check_values = enum_values[:2]
    values_lower = [v.lower() for v in check_values]

    # Common binary patterns
    binary_patterns = [
        {"off", "on"},
        {"no", "yes"},
        {"disable", "enable"},
        {"disabled", "enabled"},
        {"inactive", "active"},
        {"false", "true"},
        {"0", "1"},
    ]

    return set(values_lower) in binary_patterns


def get_on_off_values(
    enum_values: list[str], enum_first: int = 0
) -> tuple[int, int] | None:
    """Get the API values for OFF and ON states from enum.

    Analyzes enum values to determine which index represents OFF and ON,
    then returns the corresponding API values (enum_first + index).

    Args:
        enum_values: List of enum option strings (e.g., ["OFF", "ON"])
        enum_first: First value offset from enum data (default 0)

    Returns:
        Tuple of (off_value, on_value) for API calls, or None if not binary

    """
    if not enum_values:
        return None

    # Take only first 2 values (min/max determines actual option count)
    check_values = enum_values[:2] if len(enum_values) >= 2 else enum_values

    if len(check_values) != 2:
        return None

    values_lower = [v.lower() for v in check_values]

    # Patterns where first value is OFF
    off_first_patterns = ["off", "no", "disable", "disabled", "inactive", "false", "0"]

    # Patterns where first value is ON
    on_first_patterns = ["on", "yes", "enable", "enabled", "active", "true", "1"]

    # Determine which index is OFF and which is ON
    if values_lower[0] in off_first_patterns:
        # First value is OFF (index 0), second is ON (index 1)
        return enum_first, enum_first + 1

    if values_lower[0] in on_first_patterns:
        # First value is ON (index 0), second is OFF (index 1)
        return enum_first + 1, enum_first

    # Default: assume first is OFF, second is ON
    return enum_first, enum_first + 1


def should_be_select_entity(param: dict) -> bool:
    """Check if parameter should be a Select entity.

    Select entities are for editable parameters with enum having 3+ values.
    Uses min/max range to determine option count, as enum.values may have
    incorrect mappings.

    Args:
        param: Parameter dictionary from mergedData

    Returns:
        True if parameter should be a Select entity

    """
    if not param.get("edit", False):
        return False

    enum_data = param.get("enum")
    if not enum_data:
        return False

    # Use min/max to determine actual number of options (more reliable)
    minv = param.get("minv")
    maxv = param.get("maxv")
    num_options = None

    if minv is not None and maxv is not None:
        try:
            num_options = int(maxv) - int(minv) + 1
        except (ValueError, TypeError):
            num_options = None

    # Use calculated num_options if available
    if num_options is not None:
        return num_options >= 3

    # Fallback to enum.values length
    enum_values = enum_data.get("values", [])
    return len(enum_values) >= 3 and not is_binary_enum(enum_values)


def should_be_switch_entity(param: dict) -> bool:
    """Check if parameter should be a Switch entity.

    Switch entities are for editable parameters with binary enum (2 values).
    Uses min/max range to determine option count, as enum.values may have
    incorrect mappings.

    Args:
        param: Parameter dictionary from mergedData

    Returns:
        True if parameter should be a Switch entity

    """
    if not param.get("edit", False):
        return False

    enum_data = param.get("enum")
    if not enum_data:
        return False

    # Use min/max to determine actual number of options (more reliable)
    minv = param.get("minv")
    maxv = param.get("maxv")
    if minv is not None and maxv is not None:
        try:
            num_options = int(maxv) - int(minv) + 1
            # Must have exactly 2 options
            if num_options != 2:
                return False
        except (ValueError, TypeError):
            pass

    # Check if enum values represent binary pattern
    enum_values = enum_data.get("values", [])
    return is_binary_enum(enum_values)


def mixer_exists(coordinator_data: dict | None, mixer_num: int) -> bool:
    """Check if a mixer exists by verifying regParams data.

    Mixers that don't exist in the boiler will have None values for their
    temperature sensors. This function checks if the mixer temperature
    data is available.

    Args:
        coordinator_data: Coordinator data dict containing regParams
        mixer_num: Mixer number (1-6)

    Returns:
        True if mixer has valid temperature data, False otherwise

    """
    if not coordinator_data:
        return False

    reg_params = coordinator_data.get("regParams", {})
    if not reg_params:
        return False

    mixer_temp_key = f"mixerTemp{mixer_num}"
    return reg_params.get(mixer_temp_key) is not None
