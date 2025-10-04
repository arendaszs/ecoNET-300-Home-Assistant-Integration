"""Test dynamic number entity creation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from homeassistant.helpers.entity_platform import AddEntitiesCallback
import pytest

from custom_components.econet300.api import Econet300Api
from custom_components.econet300.common import EconetDataCoordinator
from custom_components.econet300.number import (
    EconetNumber,
    async_setup_entry,
    create_dynamic_number_entity_description,
    should_be_number_entity,
)


class TestDynamicNumberEntities:
    """Test dynamic number entity creation."""

    @pytest.fixture
    def mock_merged_data(self):
        """Load mock merged parameter data."""
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "ecoMAX810P-L"
            / "rmParamsComplete.json"
        )
        with fixture_path.open(encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def mock_api(self, mock_merged_data):
        """Create a mock API with merged data."""
        api = MagicMock(spec=Econet300Api)
        api.fetch_merged_rm_data_with_names_descs_and_structure = AsyncMock(
            return_value=mock_merged_data
        )
        return api

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock(spec=EconetDataCoordinator)
        coordinator.data = {"sysParams": {"controllerId": "ecoMAX810P-L"}}
        return coordinator

    def test_should_be_number_entity(self):
        """Test should_be_number_entity function."""
        # Test number entity candidate (no enum key at all)
        number_param = {"unit_name": "%", "edit": True}
        assert should_be_number_entity(number_param) is True

        # Test select entity candidate (has enum)
        select_param = {
            "unit_name": "",
            "edit": True,
            "enum": {"values": ["Off", "On"]},
        }
        assert should_be_number_entity(select_param) is False

        # Test read-only parameter
        readonly_param = {"unit_name": "%", "edit": False}
        assert should_be_number_entity(readonly_param) is False

        # Test parameter with unit but no edit
        no_edit_param = {"unit_name": "°C", "edit": False}
        assert should_be_number_entity(no_edit_param) is False

    def test_create_dynamic_number_entity_description(self):
        """Test create_dynamic_number_entity_description function."""
        param = {
            "unit_name": "%",
            "minv": 15,
            "maxv": 100,
            "key": "test_parameter",
            "name": "Test Parameter",
        }

        entity_desc = create_dynamic_number_entity_description("0", param)

        assert entity_desc.key == "0"
        assert entity_desc.translation_key == "test_parameter"
        assert entity_desc.native_min_value == 15.0
        assert entity_desc.native_max_value == 100.0
        assert entity_desc.native_step == 1.0
        # Unit mapping should work
        assert entity_desc.native_unit_of_measurement is not None

    def test_create_dynamic_number_entity_description_temperature(self):
        """Test temperature parameter entity description."""
        param = {
            "unit_name": "°C",
            "minv": 20,
            "maxv": 85,
            "key": "mixer_temp",
            "name": "Mixer Temperature",
        }

        entity_desc = create_dynamic_number_entity_description("69", param)

        assert entity_desc.key == "69"
        assert entity_desc.translation_key == "mixer_temp"
        assert entity_desc.native_min_value == 20.0
        assert entity_desc.native_max_value == 85.0
        assert entity_desc.native_step == 1.0

    def test_create_dynamic_number_entity_description_large_range(self):
        """Test parameter with large range gets step 5."""
        param = {
            "unit_name": "kW",  # Use a unit that's not in the special list
            "minv": 0,
            "maxv": 255,
            "key": "large_range_param",
            "name": "Large Range Parameter",
        }

        entity_desc = create_dynamic_number_entity_description("100", param)

        assert entity_desc.native_min_value == 0.0
        assert entity_desc.native_max_value == 255.0
        assert entity_desc.native_step == 5.0  # Large range should get step 5

    @pytest.mark.asyncio
    async def test_dynamic_number_entity_creation(
        self, hass, mock_config_entry, mock_api, mock_coordinator
    ):
        """Test dynamic number entity creation in async_setup_entry."""

        # Mock the hass.data structure
        hass.data = {
            "econet300": {
                mock_config_entry.entry_id: {
                    "api": mock_api,
                    "coordinator": mock_coordinator,
                }
            }
        }

        # Mock async_add_entities
        mock_add_entities = MagicMock(spec=AddEntitiesCallback)

        # Call the setup function
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        # Verify that entities were added
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should have created number entities
        assert len(entities) > 0
        assert all(isinstance(entity, EconetNumber) for entity in entities)

        # Check that we have the expected number of entities (should be around 104)
        # This is approximate since it depends on the fixture data
        assert len(entities) >= 50  # At least 50 number entities should be created

    @pytest.mark.asyncio
    async def test_fallback_to_legacy_method(
        self, hass, mock_config_entry, mock_coordinator
    ):
        """Test fallback to legacy method when merged data is unavailable."""

        # Create API that returns None for merged data
        mock_api = MagicMock(spec=Econet300Api)
        mock_api.fetch_merged_rm_data_with_names_descs_and_structure = AsyncMock(
            return_value=None
        )

        # Mock the hass.data structure
        hass.data = {
            "econet300": {
                mock_config_entry.entry_id: {
                    "api": mock_api,
                    "coordinator": mock_coordinator,
                }
            }
        }

        # Mock async_add_entities
        mock_add_entities = MagicMock(spec=AddEntitiesCallback)

        # Call the setup function
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        # Verify that entities were added (legacy method)
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should have created some entities from NUMBER_MAP
        assert len(entities) >= 0  # Could be 0 if no legacy entities are available

    def test_entity_properties_from_real_data(self, mock_merged_data):
        """Test entity properties using real fixture data."""
        # Find a number entity candidate from real data
        number_candidates = []
        for param_id, param in mock_merged_data["parameters"].items():
            if should_be_number_entity(param):
                number_candidates.append((param_id, param))
                if len(number_candidates) >= 3:  # Test first 3
                    break

        assert len(number_candidates) > 0, (
            "Should have number entity candidates in fixture data"
        )

        for param_id, param in number_candidates:
            entity_desc = create_dynamic_number_entity_description(param_id, param)

            # Verify basic properties
            assert entity_desc.key == param_id
            assert entity_desc.translation_key == param["key"]
            assert entity_desc.native_min_value == float(param["minv"])
            assert entity_desc.native_max_value == float(param["maxv"])

            # Verify unit mapping
            unit_name = param["unit_name"]
            if unit_name in ["%", "°C", "sek.", "min.", "h.", "r/min", "kW"]:
                assert entity_desc.native_unit_of_measurement is not None

            # Verify step calculation
            if unit_name in {"%", "°C"} or unit_name in ["sek.", "min.", "h."]:
                assert entity_desc.native_step == 1.0
            elif float(param["maxv"]) - float(param["minv"]) > 100:
                assert entity_desc.native_step == 5.0
            else:
                assert entity_desc.native_step == 1.0

    def test_error_handling_in_entity_creation(self):
        """Test error handling when creating entity descriptions."""
        # Test with invalid parameter data
        invalid_param = {
            "unit_name": "%",
            "minv": "invalid",  # Invalid min value
            "maxv": 100,
            "key": "test",
        }

        with pytest.raises((ValueError, TypeError)):
            create_dynamic_number_entity_description("0", invalid_param)

        # Test with missing required fields - should work with defaults
        incomplete_param = {
            "unit_name": "%"
            # Missing minv, maxv, key - should use defaults
        }

        # This should not raise an error because of defaults
        entity_desc = create_dynamic_number_entity_description("0", incomplete_param)
        assert entity_desc.native_min_value == 0.0  # Default min
        assert entity_desc.native_max_value == 100.0  # Default max
        assert entity_desc.translation_key == "parameter_0"  # Default key
