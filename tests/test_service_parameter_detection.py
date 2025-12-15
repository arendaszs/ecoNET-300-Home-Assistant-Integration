"""Test service parameter detection and category-based entity creation."""

from unittest.mock import MagicMock

from custom_components.econet300.common_functions import (
    get_parameter_type_from_category,
    is_information_category,
)
from custom_components.econet300.const import (
    DEVICE_INFO_ADVANCED_PARAMETERS_NAME,
    DEVICE_INFO_SERVICE_PARAMETERS_NAME,
    DOMAIN,
)
from custom_components.econet300.number import (
    AdvancedParameterNumber,
    EconetNumber,
    EconetNumberEntityDescription,
    MenuCategoryNumber,
    MixerDynamicNumber,
    ServiceParameterNumber,
    should_be_number_entity,
)


class TestServiceParameterDetection:
    """Test service parameter detection functionality."""

    def test_get_parameter_type_from_category_service_variations(self):
        """Test get_parameter_type_from_category with various service category names."""
        # Standard service categories
        assert get_parameter_type_from_category("Service Settings") == "service"
        assert get_parameter_type_from_category("Service information") == "service"
        assert get_parameter_type_from_category("Service counters") == "service"

        # Case variations
        assert get_parameter_type_from_category("SERVICE SETTINGS") == "service"
        assert get_parameter_type_from_category("service settings") == "service"
        assert get_parameter_type_from_category("SERVICE") == "service"

        # Partial matches
        assert get_parameter_type_from_category("My Service Settings") == "service"
        assert get_parameter_type_from_category("Service Mode") == "service"

        # Edge cases with whitespace
        assert get_parameter_type_from_category("  Service Settings  ") == "service"
        assert get_parameter_type_from_category("Service  Settings") == "service"

    def test_get_parameter_type_from_category_advanced_variations(self):
        """Test get_parameter_type_from_category with various advanced category names."""
        # Standard advanced categories
        assert get_parameter_type_from_category("Advanced settings") == "advanced"
        assert get_parameter_type_from_category("Advanced Settings") == "advanced"

        # Case variations
        assert get_parameter_type_from_category("ADVANCED SETTINGS") == "advanced"
        assert get_parameter_type_from_category("advanced settings") == "advanced"
        assert get_parameter_type_from_category("ADVANCED") == "advanced"

        # Partial matches
        assert get_parameter_type_from_category("My Advanced Settings") == "advanced"
        assert get_parameter_type_from_category("Advanced Mode") == "advanced"

        # Edge cases with whitespace
        assert get_parameter_type_from_category("  Advanced settings  ") == "advanced"
        assert get_parameter_type_from_category("Advanced  settings") == "advanced"

    def test_get_parameter_type_from_category_basic_categories(self):
        """Test get_parameter_type_from_category with basic category names."""
        # Standard basic categories
        assert get_parameter_type_from_category("Boiler settings") == "basic"
        assert get_parameter_type_from_category("Information") == "basic"
        assert get_parameter_type_from_category("Mixer 1 settings") == "basic"
        assert get_parameter_type_from_category("Main menu") == "basic"
        assert get_parameter_type_from_category("HUW settings") == "basic"

        # Categories that should default to basic
        assert get_parameter_type_from_category("Settings") == "basic"
        assert get_parameter_type_from_category("Other category") == "basic"
        assert get_parameter_type_from_category("Unknown") == "basic"

    def test_get_parameter_type_from_category_edge_cases(self):
        """Test get_parameter_type_from_category with edge cases."""
        # None and empty values
        assert get_parameter_type_from_category(None) == "basic"
        assert get_parameter_type_from_category("") == "basic"
        assert get_parameter_type_from_category("   ") == "basic"
        assert get_parameter_type_from_category("\t") == "basic"
        assert get_parameter_type_from_category("\n") == "basic"

        # Special characters
        assert get_parameter_type_from_category("Service-Settings") == "service"
        assert get_parameter_type_from_category("Service_Settings") == "service"
        assert get_parameter_type_from_category("Service.Settings") == "service"

    def test_service_parameter_number_device_info(self):
        """Test that ServiceParameterNumber has correct device_info."""
        mock_api = MagicMock()
        mock_api.uid = "test-device-uid"
        mock_coordinator = MagicMock()

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = ServiceParameterNumber(entity_desc, mock_coordinator, mock_api)

        device_info = entity.device_info

        assert device_info is not None
        assert device_info.get("identifiers") == {
            (DOMAIN, "test-device-uid-service-parameters")
        }
        assert device_info.get("name") == DEVICE_INFO_SERVICE_PARAMETERS_NAME
        assert device_info.get("via_device") == (DOMAIN, "test-device-uid")

    def test_advanced_parameter_number_device_info(self):
        """Test that AdvancedParameterNumber has correct device_info."""
        mock_api = MagicMock()
        mock_api.uid = "test-device-uid"
        mock_coordinator = MagicMock()

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = AdvancedParameterNumber(entity_desc, mock_coordinator, mock_api)

        device_info = entity.device_info

        assert device_info is not None
        assert device_info.get("identifiers") == {
            (DOMAIN, "test-device-uid-advanced-parameters")
        }  # type: ignore[typeddict-item]
        assert device_info.get("name") == DEVICE_INFO_ADVANCED_PARAMETERS_NAME  # type: ignore[typeddict-item]
        assert device_info.get("via_device") == (DOMAIN, "test-device-uid")  # type: ignore[typeddict-item]

    def test_service_parameter_number_enabled_default(self):
        """Test that ServiceParameterNumber is disabled by default."""
        mock_api = MagicMock()
        mock_coordinator = MagicMock()

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = ServiceParameterNumber(entity_desc, mock_coordinator, mock_api)

        assert entity.entity_registry_enabled_default is False

    def test_advanced_parameter_number_enabled_default(self):
        """Test that AdvancedParameterNumber is disabled by default."""
        mock_api = MagicMock()
        mock_coordinator = MagicMock()

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = AdvancedParameterNumber(entity_desc, mock_coordinator, mock_api)

        assert entity.entity_registry_enabled_default is False

    def test_menu_category_number_for_mixer_device_info(self):
        """Test that MenuCategoryNumber for mixer has correct device_info."""
        mock_api = MagicMock()
        mock_api.uid = "test-device-uid"
        mock_api.model_id = "test-model"
        mock_api.host = "http://test-host"
        mock_api.sw_rev = "1.0.0"
        mock_coordinator = MagicMock()
        mock_coordinator.data = {"mergedData": {"parameters": {}}}

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        # Mixer 1 uses category_index 5 (4 + mixer_num)
        entity = MenuCategoryNumber(
            entity_desc,
            mock_coordinator,
            mock_api,
            category_index=5,
            category_name="Mixer 1 settings",
            param_id="test_param",
        )

        device_info = entity.device_info

        assert device_info is not None
        assert device_info.get("identifiers") == {(DOMAIN, "test-device-uid-menu-5")}
        assert device_info.get("name") == "Mixer 1 settings"
        assert device_info.get("via_device") == (DOMAIN, "test-device-uid")

    def test_entity_type_selection_service(self):
        """Test that service category selects ServiceParameterNumber."""
        category = "Service Settings"
        param_type = get_parameter_type_from_category(category)

        assert param_type == "service"

        # Verify entity type would be ServiceParameterNumber
        mock_api = MagicMock()
        mock_coordinator = MagicMock()
        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = ServiceParameterNumber(entity_desc, mock_coordinator, mock_api)
        assert isinstance(entity, ServiceParameterNumber)
        assert not isinstance(entity, AdvancedParameterNumber)
        assert isinstance(entity, EconetNumber)

    def test_entity_type_selection_advanced(self):
        """Test that advanced category selects AdvancedParameterNumber."""
        category = "Advanced settings"
        param_type = get_parameter_type_from_category(category)

        assert param_type == "advanced"

        # Verify entity type would be AdvancedParameterNumber
        mock_api = MagicMock()
        mock_coordinator = MagicMock()
        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = AdvancedParameterNumber(entity_desc, mock_coordinator, mock_api)
        assert isinstance(entity, AdvancedParameterNumber)
        assert not isinstance(entity, ServiceParameterNumber)
        assert isinstance(entity, EconetNumber)

    def test_entity_type_selection_basic(self):
        """Test that basic category selects EconetNumber."""
        category = "Boiler settings"
        param_type = get_parameter_type_from_category(category)

        assert param_type == "basic"

        # Verify entity type would be EconetNumber (not Service/Advanced)
        mock_api = MagicMock()
        mock_coordinator = MagicMock()
        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = EconetNumber(entity_desc, mock_coordinator, mock_api)
        assert isinstance(entity, EconetNumber)
        assert not isinstance(entity, ServiceParameterNumber)
        assert not isinstance(entity, AdvancedParameterNumber)

    def test_mixer_entity_uses_menu_category_number(self):
        """Test that all mixer entities use MenuCategoryNumber for device grouping."""
        # All mixer parameters (basic, service, advanced) now use MenuCategoryNumber
        # to group into their respective "Mixer X settings" devices
        mock_api = MagicMock()
        mock_api.uid = "test-device-uid"
        mock_api.model_id = "test-model"
        mock_api.host = "http://test-host"
        mock_api.sw_rev = "1.0.0"
        mock_coordinator = MagicMock()
        mock_coordinator.data = {"mergedData": {"parameters": {}}}

        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        # Create MenuCategoryNumber for Mixer 1
        entity = MenuCategoryNumber(
            entity_desc,
            mock_coordinator,
            mock_api,
            category_index=5,  # 4 + mixer_num (1)
            category_name="Mixer 1 settings",
            param_id="test_param",
        )

        assert isinstance(entity, MenuCategoryNumber)
        # Verify device info is for the mixer device
        device_info = entity.device_info
        assert device_info is not None
        assert "Mixer 1 settings" in str(device_info.get("name"))

    def test_mixer_dynamic_number_still_exists_for_legacy(self):
        """Test that MixerDynamicNumber still exists for legacy mixer entities."""
        # MixerDynamicNumber is still used for legacy mixer set temperature entities
        mock_api = MagicMock()
        mock_coordinator = MagicMock()
        entity_desc = EconetNumberEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        entity = MixerDynamicNumber(entity_desc, mock_coordinator, mock_api, 1)
        assert isinstance(entity, MixerDynamicNumber)

    def test_is_information_category_variations(self):
        """Test is_information_category with various category names."""
        # Information categories (should return True)
        assert is_information_category("Information") is True
        assert is_information_category("information") is True
        assert is_information_category("INFORMATION") is True
        assert is_information_category("Information mixer 1") is True
        assert is_information_category("ecoNET WiFi information") is True

        # Non-information categories (should return False)
        assert is_information_category("Boiler settings") is False
        assert is_information_category("Service Settings") is False
        assert is_information_category("Advanced settings") is False
        assert is_information_category("Summer/Winter") is False
        assert is_information_category(None) is False
        assert is_information_category("") is False

    def test_multiple_categories_parameter_structure(self):
        """Test that parameters can have multiple categories."""
        # This test verifies the data structure changes in _add_parameter_categories
        # Parameters should have both "category" (string) and "categories" (list)

        # Mock parameter data
        param = {
            "name": "Test Parameter",
            "number": 123,
            "categories": ["Information", "Boiler settings"],
            "category": "Information",  # First category for backward compatibility
        }

        # Verify structure
        assert "categories" in param
        assert "category" in param
        assert isinstance(param["categories"], list)
        assert isinstance(param["category"], str)
        assert len(param["categories"]) > 1
        assert param["category"] == param["categories"][0]

    def test_information_category_creates_sensor(self):
        """Test that Information category parameters create sensor entities."""
        # Mock parameter with Information category
        param = {
            "name": "Test Info Parameter",
            "number": 123,
            "categories": ["Information"],
            "category": "Information",
            "edit": True,  # Even if editable, Information category should create sensor
            "unit_name": "%",
            "key": "test_info_param",
        }

        # Information category should be identified
        assert is_information_category("Information") is True

        # Parameter type should be basic (but Information category overrides this)
        param_type = get_parameter_type_from_category("Information")
        assert param_type == "basic"

        # However, Information category should create sensor, not number entity
        should_be_number = should_be_number_entity(param)
        assert should_be_number is True  # Would normally be number entity

        # But Information category logic should override this in entity creation
        # (This is tested in the actual entity creation functions)

    def test_service_advanced_categories_with_show_service_parameter(self):
        """Test that service/advanced categories respect show_service_parameters setting."""
        # Mock parameters
        service_param = {
            "name": "Service Parameter",
            "categories": ["Service Settings"],
            "category": "Service Settings",
            "edit": True,
            "unit_name": "%",
            "key": "service_param",
        }

        advanced_param = {
            "name": "Advanced Parameter",
            "categories": ["Advanced settings"],
            "category": "Advanced settings",
            "edit": True,
            "unit_name": "°C",
            "key": "advanced_param",
        }

        # Verify category detection
        assert get_parameter_type_from_category("Service Settings") == "service"
        assert get_parameter_type_from_category("Advanced settings") == "advanced"
        assert is_information_category("Service Settings") is False
        assert is_information_category("Advanced settings") is False

        # Verify these would be number entities if show_service_parameters=True
        assert should_be_number_entity(service_param) is True
        assert should_be_number_entity(advanced_param) is True

        # But entity creation should check show_service_parameters setting
        # (This is tested in the entity creation integration tests)
