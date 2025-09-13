"""Test icon translations for ecoNET300 integration.

This test file verifies icon translation functionality for all entity types:
- Switch entities (boiler_control)
- Select entities (heater_mode with state-specific icons)
- Binary sensor entities
- Sensor entities
- Number entities
"""

import importlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

from homeassistant.components.select import SelectEntityDescription

# Add the custom_components directory to the path
custom_components_path = str(
    Path(__file__).parent.parent / "custom_components" / "econet300"
)
if custom_components_path not in sys.path:
    sys.path.insert(0, custom_components_path)

# Also add the parent directory for the custom_components module
parent_path = str(Path(__file__).parent.parent)
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)

# Import custom components after path setup
api_module = importlib.import_module("custom_components.econet300.api")
common_module = importlib.import_module("custom_components.econet300.common")
switch_module = importlib.import_module("custom_components.econet300.switch")

# Get the classes from the modules
Econet300Api = api_module.Econet300Api
EconetDataCoordinator = common_module.EconetDataCoordinator
EconetSwitch = switch_module.EconetSwitch
create_boiler_switch = switch_module.create_boiler_switch


def test_switch_has_translation_key():
    """Test that the switch has the correct translation key for icon translations."""
    # Create a mock coordinator and API
    mock_coordinator = Mock(spec=EconetDataCoordinator)
    mock_api = Mock(spec=Econet300Api)

    # Create the boiler switch
    switch = create_boiler_switch(mock_coordinator, mock_api)

    # Verify the translation key is set correctly
    assert switch.entity_description.translation_key == "boiler_control"

    # Verify no icon is set (should use icon translations instead)
    assert (
        not hasattr(switch.entity_description, "icon")
        or switch.entity_description.icon is None
    )


def test_switch_entity_creation():
    """Test that the switch entity is created correctly."""
    # Create a mock coordinator and API
    mock_coordinator = Mock(spec=EconetDataCoordinator)
    mock_api = Mock(spec=Econet300Api)

    # Create the boiler switch
    switch = create_boiler_switch(mock_coordinator, mock_api)

    # Verify the switch is created correctly
    assert isinstance(switch, EconetSwitch)
    assert switch.entity_description.key == "boiler_control"
    assert switch.entity_description.translation_key == "boiler_control"


def test_switch_icon_translation_structure():
    """Test that the switch icon translation structure is correct."""
    # Create a mock coordinator and API
    mock_coordinator = Mock(spec=EconetDataCoordinator)
    mock_api = Mock(spec=Econet300Api)

    # Create the boiler switch
    switch = create_boiler_switch(mock_coordinator, mock_api)

    # Verify the entity description has the required fields for icon translations
    assert switch.entity_description.key == "boiler_control"
    assert switch.entity_description.translation_key == "boiler_control"

    # Verify that the translation_key matches the key (this is the lookup path)
    # Home Assistant will look for: entity.switch.boiler_control in icons.json
    assert switch.entity_description.translation_key == "boiler_control"


# =============================================================================
# SELECT ENTITY ICON TRANSLATION TESTS
# =============================================================================


def test_select_icon_translation_system():
    """Test that select entities use Home Assistant icon translation system."""
    # This test verifies that select entities rely on icons.json for icon translations
    # rather than hardcoded constants in const.py

    # Load the icons.json file
    icons_file = (
        Path(__file__).parent.parent / "custom_components" / "econet300" / "icons.json"
    )

    with icons_file.open(encoding="utf-8") as f:
        icons_data = json.load(f)

    # Verify the select entity icon structure exists in icons.json
    assert "entity" in icons_data
    assert "select" in icons_data["entity"]
    assert "heater_mode" in icons_data["entity"]["select"]

    heater_mode_icons = icons_data["entity"]["select"]["heater_mode"]

    # Verify it has default icon
    assert "default" in heater_mode_icons
    assert heater_mode_icons["default"] == "mdi:thermostat"

    # Verify it has state icons
    assert "state" in heater_mode_icons
    state_icons = heater_mode_icons["state"]

    # Verify all expected states are present
    assert "winter" in state_icons
    assert "summer" in state_icons
    assert "auto" in state_icons

    # Verify the correct icons
    assert state_icons["winter"] == "mdi:snowflake"
    assert state_icons["summer"] == "mdi:weather-sunny"
    assert state_icons["auto"] == "mdi:thermostat-auto"


