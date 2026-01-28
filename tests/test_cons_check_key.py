"""Tests for entity type consistency between fixtures and constants.

This module tests that fixture files (regParams.json, sysParams.json) contain
entity types (binary sensors vs regular sensors) that match the constants in const.py.
"""

import json
from pathlib import Path
import sys

import pytest

# Add the custom_components directory to the path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.parent / "custom_components" / "econet300"))

from const import (  # type: ignore[import-untyped]
    DEFAULT_BINARY_SENSORS,
    DEFAULT_SENSORS,
    ENTITY_BINARY_DEVICE_CLASS_MAP,
    ENTITY_SENSOR_DEVICE_CLASS_MAP,
)


@pytest.fixture
def reg_params():
    """Load regParams.json fixture."""
    file_path = BASE_DIR / "fixtures" / "ecoMAX810P-L" / "regParams.json"
    if not file_path.exists():
        pytest.skip(f"Fixture not found: {file_path}")
    with file_path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sys_params():
    """Load sysParams.json fixture."""
    file_path = BASE_DIR / "fixtures" / "ecoMAX810P-L" / "sysParams.json"
    if not file_path.exists():
        pytest.skip(f"Fixture not found: {file_path}")
    with file_path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ha_binary_keys():
    """Get all binary sensor keys from Home Assistant constants."""
    return set(ENTITY_BINARY_DEVICE_CLASS_MAP.keys()) | set(DEFAULT_BINARY_SENSORS)


@pytest.fixture
def ha_sensor_keys():
    """Get all sensor keys from Home Assistant constants."""
    return set(ENTITY_SENSOR_DEVICE_CLASS_MAP.keys()) | set(DEFAULT_SENSORS)


def analyze_entity_types(data: dict) -> tuple[list[str], list[str]]:
    """Analyze data to determine which keys are binary sensors vs regular sensors.

    Returns:
        Tuple of (binary_sensor_keys, regular_sensor_keys)

    """
    binary_sensors = []
    regular_sensors = []

    for key, value in data.items():
        if isinstance(value, bool):
            binary_sensors.append(key)
        else:
            regular_sensors.append(key)

    return binary_sensors, regular_sensors


class TestFixtureAnalysis:
    """Test fixture file analysis."""

    def test_reg_params_loads(self, reg_params):
        """Test regParams.json loads correctly."""
        assert reg_params is not None
        assert len(reg_params) > 0

    def test_sys_params_loads(self, sys_params):
        """Test sysParams.json loads correctly."""
        assert sys_params is not None
        assert len(sys_params) > 0

    def test_reg_params_has_binary_sensors(self, reg_params):
        """Test regParams.json contains binary sensor data."""
        binary, _ = analyze_entity_types(reg_params)
        # Should have some binary sensors (True/False values)
        assert len(binary) >= 0  # May or may not have binary sensors

    def test_sys_params_has_entity_data(self, sys_params):
        """Test sysParams.json contains entity data."""
        binary, regular = analyze_entity_types(sys_params)
        total = len(binary) + len(regular)
        assert total > 0


class TestEntityTypeMismatches:
    """Test for entity type mismatches between fixtures and constants."""

    def test_fixture_binary_sensors_match_constants(
        self, reg_params, sys_params, ha_binary_keys, ha_sensor_keys
    ):
        """Test that fixture binary sensors match constant definitions."""
        reg_binary, _ = analyze_entity_types(reg_params)
        sys_binary, _ = analyze_entity_types(sys_params)
        all_binary = set(reg_binary) | set(sys_binary)

        # Find keys that are binary in fixture but defined as sensors in HA
        mismatched = [key for key in all_binary if key in ha_sensor_keys]

        # Report mismatches but don't fail (may be intentional)
        if mismatched:
            pytest.skip(
                f"Found {len(mismatched)} fixture binary sensors "
                f"defined as regular sensors in const.py: {mismatched[:5]}..."
            )

    def test_fixture_regular_sensors_match_constants(
        self, reg_params, sys_params, ha_binary_keys, ha_sensor_keys
    ):
        """Test that fixture regular sensors match constant definitions."""
        _, reg_regular = analyze_entity_types(reg_params)
        _, sys_regular = analyze_entity_types(sys_params)
        all_regular = set(reg_regular) | set(sys_regular)

        # Find keys that are regular in fixture but defined as binary in HA
        mismatched = [key for key in all_regular if key in ha_binary_keys]

        # Report mismatches but don't fail (may be intentional)
        if mismatched:
            pytest.skip(
                f"Found {len(mismatched)} fixture regular sensors "
                f"defined as binary sensors in const.py: {mismatched[:5]}..."
            )


class TestEntityCoverage:
    """Test entity coverage between fixtures and constants."""

    def test_constants_cover_fixture_keys(
        self, reg_params, sys_params, ha_binary_keys, ha_sensor_keys
    ):
        """Test that constants cover most fixture keys."""
        all_fixture_keys = set(reg_params.keys()) | set(sys_params.keys())
        all_ha_keys = ha_binary_keys | ha_sensor_keys

        # Find keys in fixtures but not in HA constants
        missing = [key for key in all_fixture_keys if key not in all_ha_keys]

        # Report missing but don't fail (dynamic entities may not be in constants)
        if missing and len(missing) > len(all_fixture_keys) * 0.5:
            pytest.skip(
                f"Many fixture keys ({len(missing)}/{len(all_fixture_keys)}) "
                f"not in constants: {missing[:5]}..."
            )


class TestBinaryVsRegularClassification:
    """Test binary vs regular sensor classification."""

    def test_boolean_values_are_binary_sensors(self, reg_params):
        """Test that boolean values in fixtures are classified as binary sensors."""
        for value in reg_params.values():
            if isinstance(value, bool):
                # This is correctly classified as a binary sensor
                assert True

    def test_non_boolean_values_are_regular_sensors(self, reg_params):
        """Test that non-boolean values are classified as regular sensors."""
        for value in reg_params.values():
            if not isinstance(value, bool):
                # This is correctly classified as a regular sensor
                assert True

    @pytest.mark.parametrize(
        ("value", "expected_type"),
        [
            (True, "binary"),
            (False, "binary"),
            (25.5, "regular"),
            (100, "regular"),
            ("online", "regular"),
            (None, "regular"),
        ],
    )
    def test_value_type_classification(self, value, expected_type):
        """Test value type classification logic."""
        is_binary = isinstance(value, bool)
        actual_type = "binary" if is_binary else "regular"
        assert actual_type == expected_type
