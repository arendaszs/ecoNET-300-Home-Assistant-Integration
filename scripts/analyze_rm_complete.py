#!/usr/bin/env python3
"""Analyze mergedData.json and show how it relates to individual RM endpoints."""

import json
from pathlib import Path


def analyze_merged_data():
    """Analyze the mergedData.json fixture."""
    fixtures_root = Path("tests/fixtures/ecoMAX810P-L")
    merged_file = fixtures_root / "mergedData.json"

    if not merged_file.exists():
        print(f"Error: {merged_file} not found")
        return

    # Load the merged data
    complete_data = json.loads(merged_file.read_text(encoding="utf-8"))

    print("[MERGED DATA ANALYSIS]")
    print("=" * 50)

    # Show version and metadata
    print(f"Version: {complete_data.get('version', 'N/A')}")
    print(f"Timestamp: {complete_data.get('timestamp', 'N/A')}")

    device_info = complete_data.get("device", {})
    print(f"Device UID: {device_info.get('uid', 'N/A')}")
    print(f"Controller ID: {device_info.get('controllerId', 'N/A')}")
    print(f"Language: {device_info.get('language', 'N/A')}")
    print()

    # Analyze parameters
    parameters = complete_data.get("parameters", {})
    print(f"[PARAMETERS: {len(parameters)} total]")

    # Sample first parameter
    if parameters:
        first_param_key = next(iter(parameters.keys()))
        first_param = parameters[first_param_key]

        print("\n[SAMPLE PARAMETER STRUCTURE]")
        print(f"Parameter ID: {first_param_key}")
        for key, value in first_param.items():
            if key == "description" and len(str(value)) > 50:
                print(f"  {key}: {str(value)[:50]}...")
            else:
                print(f"  {key}: {value}")

    # Count editable vs read-only
    editable_count = sum(1 for p in parameters.values() if p.get("edit", False))
    readonly_count = len(parameters) - editable_count

    print("\n[PARAMETER STATS]")
    print(f"  Editable (number entities): {editable_count}")
    print(f"  Read-only (sensor entities): {readonly_count}")

    # Analyze units
    units_used = set()
    for param in parameters.values():
        unit_name = param.get("unit_name", "")
        if unit_name:
            units_used.add(unit_name)

    print(f"\n[UNITS USED: {len(units_used)}]")
    for unit in sorted(units_used):
        print(f"  - {unit}")

    # Show what endpoints this data came from
    print("\n[DERIVED FROM ENDPOINTS]")
    print("  1. rmParamsData -> Basic parameter values, limits, edit flags")
    print("  2. rmParamsNames -> Human-readable names")
    print("  3. rmParamsDescs -> Parameter descriptions")
    print("  4. rmStructure -> Parameter numbers and menu structure")
    print("  5. rmParamsUnitsNames -> Unit symbols")
    print("  6. rmParamsEnums -> Enumeration values")

    print("\n[MERGING PROCESS]")
    print("  fetch_merged_rm_data_with_names_descs_and_structure()")
    print("  ->")
    print("  Single API call that combines all RM endpoints")
    print("  ->")
    print("  Complete parameter data ready for entity creation")

    print("\n[RELATED FIXTURE FILES]")
    fixture_files = [
        "rmParamsData.json",
        "rmParamsNames.json",
        "rmParamsDescs.json",
        "rmStructure.json",
        "rmParamsUnitsNames.json",
        "rmParamsEnums.json",
        "rmCatsNames.json",
    ]

    for fixture in fixture_files:
        file_path = fixtures_root / fixture
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"  [OK] {fixture} ({size} bytes)")
        else:
            print(f"  [MISSING] {fixture} (missing)")


if __name__ == "__main__":
    analyze_merged_data()
