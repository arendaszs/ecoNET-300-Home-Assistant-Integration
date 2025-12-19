"""Select entities for ecoNET300 integration.

This module implements select entities for the ecoNET300 integration.
Uses Home Assistant icon translation system via icons.json.
"""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Econet300Api
from .common import EconetDataCoordinator
from .common_functions import (
    camel_to_snake,
    extract_device_group_from_name,
    generate_translation_key,
    get_lock_reason,
    get_parameter_type_from_category,
    is_information_category,
    is_parameter_locked,
    mixer_exists,
    should_be_select_entity,
    validate_parameter_data,
)
from .const import (
    DOMAIN,
    SELECT_KEY_GET_INDEX,
    SELECT_KEY_POST_INDEX,
    SELECT_KEY_VALUES,
    SERVICE_API,
    SERVICE_COORDINATOR,
)
from .entity import EconetEntity, MenuCategoryEntity

_LOGGER = logging.getLogger(__name__)


class HeaterModeSelectError(HomeAssistantError):
    """Raised when heater mode selection fails."""


class EconetSelect(EconetEntity, SelectEntity):
    """Represents an ecoNET select entity."""

    entity_description: SelectEntityDescription
    select_key: str

    def __init__(
        self,
        entity_description: SelectEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        select_key: str,
    ):
        """Initialize a new ecoNET select entity."""
        self.entity_description = entity_description
        self.api = api
        self.select_key = select_key
        self._attr_current_option = None
        super().__init__(coordinator, api)

    @property
    def options(self) -> list[str]:
        """Return the available options with proper display names."""
        # Use original camelCase key for dictionary lookup
        values_dict = SELECT_KEY_VALUES.get(self.select_key, {})
        # Return properly formatted display names for better user experience
        return [value.title() for value in values_dict.values()]

    @property
    def icon(self) -> str | None:
        """Return the icon for the entity.

        Home Assistant will automatically handle icon translations using:
        - entity.select.{translation_key} in icons.json
        - State-specific icons based on current_option
        """
        # Let Home Assistant handle icon translations via icons.json
        # The icon will be automatically selected based on the current_option
        return None

    @property
    def current_option(self) -> str | None:
        """Return the current option with proper display name."""
        if self._attr_current_option:
            return self._attr_current_option.title()
        return None

    def _sync_state(self, value: str | None) -> None:
        """Synchronize the state of the select entity."""
        _LOGGER.debug("🔄 _sync_state called with value: %s", value)
        # Store the internal lowercase value for icon matching
        self._attr_current_option = value
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        current_option = self._attr_current_option
        heater_mode_value = (
            get_heater_mode_value(current_option) if current_option else None
        )

        # Get current state from regParamsData if available
        current_state_value = None
        if self.coordinator.data is not None:
            reg_params_data = self.coordinator.data.get("regParamsData", {})
            current_state_value = reg_params_data.get(
                SELECT_KEY_GET_INDEX[self.select_key]
            )

        values_dict = SELECT_KEY_VALUES.get(self.select_key, {})
        return {
            "heater_mode_value": heater_mode_value,
            "current_state_value": current_state_value,
            "available_options": list(values_dict.values()),
            "setting_parameter": SELECT_KEY_POST_INDEX.get(self.select_key, "unknown"),
            "current_state_parameter": SELECT_KEY_GET_INDEX.get(
                self.select_key, "unknown"
            ),
        }

    async def async_added_to_hass(self):
        """Handle added to hass - override to check regParamsData for heater_mode."""
        _LOGGER.debug(
            "🏠 async_added_to_hass called for: %s", self.entity_description.key
        )

        if self.entity_description.key == "heater_mode":
            _LOGGER.debug("🔥 Processing heater_mode in async_added_to_hass")
            # For heater mode, get current state from regParamsData parameter 2049
            if self.coordinator.data is not None:
                reg_params_data = self.coordinator.data.get("regParamsData")
                if reg_params_data is None:
                    reg_params_data = {}

                heater_mode_value = reg_params_data.get(
                    SELECT_KEY_GET_INDEX.get(self.select_key, "unknown")
                )
                _LOGGER.debug(
                    "🎯 Heater mode current state (2049): %s (type: %s)",
                    heater_mode_value,
                    type(heater_mode_value),
                )

                if heater_mode_value is not None:
                    values_dict = SELECT_KEY_VALUES.get(self.select_key, {})
                    if heater_mode_value in values_dict:
                        current_option = values_dict[heater_mode_value]
                        _LOGGER.debug("✅ Found valid heater mode: %s", current_option)
                        self._attr_available = True
                        self._sync_state(current_option)
                    else:
                        _LOGGER.warning(
                            "❌ Unknown heater mode value: %s (valid values: %s)",
                            heater_mode_value,
                            list(values_dict.keys()),
                        )
                        self._attr_available = False
                        self._sync_state(None)
                else:
                    _LOGGER.debug("❌ No heater mode current state found")
                    self._attr_available = False
                    self._sync_state(None)
            else:
                _LOGGER.debug("❌ Coordinator data is None")
                self._attr_available = False
                self._sync_state(None)
        else:
            # For other entities, use standard logic
            _LOGGER.debug(
                "🔄 Using standard logic for: %s", self.entity_description.key
            )
            await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "🔄 _handle_coordinator_update called for: %s", self.entity_description.key
        )

        if self.coordinator.data is None:
            _LOGGER.debug("❌ Coordinator data is None")
            return

        # For heater mode, get current state from regParamsData parameter 2049
        if self.entity_description.key == "heater_mode":
            _LOGGER.debug("🔥 Processing heater_mode in _handle_coordinator_update")
            reg_params_data = self.coordinator.data.get("regParamsData", {})

            heater_mode_value = reg_params_data.get(
                SELECT_KEY_GET_INDEX.get(self.select_key, "unknown")
            )
            _LOGGER.debug(
                "🎯 Heater mode current state (2049): %s (type: %s)",
                heater_mode_value,
                type(heater_mode_value),
            )

            if heater_mode_value is not None:
                # Map numeric value to option name
                values_dict = SELECT_KEY_VALUES.get(self.select_key, {})
                if heater_mode_value in values_dict:
                    current_option = values_dict[heater_mode_value]
                    _LOGGER.debug("✅ Found valid heater mode: %s", current_option)
                    self._attr_available = True
                    self._sync_state(current_option)
                else:
                    _LOGGER.warning(
                        "❌ Unknown heater mode value: %s (valid values: %s)",
                        heater_mode_value,
                        list(values_dict.keys()),
                    )
                    self._attr_available = False
                    self._sync_state(None)
            else:
                _LOGGER.debug("❌ No heater mode current state found")
                self._attr_available = False
                self._sync_state(None)
        else:
            # For other entities, use standard logic
            _LOGGER.debug(
                "🔄 Using standard logic for: %s", self.entity_description.key
            )
            super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.debug("🎯 async_select_option called with option: %s", option)
        try:
            # Convert display name back to internal lowercase value for lookup
            internal_option = option.lower()
            _LOGGER.debug(
                "🔄 Converted display name '%s' to internal value: %s",
                option,
                internal_option,
            )

            # Get the numeric value for the selected option
            value = get_heater_mode_value(internal_option)
            _LOGGER.debug(
                "🔢 Converted option '%s' to value: %s", internal_option, value
            )

            if value is None:
                _LOGGER.error("❌ Invalid option: %s", option)
                self._raise_heater_mode_error(f"Invalid option: {option}")

            # Use the parameter index to set the value
            param_index = SELECT_KEY_POST_INDEX.get(self.select_key, "unknown")
            _LOGGER.debug(
                "📡 Calling API to set parameter %s to value %s",
                param_index,
                value,
            )
            success = await self.api.set_param(param_index, value)
            _LOGGER.debug("📡 API call result: %s", success)

            if success:
                # Update the current option (store internal lowercase value)
                old_option = self._attr_current_option
                _LOGGER.debug(
                    "🔄 Updating from '%s' to '%s'", old_option, internal_option
                )

                self._attr_current_option = internal_option
                self._attr_available = True

                # Log the change with context for better logbook entries
                _LOGGER.info(
                    "Heater mode changed from '%s' to '%s' (API value: %d)",
                    old_option or "unknown",
                    option,  # Display the user-friendly name in logs
                    value,
                )

                # Write the state change to trigger Home Assistant's state change logging
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Failed to change heater mode to %s - API returned failure", option
                )
                self._raise_heater_mode_error(
                    f"Failed to change heater mode to {option}"
                )

        except Exception as e:
            _LOGGER.error("Failed to change heater mode to %s: %s", option, e)
            raise HeaterModeSelectError(
                f"Failed to change heater mode to {option}"
            ) from e

    @staticmethod
    def _raise_heater_mode_error(message: str) -> None:
        """Raise a HeaterModeSelectError with the given message."""
        raise HeaterModeSelectError(message)


