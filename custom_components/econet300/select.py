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
from .common_functions import camel_to_snake
from .const import (
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


# Function removed - category support eliminated


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

    # Dynamic select entities removed - category support eliminated

    _LOGGER.info("Adding %d total select entities", len(entities))
    async_add_entities(entities)
