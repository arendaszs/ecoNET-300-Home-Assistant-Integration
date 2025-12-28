"""Select entities for ecoNET300 integration.

This module implements select entities for the ecoNET300 integration.
Uses Home Assistant icon translation system via icons.json.
"""

import logging
import re
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Econet300Api
from .common import EconetDataCoordinator
from .common_functions import camel_to_snake, mixer_exists
from .const import (
    DEVICE_INFO_MANUFACTURER,
    DEVICE_INFO_MODEL,
    DOMAIN,
    SELECT_KEY_GET_INDEX,
    SELECT_KEY_POST_INDEX,
    SELECT_KEY_VALUES,
    SERVICE_API,
    SERVICE_COORDINATOR,
)
from .entity import EconetEntity

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


class EconetDynamicSelect(SelectEntity):
    """Represents a dynamic ecoNET select entity from mergedData."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entity_description: SelectEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        param_id: str,
        param: dict,
    ):
        """Initialize a new dynamic ecoNET select entity."""
        self.entity_description = entity_description
        self.coordinator = coordinator
        self.api = api
        self._param_id = param_id
        self._param = param
        self._attr_current_option = None

        # Get enum values
        enum_data = param.get("enum", {})
        self._enum_values = enum_data.get("values", [])
        self._first_index = enum_data.get("first", 0)

        # Set unique ID
        self._attr_unique_id = f"econet300_select_{param_id}"

        # Set initial state
        self._update_state_from_param()

    @property
    def options(self) -> list[str]:
        """Return the available options."""
        return [v for v in self._enum_values if v]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api.uid)},
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            name=self.api.uid,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        if self._is_parameter_locked():
            return "mdi:lock"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "param_id": self._param_id,
            "options": self._enum_values,
        }
        if self._is_parameter_locked():
            attrs["locked"] = True
            lock_reason = self._get_lock_reason()
            if lock_reason:
                attrs["lock_reason"] = lock_reason
        return attrs

    def _update_state_from_param(self) -> None:
        """Update state from parameter value."""
        if self.coordinator.data is None:
            return

        merged_data = self.coordinator.data.get("mergedData")
        if not merged_data:
            return

        parameters = merged_data.get("parameters", {})
        param_data = parameters.get(self._param_id)
        if param_data:
            value = param_data.get("value")
            if value is not None:
                # Convert numeric value to option string
                index = int(value) - self._first_index
                if 0 <= index < len(self._enum_values):
                    self._attr_current_option = self._enum_values[index]

    def _is_parameter_locked(self) -> bool:
        """Check if the parameter is locked."""
        if self.coordinator.data is None:
            return False

        merged_data = self.coordinator.data.get("mergedData")
        if not merged_data:
            return False

        parameters = merged_data.get("parameters", {})
        param_data = parameters.get(self._param_id)
        if param_data:
            return param_data.get("locked", False)
        return False

    def _get_lock_reason(self) -> str | None:
        """Get the lock reason for this parameter."""
        if self.coordinator.data is None:
            return None

        merged_data = self.coordinator.data.get("mergedData")
        if not merged_data:
            return None

        parameters = merged_data.get("parameters", {})
        param_data = parameters.get(self._param_id)
        if param_data:
            return param_data.get("lock_reason")
        return None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        self._update_state_from_param()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        self._update_state_from_param()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self._is_parameter_locked():
            lock_reason = self._get_lock_reason() or "Parameter is locked"
            _LOGGER.warning(
                "Cannot change locked select %s: %s",
                self.entity_description.key,
                lock_reason,
            )
            self._raise_select_error(f"Select is locked: {lock_reason}")

        try:
            # Convert option to numeric value
            if option in self._enum_values:
                value = self._enum_values.index(option) + self._first_index
            else:
                self._raise_select_error(f"Invalid option: {option}")

            success = await self.api.set_param(self._param_id, value)
            if success:
                self._attr_current_option = option
                self.async_write_ha_state()
                _LOGGER.info(
                    "Select %s changed to %s",
                    self.entity_description.key,
                    option,
                )
            else:
                self._raise_select_error(
                    f"Failed to set {self.entity_description.name}"
                )
        except HomeAssistantError:
            raise
        except Exception as e:
            _LOGGER.error(
                "Failed to change select %s: %s", self.entity_description.key, e
            )
            raise HomeAssistantError(f"Failed to change select: {e}") from e

    @staticmethod
    def _raise_select_error(message: str) -> None:
        """Raise a HomeAssistantError with the given message."""
        raise HomeAssistantError(message)


def should_be_select_entity(param: dict) -> bool:
    """Check if a parameter should be a select entity.

    Select entities are parameters with 3+ enum values,
    or 2 values that are NOT On/Off type.
    """
    if "enum" not in param:
        return False

    enum_data = param.get("enum", {})
    values = enum_data.get("values", [])

    # Filter out empty values
    non_empty_values = [v for v in values if v]

    # Must have at least 2 options
    if len(non_empty_values) < 2:
        return False

    # If 3+ options, it's definitely a select
    if len(non_empty_values) >= 3:
        return True

    # If exactly 2 options, check if NOT On/Off type (those are switches)
    if len(non_empty_values) == 2:
        values_upper = [v.upper() for v in non_empty_values]
        on_off_patterns = [
            {"OFF", "ON"},
            {"0", "1"},
            {"FALSE", "TRUE"},
            {"NO", "YES"},
            {"DISABLED", "ENABLED"},
        ]

        for pattern in on_off_patterns:
            if set(values_upper) == pattern:
                return False  # It's a switch, not a select

        # Check for empty + something pattern (calibration toggle = switch)
        if values[0] == "" and values[1]:
            return False

        # 2 options that are not On/Off = select
        return True

    return False


def create_dynamic_selects(
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
) -> list[SelectEntity]:
    """Create dynamic select entities from mergedData."""
    entities: list[SelectEntity] = []

    if coordinator.data is None:
        _LOGGER.debug("No coordinator data for dynamic selects")
        return entities

    merged_data = coordinator.data.get("mergedData")
    if not merged_data:
        _LOGGER.debug("No mergedData for dynamic selects")
        return entities

    parameters = merged_data.get("parameters", {})
    _LOGGER.debug("Creating dynamic selects from %d parameters", len(parameters))

    for param_id, param in parameters.items():
        if not should_be_select_entity(param):
            continue

        # Check for mixer-related entities and skip non-existent mixers
        param_name = param.get("name", f"Parameter {param_id}")
        param_key = param.get("key", f"param_{param_id}")

        # Check if mixer-related and if mixer exists
        if "mixer" in param_name.lower() or "mixer" in param_key.lower():
            mixer_match = re.search(r"mixer\s*(\d+)", param_name.lower())
            if mixer_match:
                mixer_num = int(mixer_match.group(1))
                if not mixer_exists(coordinator.data, mixer_num):
                    _LOGGER.debug(
                        "Skipping select %s - mixer %d not connected",
                        param_name,
                        mixer_num,
                    )
                    continue

        # Create entity key
        entity_key = param.get("key") or camel_to_snake(param_name)

        entity_description = SelectEntityDescription(
            key=entity_key,
            name=param_name,
            translation_key=entity_key,
        )

        entity = EconetDynamicSelect(
            entity_description,
            coordinator,
            api,
            param_id,
            param,
        )

        entities.append(entity)
        _LOGGER.debug(
            "Created dynamic select: %s (param_id=%s, values=%s)",
            param_name,
            param_id,
            param.get("enum", {}).get("values", []),
        )

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
    _LOGGER.info("Created %d dynamic select entities", len(dynamic_selects))

    _LOGGER.info("Adding %d total select entities", len(entities))
    async_add_entities(entities)