class MenuCategorySelectError(HomeAssistantError):
    """Raised when menu category select operation fails."""


class MenuCategorySelect(MenuCategoryEntity, SelectEntity):  # type: ignore[misc]
    """Dynamic select entity grouped by menu category.

    This entity type creates select entities from parameters with enum data
    (3+ values), grouped into Home Assistant devices based on the ecoNET
    controller menu structure or name-based heuristics.

    Note: type: ignore[misc] is used because of entity_description type
    conflict between MenuCategoryEntity and SelectEntity base classes.
    """

    entity_description: SelectEntityDescription

    def __init__(
        self,
        entity_description: SelectEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        category_index: int,
        category_name: str,
        param_id: str,
        param_number: int,
        enum_values: list[str],
        enum_first: int = 0,
    ):
        """Initialize a new MenuCategorySelect entity.

        Args:
            entity_description: Entity description with key, name, etc.
            coordinator: Data coordinator for updates
            api: API instance for device info and API calls
            category_index: Index into rmCatsNames array
            category_name: Human-readable category name
            param_id: Parameter ID for value lookup in merged data
            param_number: Parameter number for API set_param calls
            enum_values: List of option strings from enum data
            enum_first: First value offset for enum (default 0)

        """
        super().__init__(
            entity_description, coordinator, api, category_index, category_name
        )
        self._param_id = param_id
        self._param_number = param_number
        self._enum_values = enum_values
        self._enum_first = enum_first
        self._attr_current_option: str | None = None
        # Lock state tracking
        self._locked: bool = False
        self._lock_reason: str | None = None

    @property
    def options(self) -> list[str]:
        """Return the available options."""
        return [opt.title() for opt in self._enum_values]

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if self._attr_current_option:
            return self._attr_current_option.title()
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            return

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return

        merged_parameters = merged_data.get("parameters", {})
        param_data = merged_parameters.get(self._param_id)

        if param_data and isinstance(param_data, dict):
            value = param_data.get("value")
            if value is not None:
                self._update_from_value(value)

            # Update lock state
            self._locked = param_data.get("locked", False)
            self._lock_reason = param_data.get("lock_reason")

            self.async_write_ha_state()

    def _update_from_value(self, value: int) -> None:
        """Update current option from numeric value."""
        # Convert API value to option index
        option_index = value - self._enum_first
        if 0 <= option_index < len(self._enum_values):
            self._attr_current_option = self._enum_values[option_index]
            self._attr_available = True
        else:
            _LOGGER.warning(
                "Invalid value %d for %s (valid range: %d-%d)",
                value,
                self.entity_description.key,
                self._enum_first,
                self._enum_first + len(self._enum_values) - 1,
            )
            self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        # Initialize value from coordinator data
        if self.coordinator.data is None:
            return

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return

        merged_parameters = merged_data.get("parameters", {})
        param_data = merged_parameters.get(self._param_id)

        if param_data and isinstance(param_data, dict):
            value = param_data.get("value")
            if value is not None:
                self._update_from_value(value)

            # Initialize lock state
            self._locked = param_data.get("locked", False)
            self._lock_reason = param_data.get("lock_reason")

            _LOGGER.debug(
                "Initialized MenuCategorySelect %s with option %s (locked=%s)",
                self.entity_description.key,
                self._attr_current_option,
                self._locked,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including lock information."""
        attrs: dict[str, Any] = {}
        if self._locked:
            attrs["locked"] = True
            if self._lock_reason:
                attrs["lock_reason"] = self._lock_reason
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available (not locked).

        When a parameter is locked by the device (e.g., "Weather control enabled"),
        the entity becomes unavailable in Home Assistant, preventing user interaction.
        """
        # Base availability check (coordinator connected, etc.)
        if not super().available:
            return False
        # Check if parameter is locked
        return not self._locked

    @staticmethod
    def _raise_select_error(message: str) -> None:
        """Raise a MenuCategorySelectError with the given message."""
        raise MenuCategorySelectError(message)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Check if parameter is locked
        if self._locked:
            reason = self._lock_reason or "Parameter is locked"
            _LOGGER.warning(
                "Cannot change option for %s: %s",
                self.entity_description.key,
                reason,
            )
            raise HomeAssistantError(f"Cannot change option: {reason}")

        try:
            # Find the option index (case-insensitive match)
            option_lower = option.lower()
            option_index = None

            for i, enum_opt in enumerate(self._enum_values):
                if enum_opt.lower() == option_lower:
                    option_index = i
                    break

            if option_index is None:
                self._raise_select_error(f"Invalid option: {option}")
                return  # Unreachable but helps type checker

            # Calculate API value
            api_value = self._enum_first + option_index

            _LOGGER.debug(
                "Setting %s to option '%s' (param %d = value %d)",
                self.entity_description.key,
                option,
                self._param_number,
                api_value,
            )

            success = await self.api.set_param(str(self._param_number), api_value)

            if success:
                old_option = self._attr_current_option
                self._attr_current_option = self._enum_values[option_index]
                self._attr_available = True
                self.async_write_ha_state()

                _LOGGER.info(
                    "%s changed from '%s' to '%s'",
                    self.entity_description.key,
                    old_option or "unknown",
                    option,
                )
            else:
                self._raise_select_error(f"API failed to set {option}")

        except MenuCategorySelectError:
            raise
        except Exception as e:
            _LOGGER.error(
                "Failed to set %s to %s: %s", self.entity_description.key, option, e
            )
            raise MenuCategorySelectError(f"Failed to set option: {e}") from e


def create_dynamic_selects(
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
) -> list[MenuCategorySelect]:
    """Create dynamic select entities from mergedData parameters with enum.

    Creates MenuCategorySelect entities for parameters that have enum data
    with 3 or more values and are editable.

    Args:
        coordinator: Data coordinator with mergedData
        api: API instance

    Returns:
        List of MenuCategorySelect entities

    """
    entities: list[MenuCategorySelect] = []

    if coordinator.data is None:
        return entities

    merged_data = coordinator.data.get("mergedData", {})
    if not merged_data or "parameters" not in merged_data:
        return entities

    parameters = merged_data.get("parameters", {})
    _LOGGER.debug("Checking %d parameters for select entities", len(parameters))

    # Track created keys to avoid duplicates
    created_keys: set[str] = set()

    for param_id, param in parameters.items():
        if not isinstance(param, dict):
            continue

        # Validate parameter data first
        is_valid, error_msg = validate_parameter_data(param)
        if not is_valid:
            _LOGGER.debug(
                "Skipping invalid select parameter %s: %s", param_id, error_msg
            )
            continue

        # Check if this should be a select entity (includes lock check)
        if not should_be_select_entity(param):
            continue

        # Log if parameter is locked (should not reach here due to should_be_select_entity)
        if is_parameter_locked(param):
            lock_reason = get_lock_reason(param) or "Parameter is locked"
            _LOGGER.debug(
                "Skipping locked select parameter %s (reason: %s)",
                param_id,
                lock_reason,
            )
            continue

        # Skip Information categories (read-only)
        categories = param.get("categories", [param.get("category", "")])
        if any(is_information_category(cat) for cat in categories):
            continue

        # Get enum data
        enum_data = param.get("enum", {})
        enum_values = enum_data.get("values", [])
        enum_first = enum_data.get("first", 0)

        # Skip if no valid enum
        if len(enum_values) < 3:
            continue

        # Get parameter info
        param_name = param.get("name", f"Select {param_id}")
        param_key = param.get("key", f"select_{param_id}")
        param_number = param.get("number")

        if param_number is None:
            continue

        # Avoid duplicates
        if param_key in created_keys:
            _LOGGER.debug("Skipping duplicate select key: %s", param_key)
            continue

        # Get device grouping from name-based heuristics or structure
        name_based_index, name_based_category = extract_device_group_from_name(
            param_name, for_information=False
        )

        if name_based_index is not None and name_based_category is not None:
            category_index = name_based_index
            category_name = name_based_category
        else:
            category_index = param.get("category_index", 0)
            category_name = param.get("category", "Settings")

        # Check if this is a mixer entity and if the mixer exists
        # Mixer settings are at indices 5-8 (4 + mixer_num)
        if 5 <= category_index <= 8:
            mixer_num = category_index - 4
            if not mixer_exists(coordinator.data, mixer_num):
                _LOGGER.debug(
                    "Skipping select '%s' - Mixer %d does not exist",
                    param_name,
                    mixer_num,
                )
                continue

        # Create entity description
        entity_description = SelectEntityDescription(
            key=param_key,
            name=param_name,
            translation_key=generate_translation_key(param_name),
        )

        # Create entity
        entity = MenuCategorySelect(
            entity_description=entity_description,
            coordinator=coordinator,
            api=api,
            category_index=category_index,
            category_name=category_name,
            param_id=param_id,
            param_number=param_number,
            enum_values=enum_values,
            enum_first=enum_first,
        )

        # Set disabled by default for service/advanced params
        param_type = get_parameter_type_from_category(category_name)
        if param_type in ("service", "advanced"):
            entity._attr_entity_registry_enabled_default = False  # noqa: SLF001

        entities.append(entity)
        created_keys.add(param_key)

        _LOGGER.debug(
            "Created dynamic select: %s (param %d) -> %s with %d options",
            param_name,
            param_number,
            category_name,
            len(enum_values),
        )

    _LOGGER.info("Created %d dynamic select entities", len(entities))
    return entities


def get_select_option_name(select_key: str, numeric_value: int) -> str | None:
    """Convert numeric value to option name for any select entity."""
    values_dict = SELECT_KEY_VALUES.get(select_key, {})
    return values_dict.get(numeric_value)


def get_select_option_value(select_key: str, option_name: str) -> int | None:
    """Convert option name to numeric value for any select entity."""
    values_dict = SELECT_KEY_VALUES.get(select_key, {})
    for value, name in values_dict.items():
        if name == option_name:
            return value
    return None


# Legacy functions for backward compatibility
def get_heater_mode_name(numeric_value: int) -> str | None:
    """Convert numeric heater mode value to option name."""
    return get_select_option_name("heaterMode", numeric_value)


def get_heater_mode_value(option_name: str) -> int | None:
    """Convert option name to numeric heater mode value for API."""
    return get_select_option_value("heaterMode", option_name)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    _LOGGER.debug("Setting up select platform for entry: %s", config_entry.entry_id)

    # Check if DOMAIN data exists
    if DOMAIN not in hass.data:
        _LOGGER.error("DOMAIN %s not found in hass.data", DOMAIN)
        return

    # Check if entry data exists
    if config_entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "Entry %s not found in hass.data[%s]", config_entry.entry_id, DOMAIN
        )
        return

    entry_data = hass.data[DOMAIN][config_entry.entry_id]

    # Check if required services exist
    if SERVICE_COORDINATOR not in entry_data:
        _LOGGER.error("SERVICE_COORDINATOR not found in entry data")
        return

    if SERVICE_API not in entry_data:
        _LOGGER.error("SERVICE_API not found in entry data")
        return

    coordinator = entry_data[SERVICE_COORDINATOR]
    api = entry_data[SERVICE_API]

    _LOGGER.debug("Successfully retrieved coordinator and API")

    # Create select entities based on available configurations
    entities: list[SelectEntity] = []

    # Create static select entities (heaterMode, etc.)
    for select_key in SELECT_KEY_POST_INDEX:
        _LOGGER.debug("Creating select entity: %s", select_key)
        # Convert camelCase to snake_case for entity key
        entity_key = camel_to_snake(select_key)

        entity_description = SelectEntityDescription(
            key=entity_key,
            translation_key=entity_key,
            # Icon will be handled by Home Assistant icon translations via icons.json
        )

        entity = EconetSelect(entity_description, coordinator, api, select_key)
        entities.append(entity)
        _LOGGER.debug("Created select entity: %s", select_key)

    _LOGGER.info("Created %d static select entities", len(entities))

    # Create dynamic select entities from mergedData
    dynamic_selects = create_dynamic_selects(coordinator, api)
    entities.extend(dynamic_selects)

    _LOGGER.info("Adding %d total select entities", len(entities))
    async_add_entities(entities)
