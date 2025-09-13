"""Select entities for ecoNET300 integration."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Econet300Api
from .common import EconetDataCoordinator
from .const import (
    DOMAIN,
    HEATER_MODE_CURRENT_STATE_PARAM,
    HEATER_MODE_PARAM_INDEX,
    HEATER_MODE_VALUES,
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

    def __init__(
        self,
        entity_description: SelectEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize a new ecoNET select entity."""
        self.entity_description = entity_description
        self.api = api
        self._attr_current_option = None
        super().__init__(coordinator, api)

    @property
    def options(self) -> list[str]:
        """Return the available options."""
        return list(HEATER_MODE_VALUES.values())

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._attr_current_option

    def _sync_state(self, value: str | None) -> None:
        """Synchronize the state of the select entity."""
        _LOGGER.debug("🔄 _sync_state called with value: %s", value)
        self._attr_current_option = value
        _LOGGER.debug(
            "✅ Updated _attr_current_option to: %s for entity: %s",
            self._attr_current_option,
            self.entity_description.key,
        )
        self.async_write_ha_state()
        _LOGGER.debug("📤 Called async_write_ha_state()")

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
            current_state_value = reg_params_data.get(HEATER_MODE_CURRENT_STATE_PARAM)

        return {
            "heater_mode_value": heater_mode_value,
            "current_state_value": current_state_value,
            "available_options": list(HEATER_MODE_VALUES.values()),
            "setting_parameter": HEATER_MODE_PARAM_INDEX,
            "current_state_parameter": HEATER_MODE_CURRENT_STATE_PARAM,
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
                _LOGGER.debug("📊 Coordinator data available")
                reg_params_data = self.coordinator.data.get("regParamsData", {})
                _LOGGER.debug("📋 regParamsData keys: %s", list(reg_params_data.keys()))
                _LOGGER.debug("📋 regParamsData type: %s", type(reg_params_data))

                heater_mode_value = reg_params_data.get(HEATER_MODE_CURRENT_STATE_PARAM)
                _LOGGER.debug(
                    "🎯 Heater mode current state (2049): %s (type: %s)",
                    heater_mode_value,
                    type(heater_mode_value),
                )

                if heater_mode_value is not None:
                    if heater_mode_value in HEATER_MODE_VALUES:
                        current_option = HEATER_MODE_VALUES[heater_mode_value]
                        _LOGGER.debug("✅ Found valid heater mode: %s", current_option)
                        self._attr_available = True
                        self._sync_state(current_option)
                    else:
                        _LOGGER.warning(
                            "❌ Unknown heater mode value: %s (valid values: %s)",
                            heater_mode_value,
                            list(HEATER_MODE_VALUES.keys()),
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
            _LOGGER.debug("📋 regParamsData keys: %s", list(reg_params_data.keys()))
            _LOGGER.debug("📋 regParamsData type: %s", type(reg_params_data))

            heater_mode_value = reg_params_data.get(HEATER_MODE_CURRENT_STATE_PARAM)
            _LOGGER.debug(
                "🎯 Heater mode current state (2049): %s (type: %s)",
                heater_mode_value,
                type(heater_mode_value),
            )

            if heater_mode_value is not None:
                # Map numeric value to option name
                if heater_mode_value in HEATER_MODE_VALUES:
                    current_option = HEATER_MODE_VALUES[heater_mode_value]
                    _LOGGER.debug("✅ Found valid heater mode: %s", current_option)
                    self._attr_available = True
                    self._sync_state(current_option)
                else:
                    _LOGGER.warning(
                        "❌ Unknown heater mode value: %s (valid values: %s)",
                        heater_mode_value,
                        list(HEATER_MODE_VALUES.keys()),
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
            # Get the numeric value for the selected option
            value = get_heater_mode_value(option)
            _LOGGER.debug("🔢 Converted option '%s' to value: %s", option, value)

            if value is None:
                _LOGGER.error("❌ Invalid option: %s", option)
                self._raise_heater_mode_error(f"Invalid option: {option}")

            # Use the parameter index (55) to set the value
            _LOGGER.debug(
                "📡 Calling API to set parameter %s to value %s",
                HEATER_MODE_PARAM_INDEX,
                value,
            )
            success = await self.api.set_param(HEATER_MODE_PARAM_INDEX, value)
            _LOGGER.debug("📡 API call result: %s", success)

            if success:
                # Update the current option
                old_option = self._attr_current_option
                _LOGGER.debug("🔄 Updating from '%s' to '%s'", old_option, option)

                self._attr_current_option = option
                self._attr_available = True

                # Log the change with context for better logbook entries
                _LOGGER.info(
                    "Heater mode changed from '%s' to '%s' (API value: %d)",
                    old_option or "unknown",
                    option,
                    value,
                )

                # Write the state change to trigger Home Assistant's state change logging
                _LOGGER.debug("📤 Calling async_write_ha_state() after option change")
                self.async_write_ha_state()

                # Additional context for debugging
                _LOGGER.debug(
                    "Heater mode state updated: %s -> %s (API value: %d)",
                    old_option,
                    option,
                    value,
                )
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


def get_heater_mode_name(numeric_value: int) -> str | None:
    """Convert numeric heater mode value to option name."""
    return HEATER_MODE_VALUES.get(numeric_value)


def get_heater_mode_value(option_name: str) -> int | None:
    """Convert option name to numeric heater mode value for API."""
    for value, name in HEATER_MODE_VALUES.items():
        if name == option_name:
            return value
    return None


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
    _LOGGER.debug("Entry data keys: %s", list(entry_data.keys()))

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

    # Create heater mode select entity
    heater_mode_description = SelectEntityDescription(
        key="heater_mode",
        translation_key="heater_mode",
        icon="mdi:thermostat",
    )

    entities = [
        EconetSelect(heater_mode_description, coordinator, api),
    ]

    _LOGGER.info("Adding %d select entities", len(entities))
    async_add_entities(entities)