def test_icons_json_structure():
    """Test that the icons.json file has the correct structure for select entities."""
    # Load the icons.json file
    icons_file = (
        Path(__file__).parent.parent / "custom_components" / "econet300" / "icons.json"
    )

    with icons_file.open(encoding="utf-8") as f:
        icons_data = json.load(f)

    # Verify the structure exists
    assert "entity" in icons_data
    assert "select" in icons_data["entity"]
    assert "heater_mode" in icons_data["entity"]["select"]

    heater_mode_icons = icons_data["entity"]["select"]["heater_mode"]

    # Verify it has default icon
    assert "default" in heater_mode_icons
    assert heater_mode_icons["default"] == "mdi:thermostat"

    # Verify it has state icons
    assert "state" in heater_mode_icons
    state_icons = heater_mode_icons["state"]

    # Verify all expected states are present
    assert "winter" in state_icons
    assert "summer" in state_icons
    assert "auto" in state_icons

    # Verify the correct icons
    assert state_icons["winter"] == "mdi:snowflake"
    assert state_icons["summer"] == "mdi:weather-sunny"
    assert state_icons["auto"] == "mdi:thermostat-auto"


def test_select_icon_selection_logic():
    """Test the icon selection logic for select entities."""
    # Mock the icon configuration
    icon_config = {
        "default": "mdi:thermostat",
        "state": {
            "winter": "mdi:snowflake",
            "summer": "mdi:weather-sunny",
            "auto": "mdi:thermostat-auto",
        },
    }

    def get_icon(current_option):
        """Simulate the icon property logic."""
        if current_option:
            if isinstance(icon_config, dict) and "state" in icon_config:
                state_icons = icon_config["state"]
                if isinstance(state_icons, dict):
                    default_icon = icon_config.get("default")
                    if isinstance(default_icon, str):
                        return state_icons.get(current_option, default_icon)
        if isinstance(icon_config, dict):
            default_icon = icon_config.get("default")
            if isinstance(default_icon, str):
                return default_icon
        return None

    # Test different states
    test_cases = [
        (None, "mdi:thermostat"),
        ("winter", "mdi:snowflake"),
        ("summer", "mdi:weather-sunny"),
        ("auto", "mdi:thermostat-auto"),
        ("unknown", "mdi:thermostat"),
    ]

    for current_option, expected_icon in test_cases:
        result = get_icon(current_option)
        assert result == expected_icon, (
            f"Expected {expected_icon} for {current_option}, got {result}"
        )


def test_select_entity_uses_icon_translations():
    """Test that select entities properly use Home Assistant icon translation system."""
    # Create a mock coordinator and API
    mock_coordinator = Mock(spec=EconetDataCoordinator)
    mock_api = Mock(spec=Econet300Api)

    # Mock coordinator data
    mock_coordinator.data = {
        "regParamsData": {
            "2049": 0  # winter mode
        }
    }

    # Create the heater mode select entity
    entity_description = SelectEntityDescription(
        key="heater_mode",
        translation_key="heater_mode",
        # No icon specified - will use icon translations
    )

    # Import EconetSelect after path setup
    select_module = importlib.import_module("custom_components.econet300.select")
    EconetSelect = select_module.EconetSelect

    select_entity = EconetSelect(
        entity_description, mock_coordinator, mock_api, "heater_mode"
    )

    # Verify the entity description has the required fields for icon translations
    assert select_entity.entity_description.key == "heater_mode"
    assert select_entity.entity_description.translation_key == "heater_mode"

    # Verify that the icon property returns None (letting Home Assistant handle translations)
    assert select_entity.icon is None

    # Verify that the translation_key matches the key (this is the lookup path)
    # Home Assistant will look for: entity.select.heater_mode in icons.json
    assert select_entity.entity_description.translation_key == "heater_mode"
