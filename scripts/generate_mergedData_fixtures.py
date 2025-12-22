#!/usr/bin/env python3
"""Generate mergedData.json from individual RM endpoint fixture files.

This script merges data from multiple RM endpoint files to create a complete
parameter data structure, following the same logic as the API's
fetch_merged_rm_data_with_names_descs_and_structure() method.

The output matches what is stored in coordinator.data["mergedData"] in common.py.

Required source files (in tests/fixtures/<device>/):
- rmParamsData.json      - Basic parameter values, min/max, edit flags, unit indices
- rmParamsNames.json     - Human-readable parameter names
- rmParamsDescs.json     - Parameter descriptions
- rmStructure.json       - Menu structure and parameter numbers
- rmParamsUnitsNames.json - Unit symbols array
- rmParamsEnums.json     - Enumeration values for select-type parameters
- rmCatsNames.json       - Category names for menu organization
- rmLocksNames.json      - Lock reason messages (optional)

Output:
- mergedData.json        - Complete merged parameter data (matches coordinator.data["mergedData"])

Usage:
    python scripts/generate_mergedData_fixtures.py [device_folder]

    device_folder: Optional device folder name (default: ecoMAX810P-L)

Examples:
    python scripts/generate_mergedData_fixtures.py
    python scripts/generate_mergedData_fixtures.py ecoMAX360
    python scripts/generate_mergedData_fixtures.py ecoMAX860P3-V

"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

# Add parent directory to path for imports from custom_components
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.econet300.const import (
    CATEGORY_OTHER,
    SIMPLIFIED_CATEGORY_KEYWORDS,
)


def generate_translation_key(name: str) -> str:
    """Convert parameter name to Home Assistant translation key.

    This matches the implementation in common_functions.py.
    """
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

    # Handle other similar patterns
    return re.sub(r"(\w+)(\d+)_(\w+)", r"\1\2_\3", key)


def load_json_file(file_path: Path) -> dict | list | None:
    """Load and parse a JSON file."""
    if not file_path.exists():
        print(f"  [MISSING] {file_path.name}")
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        print(f"  [OK] {file_path.name}")
        return data
    except json.JSONDecodeError as e:
        print(f"  [ERROR] {file_path.name}: {e}")
        return None


def extract_data_array(json_data: dict | list | None) -> list:
    """Extract the data array from JSON response.

    RM endpoint responses have format: {"remoteMenu...Ver": version, "data": [...]}
    """
    if json_data is None:
        return []
    if isinstance(json_data, list):
        return json_data
    if isinstance(json_data, dict) and "data" in json_data:
        return json_data["data"]
    return []


def add_parameter_numbers(parameters: list[dict], structure: list[dict]) -> None:
    """Add parameter numbers based on structure data.

    The structure contains entries with type == 1 for parameters.
    Each parameter index maps to a structure entry index (parameter number).

    This matches api.py _add_parameter_numbers() method.
    """
    # Extract parameter entries from structure (type == 1)
    param_structure_entries = [
        item for item in structure if isinstance(item, dict) and item.get("type") == 1
    ]

    # Add numbers to parameters based on structure mapping
    for param in parameters:
        param_index = param.get("index", 0)

        # Use the structure entry index if available
        if param_index < len(param_structure_entries):
            structure_entry = param_structure_entries[param_index]
            param["number"] = structure_entry.get("index", param_index)
        else:
            # Fallback to parameter index if no structure entry
            param["number"] = param_index


def add_unit_names(parameters: list[dict], units: list[str]) -> None:
    """Add unit names to parameters based on unit indices.

    This matches api.py _add_unit_names() method.
    """
    for param in parameters:
        unit_index = param.get("unit")
        if (
            unit_index is not None
            and isinstance(unit_index, int)
            and unit_index < len(units)
            and isinstance(units[unit_index], str)
        ):
            param["unit_name"] = units[unit_index]
        else:
            param["unit_name"] = ""


def get_simplified_category(param_name: str, param_desc: str = "") -> str:
    """Get simplified category for a parameter using keywords from const.py.

    Uses the same logic as api.py _apply_simplified_categories() method.

    Args:
        param_name: Parameter name (e.g., "100% Blow-in output")
        param_desc: Parameter description

    Returns:
        Simplified category name (Boiler settings/HUW settings/Mixer settings/Other)

    """
    combined_text = f"{param_name.lower()} {param_desc.lower()}"

    for category, keywords in SIMPLIFIED_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined_text:
                return category

    return CATEGORY_OTHER


def add_parameter_categories(
    parameters_dict: dict[str, dict],
    structure: list[dict],  # kept for API compatibility, not used in simplified mode
    categories: list[str],  # kept for API compatibility, not used in simplified mode
) -> int:
    """Add simplified category information to parameters using keyword matching.

    Uses the same simplified category system as api.py _apply_simplified_categories().
    Categories: Boiler settings, HUW settings, Mixer settings, Other

    This matches api.py _add_parameter_categories() with CATEGORY_MODE_SIMPLIFIED.
    """
    category_count = 0

    for param in parameters_dict.values():
        param_name = param.get("name", "")
        param_desc = param.get("description", "")

        # Use simplified category assignment (same as api.py)
        category = get_simplified_category(param_name, param_desc)

        param["categories"] = [category]
        param["category"] = category
        param["category_indices"] = []
        param["category_index"] = 0
        category_count += 1

    return category_count


def add_parameter_categories_from_structure(
    parameters_dict: dict[str, dict],
    structure: list[dict],
    categories: list[str],
) -> int:
    """Add category information to parameters based on API structure data.

    This is the original structure-based mapping (CATEGORY_MODE_API).
    Kept for reference but not used by default.

    Structure types:
    - type 7 = category/menu group (index maps to rmCatsNames array)
    - type 1 = parameter (index is the parameter number)
    """
    if not categories:
        return 0

    # Map parameter numbers to their categories from structure
    param_to_categories: dict[int, list[tuple[int, str]]] = {}
    current_category_index: int | None = None

    for entry in structure:
        if not isinstance(entry, dict):
            continue

        entry_type = entry.get("type")
        entry_index = entry.get("index")

        if entry_type == 7:  # Category/menu group
            if isinstance(entry_index, int) and entry_index < len(categories):
                current_category_index = entry_index
        elif entry_type == 1:  # Parameter
            if isinstance(entry_index, int) and current_category_index is not None:
                category_name = categories[current_category_index]
                if entry_index not in param_to_categories:
                    param_to_categories[entry_index] = []
                existing_indices = [idx for idx, _ in param_to_categories[entry_index]]
                if current_category_index not in existing_indices:
                    param_to_categories[entry_index].append(
                        (current_category_index, category_name)
                    )

    # Add categories to parameters
    category_count = 0

    for param in parameters_dict.values():
        param_number = param.get("number")

        if isinstance(param_number, int) and param_number in param_to_categories:
            category_tuples = param_to_categories[param_number]
            param_category_indices = [idx for idx, _ in category_tuples]
            param_category_names = [name for _, name in category_tuples]
            param["categories"] = param_category_names
            param["category"] = param_category_names[0] if param_category_names else ""
            param["category_indices"] = param_category_indices
            param["category_index"] = (
                param_category_indices[0] if param_category_indices else 0
            )
            category_count += len(category_tuples)
        else:
            # No category found - mark as empty
            param["categories"] = []
            param["category"] = ""
            param["category_indices"] = []
            param["category_index"] = 0

    return category_count


def add_parameter_locks(
    parameters_dict: dict[str, dict],
    structure: list[dict],
    lock_names: list[str] | None = None,
) -> int:
    """Add lock status to parameters based on structure data.

    This matches api.py _add_parameter_locks() method.
    """
    # Build mapping: parameter_number -> (lock_status, lock_index)
    param_to_lock: dict[int, tuple[bool, int | None]] = {}

    for entry in structure:
        if not isinstance(entry, dict):
            continue

        entry_type = entry.get("type")
        entry_index = entry.get("index")
        entry_lock = entry.get("lock", False)
        entry_lock_index = entry.get("lock_index")

        if entry_type == 1:  # Parameter
            if entry_index is not None:
                param_to_lock[entry_index] = (entry_lock, entry_lock_index)

    # Add lock status to parameters based on their number
    lock_count = 0
    for param in parameters_dict.values():
        param_number = param.get("number")
        if isinstance(param_number, int) and param_number in param_to_lock:
            locked, lock_index = param_to_lock[param_number]
            param["locked"] = locked
            param["lock_index"] = lock_index

            # Add lock reason from rmLocksNames if available
            if locked and lock_index is not None and lock_names:
                if 0 <= lock_index < len(lock_names):
                    param["lock_reason"] = lock_names[lock_index]
                else:
                    param["lock_reason"] = "Parameter locked"
            else:
                param["lock_reason"] = None

            if locked:
                lock_count += 1
        else:
            param["locked"] = False
            param["lock_index"] = None
            param["lock_reason"] = None

    return lock_count


def add_enum_data_from_unit_offset(
    parameters_dict: dict[str, dict],
    enums: list[dict],
) -> int:
    """Add enum data to parameters based on unit=31 and offset field.

    According to ecoNET24 web interface JS code (dev_set3.js):
    - When unit == 31 (ENUM_UNIT), the offset field contains the enum index
    - This is the authoritative source for enum type parameters

    This matches api.py _add_enum_data_from_unit_offset() method.
    """
    # ENUM_UNIT constant from ecoNET24 JS code
    ENUM_UNIT = 31

    enum_count = 0
    for param in parameters_dict.values():
        # Check if this parameter has unit=31 (ENUM_UNIT)
        if param.get("unit") == ENUM_UNIT:
            # The offset field contains the enum index
            enum_id = param.get("offset", 0)

            # Get enum data if available
            if isinstance(enum_id, int) and 0 <= enum_id < len(enums):
                enum_data = enums[enum_id]
                if isinstance(enum_data, dict) and enum_data.get("values"):
                    param["enum"] = {
                        "id": enum_id,
                        "values": enum_data.get("values", []),
                        "first": enum_data.get("first", 0),
                        "detection_method": "unit_offset",
                    }
                    # Add current enum value if applicable
                    value = param.get("value")
                    first = enum_data.get("first", 0)
                    values = enum_data.get("values", [])
                    if isinstance(value, int) and values:
                        adjusted_index = value - first
                        if 0 <= adjusted_index < len(values):
                            param["enum_value"] = values[adjusted_index]
                    enum_count += 1

    return enum_count


def add_enum_data_from_structure(
    parameters_dict: dict[str, dict],
    structure: list[dict],
    enums: list[dict],
) -> int:
    """Add enum data to parameters based on structure data_id references.

    This is a fallback method for parameters that don't have unit=31.
    This matches api.py _add_enum_data_from_structure() method.
    """
    # Create structure enum map
    structure_enum_map = {}
    for entry in structure:
        if isinstance(entry, dict) and "data_id" in entry:
            param_index = entry.get("index")
            enum_id = int(entry.get("data_id", 0))
            if param_index is not None:
                structure_enum_map[param_index] = enum_id

    # Add enum data to parameters
    enum_count = 0
    for param in parameters_dict.values():
        # Skip if already has enum data (from unit/offset method)
        if "enum" in param:
            continue

        param_number = param.get("number")
        if param_number is not None and param_number in structure_enum_map:
            enum_id = structure_enum_map[param_number]
            if 0 <= enum_id < len(enums):
                enum_data = enums[enum_id]
                if isinstance(enum_data, dict) and enum_data.get("values"):
                    param["enum"] = {
                        "id": enum_id,
                        "values": enum_data.get("values", []),
                        "first": enum_data.get("first", 0),
                        "detection_method": "structure_data_id",
                    }
                    # Add current enum value if applicable
                    value = param.get("value")
                    first = enum_data.get("first", 0)
                    values = enum_data.get("values", [])
                    if isinstance(value, int) and values:
                        adjusted_index = value - first
                        if 0 <= adjusted_index < len(values):
                            param["enum_value"] = values[adjusted_index]
                    enum_count += 1

    return enum_count


def add_smart_enum_detection(
    parameters_dict: dict[str, dict],
    enums: list[dict],
) -> int:
    """Add enum data using smart detection for parameters without prior enum mapping.

    This is the last fallback method for enum detection.
    This matches api.py _add_smart_enum_detection() method.
    """
    smart_count = 0

    for param in parameters_dict.values():
        # Skip if already has enum (from unit/offset or structure methods)
        if "enum" in param:
            continue

        # Check if parameter should have smart enum detection
        if not should_detect_enum_smart(param):
            continue

        # Find best matching enum
        best_enum_id = find_best_matching_enum(param, enums)
        if best_enum_id is not None and 0 <= best_enum_id < len(enums):
            enum_data = enums[best_enum_id]
            if isinstance(enum_data, dict) and enum_data.get("values"):
                param["enum"] = {
                    "id": best_enum_id,
                    "values": enum_data.get("values", []),
                    "first": enum_data.get("first", 0),
                    "detection_method": "smart_detection",
                }
                # Add current enum value if applicable
                value = param.get("value")
                first = enum_data.get("first", 0)
                values = enum_data.get("values", [])
                if isinstance(value, int) and values:
                    adjusted_index = value - first
                    if 0 <= adjusted_index < len(values):
                        param["enum_value"] = values[adjusted_index]
                smart_count += 1

    return smart_count


def should_detect_enum_smart(param: dict) -> bool:
    """Determine if a parameter should have smart enum detection applied.

    This matches api.py _should_detect_enum_smart() method.
    """
    # Check for empty unit_name (indicates enum-type parameter)
    unit_name = param.get("unit_name", "")
    if unit_name != "":
        return False

    # Check for special unit indices that typically indicate enums
    unit_index = param.get("unit")
    if unit_index in [31]:  # Known enum unit indices
        return True

    # Check if description contains enum-like patterns
    description = param.get("description", "").lower()
    enum_patterns = [
        "off",
        "on",
        "auto",
        "manual",
        "enabled",
        "disabled",
        "start",
        "stop",
        "open",
        "close",
        "connected",
        "disconnected",
    ]

    pattern_matches = sum(1 for pattern in enum_patterns if pattern in description)
    if pattern_matches >= 2:  # At least 2 enum-like patterns
        return True

    # Check if min/max values suggest discrete states
    minv = param.get("minv", 0)
    maxv = param.get("maxv", 0)
    if isinstance(minv, (int, float)) and isinstance(maxv, (int, float)):
        # If range is small and discrete, likely an enum
        if 0 <= minv <= maxv <= 10 and maxv - minv <= 5:
            return True

    return False


def find_best_matching_enum(param: dict, enums: list[dict]) -> int | None:
    """Find the best matching enum for a parameter based on description analysis.

    This matches api.py _find_best_matching_enum() method.
    """
    description = param.get("description", "").lower()
    minv = param.get("minv", 0)
    maxv = param.get("maxv", 0)

    # Calculate expected enum size
    expected_size = (
        maxv - minv + 1 if isinstance(maxv, int) and isinstance(minv, int) else 2
    )

    best_match_id = None
    best_score = 0

    for enum_id, enum_data in enumerate(enums):
        if not isinstance(enum_data, dict):
            continue

        values = enum_data.get("values", [])
        if not values:
            continue

        # Skip empty enums
        non_empty_values = [v for v in values if v]
        if not non_empty_values:
            continue

        # Calculate match score
        score = 0

        # Size match (higher weight)
        if len(non_empty_values) == expected_size:
            score += 3

        # Check for value matches in description
        for value in non_empty_values:
            if value.lower() in description:
                score += 2

        # OFF/ON enum is common fallback (enum_id 1)
        if enum_id == 1 and expected_size == 2:
            score += 1

        if score > best_score:
            best_score = score
            best_match_id = enum_id

    return best_match_id if best_score > 0 else None


def generate_merged_data(fixtures_root: Path, device_folder: str) -> dict | None:
    """Generate complete merged parameter data from individual RM endpoint files.

    This follows the exact logic of api.py fetch_merged_rm_data_with_names_descs_and_structure()
    which is called by common.py EconetDataCoordinator._async_update_data() and stored
    in coordinator.data["mergedData"].

    Args:
        fixtures_root: Path to the fixtures root directory
        device_folder: Name of the device folder (e.g., "ecoMAX810P-L")

    Returns:
        Complete merged data dictionary or None if generation fails

    """
    device_path = fixtures_root / device_folder

    if not device_path.exists():
        print(f"Error: Device folder not found: {device_path}")
        return None

    print(f"\n[LOADING SOURCE FILES FROM {device_folder}]")
    print("=" * 60)

    # Load all required files
    params_data_json = load_json_file(device_path / "rmParamsData.json")
    params_names_json = load_json_file(device_path / "rmParamsNames.json")
    params_descs_json = load_json_file(device_path / "rmParamsDescs.json")
    structure_json = load_json_file(device_path / "rmStructure.json")
    units_json = load_json_file(device_path / "rmParamsUnitsNames.json")
    enums_json = load_json_file(device_path / "rmParamsEnums.json")
    cats_json = load_json_file(device_path / "rmCatsNames.json")
    locks_json = load_json_file(device_path / "rmLocksNames.json")

    # Extract data arrays
    params_data = extract_data_array(params_data_json)
    params_names = extract_data_array(params_names_json)
    params_descs = extract_data_array(params_descs_json)
    structure = extract_data_array(structure_json)
    units = extract_data_array(units_json)
    enums = extract_data_array(enums_json)
    categories = extract_data_array(cats_json)
    lock_names = extract_data_array(locks_json)

    if not params_data:
        print("\nError: No parameter data available (rmParamsData.json)")
        return None

    print(
        "\n[MERGING DATA - Following api.py fetch_merged_rm_data_with_names_descs_and_structure()]"
    )
    print("=" * 60)

    # Step 1: Merge parameter data with names (fetch_merged_rm_data_with_names)
    print("Step 1: Merging rmParamsData + rmParamsNames...")
    merged_params = []
    for i, param in enumerate(params_data):
        if isinstance(param, dict):
            merged_param = param.copy()

            # Add name if available
            if i < len(params_names) and isinstance(params_names, list):
                merged_param["name"] = params_names[i]
            else:
                merged_param["name"] = f"Parameter {i}"

            # Add index for reference
            merged_param["index"] = i

            merged_params.append(merged_param)

    print(f"  - Merged {len(merged_params)} parameters with names")

    # Step 2: Add descriptions (fetch_merged_rm_data_with_names_and_descs)
    print("Step 2: Adding descriptions from rmParamsDescs...")
    for i, param in enumerate(merged_params):
        if i < len(params_descs) and isinstance(params_descs, list):
            param["description"] = params_descs[i]
        else:
            param["description"] = ""

    desc_count = len([p for p in merged_params if p.get("description")])
    print(f"  - Added descriptions to {desc_count} parameters")

    # Step 3: Add parameter numbers from structure (_add_parameter_numbers)
    print("Step 3: Adding parameter numbers from rmStructure...")
    add_parameter_numbers(merged_params, structure)

    # Step 4: Add unit names (_add_unit_names)
    print("Step 4: Adding unit names from rmParamsUnitsNames...")
    add_unit_names(merged_params, units)

    # Step 5: Add translation keys (generate_translation_key)
    print("Step 5: Generating translation keys...")
    for param in merged_params:
        if "name" in param:
            param["key"] = generate_translation_key(param["name"])

    # Step 6: Convert to indexed dictionary (parameters array to object)
    print("Step 6: Converting to indexed parameter dictionary...")
    parameters_dict: dict[str, dict] = {}
    for param in merged_params:
        param_index = str(param.get("index", 0))
        parameters_dict[param_index] = param

    # Step 7: Add enum data (priority: unit/offset > structure > smart detection)
    print("Step 7: Adding enum data from rmParamsEnums...")
    unit_enum_count = add_enum_data_from_unit_offset(parameters_dict, enums)
    struct_enum_count = add_enum_data_from_structure(parameters_dict, structure, enums)
    smart_enum_count = add_smart_enum_detection(parameters_dict, enums)
    print(
        f"  - Added {unit_enum_count} enums from unit/offset, {struct_enum_count} from structure, {smart_enum_count} smart-detected"
    )

    # Step 8: Add category information (_add_parameter_categories)
    print("Step 8: Adding category information from rmCatsNames...")
    category_count = add_parameter_categories(parameters_dict, structure, categories)
    print(f"  - Added category info to {category_count} parameter assignments")

    # Step 9: Add lock status (_add_parameter_locks)
    print("Step 9: Adding lock status from rmLocksNames...")
    lock_count = add_parameter_locks(parameters_dict, structure, lock_names)
    print(f"  - Found {lock_count} locked parameters")

    # Build final structure (matches api.py output format)
    merged_data = {
        "version": "1.0-names-descs-structure-units-indexed-enums-categories-locks-cleaned",
        "timestamp": datetime.now().isoformat(),
        "device": {
            "uid": f"{device_folder}-device",
            "controllerId": device_folder,
            "language": "en",
        },
        "parameters": parameters_dict,
        "metadata": {
            "totalParameters": len(parameters_dict),
            "namedParameters": len(
                [p for p in parameters_dict.values() if p.get("name")]
            ),
            "describedParameters": len(
                [p for p in parameters_dict.values() if p.get("description")]
            ),
            "editableParameters": len(
                [p for p in parameters_dict.values() if p.get("edit", False)]
            ),
            "enumParameters": len([p for p in parameters_dict.values() if "enum" in p]),
            "lockedParameters": lock_count,
        },
        "sourceEndpoints": {
            "rmParamsData": "Parameter metadata (values, min/max, units, edit flags)",
            "rmParamsNames": "Human-readable parameter names",
            "rmParamsDescs": "Parameter descriptions",
            "rmStructure": "Menu structure and parameter numbers",
            "rmParamsUnitsNames": "Unit symbols",
            "rmParamsEnums": "Enumeration values",
            "rmCatsNames": "Category names",
            "rmLocksNames": "Lock reason messages",
        },
    }

    return merged_data


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate mergedData.json from individual RM endpoint files"
    )
    parser.add_argument(
        "device_folder",
        nargs="?",
        default="ecoMAX810P-L",
        help="Device folder name (default: ecoMAX810P-L)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: tests/fixtures/<device>/mergedData.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to stdout instead of writing to file",
    )

    args = parser.parse_args()

    # Find fixtures root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    fixtures_root = project_root / "tests" / "fixtures"

    if not fixtures_root.exists():
        print(f"Error: Fixtures directory not found: {fixtures_root}")
        return 1

    print("[MERGED DATA FIXTURE GENERATOR]")
    print("=" * 60)
    print(f"Device: {args.device_folder}")
    print(f"Fixtures root: {fixtures_root}")
    print("Output: mergedData.json (matches coordinator.data['mergedData'])")

    # Generate the merged data
    merged_data = generate_merged_data(fixtures_root, args.device_folder)

    if merged_data is None:
        print("\nGeneration failed!")
        return 1

    # Print statistics
    print("\n[GENERATION COMPLETE]")
    print("=" * 60)
    metadata = merged_data.get("metadata", {})
    print(f"Total parameters: {metadata.get('totalParameters', 0)}")
    print(f"Named parameters: {metadata.get('namedParameters', 0)}")
    print(f"Described parameters: {metadata.get('describedParameters', 0)}")
    print(f"Editable parameters: {metadata.get('editableParameters', 0)}")
    print(f"Enum parameters: {metadata.get('enumParameters', 0)}")
    print(f"Locked parameters: {metadata.get('lockedParameters', 0)}")

    # Output
    if args.dry_run:
        print("\n[DRY RUN - OUTPUT]")
        print("=" * 60)
        print(json.dumps(merged_data, indent=2, ensure_ascii=False))
    else:
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = fixtures_root / args.device_folder / "mergedData.json"

        # Write to file
        output_path.write_text(
            json.dumps(merged_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nOutput written to: {output_path}")
        print(f"File size: {output_path.stat().st_size:,} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
