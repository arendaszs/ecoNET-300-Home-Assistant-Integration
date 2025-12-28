"""Switch for Econet300."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import Econet300Api, EconetDataCoordinator
from .common_functions import (
    camel_to_snake,
    get_duplicate_display_name,
    get_duplicate_entity_key,
    get_validated_entity_component,
    mixer_exists,
)
from .const import BOILER_CONTROL, DOMAIN, SERVICE_API, SERVICE_COORDINATOR
from .entity import EconetEntity, get_device_info_for_component

_LOGGER = logging.getLogger(__name__)


class BoilerControlError(HomeAssistantError):
    """Raised when boiler control fails."""


class EconetSwitch(EconetEntity, SwitchEntity):
    """Represents an ecoNET switch entity."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        entity_description: SwitchEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize a new ecoNET switch entity."""
        self.entity_description = entity_description
        self.api = api
        self._attr_is_on = False
        super().__init__(coordinator, api)

    def _sync_state(self, value: Any) -> None:
        """Synchronize the state of the switch entity."""
        # Use mode parameter: 0 = OFF, anything else = ON
        mode_value = self.coordinator.data.get("mode", 0)
        self._attr_is_on = mode_value != 0
        self.async_write_ha_state()

    def update_state_from_mode(self, mode_value: int) -> None:
        """Update switch state based on mode value."""
        self._attr_is_on = mode_value != 0
        self.async_write_ha_state()

    @staticmethod
    def _raise_boiler_control_error(message: str) -> None:
        raise BoilerControlError(message)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            # Use BOILER_CONTROL parameter: set to 1 to turn on
            success = await self.api.set_param(BOILER_CONTROL, 1)
            if not success:
                EconetSwitch._raise_boiler_control_error("Failed to turn boiler ON")
            self._attr_is_on = True
            self.async_write_ha_state()
            _LOGGER.info("Boiler turned ON")
        except Exception as e:
            _LOGGER.error("Failed to turn boiler ON: %s", e)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the boiler off."""
        try:
            # Use BOILER_CONTROL parameter: set to 0 to turn off
            success = await self.api.set_param(BOILER_CONTROL, 0)
            if not success:
                EconetSwitch._raise_boiler_control_error("Failed to turn boiler OFF")
            self._attr_is_on = False
            self.async_write_ha_state()
            _LOGGER.info("Boiler turned OFF")
        except BoilerControlError:
            raise
        except (OSError, TimeoutError) as e:
            _LOGGER.error("Failed to turn boiler OFF: %s", e)
            EconetSwitch._raise_boiler_control_error(f"Error turning boiler OFF: {e}")
        except Exception as e:
            _LOGGER.error("Failed to turn boiler OFF: %s", e)
            raise


class EconetDynamicSwitch(SwitchEntity):
    """Represents a dynamic ecoNET switch entity from mergedData."""

    _attr_has_entity_name = True

    # CONFIG entities are disabled by default - users can enable the ones they need
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entity_description: SwitchEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        param_id: str,
        param: dict,
        sequence_num: int | None = None,
    ):
        """Initialize a new dynamic ecoNET switch entity."""
        self.entity_description = entity_description
        self.coordinator = coordinator
        self.api = api
        self._param_id = param_id
        self._param = param
        self._attr_is_on = False

        # Get enum values for on/off mapping
        enum_data = param.get("enum", {})
        self._enum_values = enum_data.get("values", [])
        self._on_value = self._get_on_value()
        self._off_value = self._get_off_value()

        # Set unique ID
        self._attr_unique_id = f"econet300_switch_{param_id}"

        # Determine which component this entity belongs to (with hardware validation)
        param_name = param.get("name", "")
        param_key = param.get("key", "")
        description = param.get("description", "")
        self._component = get_validated_entity_component(
            param_name, param_key, description, sequence_num, coordinator.data
        )

        # Set initial state
        self._update_state_from_param()

    def _get_on_value(self) -> int:
        """Get the numeric value that represents ON."""
        # Usually ON is at index 1, but check for variations
        for i, val in enumerate(self._enum_values):
            if val.upper() in ("ON", "1", "TRUE", "YES", "ENABLED"):
                return i
        return 1 if len(self._enum_values) > 1 else 0

    def _get_off_value(self) -> int:
        """Get the numeric value that represents OFF."""
        # Usually OFF is at index 0
        for i, val in enumerate(self._enum_values):
            if val.upper() in ("OFF", "0", "FALSE", "NO", "DISABLED"):
                return i
        return 0

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
                self._attr_is_on = value == self._on_value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info based on entity component."""
        return get_device_info_for_component(self._component, self.api)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        # Check if locked
        if self._is_parameter_locked():
            return "mdi:lock"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including lock information."""
        attrs: dict[str, Any] = {
            "param_id": self._param_id,
            "enum_values": self._enum_values,
        }
        # Add description from API to help users understand the parameter
        description = self._param.get("description")
        if description:
            attrs["description"] = description
        if self._is_parameter_locked():
            attrs["locked"] = True
            lock_reason = self._get_lock_reason()
            if lock_reason:
                attrs["lock_reason"] = lock_reason
        return attrs

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self._is_parameter_locked():
            lock_reason = self._get_lock_reason() or "Parameter is locked"
            _LOGGER.warning(
                "Cannot turn on locked switch %s: %s",
                self.entity_description.key,
                lock_reason,
            )
            self._raise_switch_error(f"Switch is locked: {lock_reason}")

        try:
            success = await self.api.set_param(self._param_id, self._on_value)
            if success:
                self._attr_is_on = True
                self.async_write_ha_state()
                _LOGGER.info("Switch %s turned ON", self.entity_description.key)
            else:
                self._raise_switch_error(
                    f"Failed to turn on {self.entity_description.name}"
                )
        except HomeAssistantError:
            raise
        except Exception as e:
            _LOGGER.error(
                "Failed to turn on switch %s: %s", self.entity_description.key, e
            )
            raise HomeAssistantError(f"Failed to turn on switch: {e}") from e

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self._is_parameter_locked():
            lock_reason = self._get_lock_reason() or "Parameter is locked"
            _LOGGER.warning(
                "Cannot turn off locked switch %s: %s",
                self.entity_description.key,
                lock_reason,
            )
            self._raise_switch_error(f"Switch is locked: {lock_reason}")

        try:
            success = await self.api.set_param(self._param_id, self._off_value)
            if success:
                self._attr_is_on = False
                self.async_write_ha_state()
                _LOGGER.info("Switch %s turned OFF", self.entity_description.key)
            else:
                self._raise_switch_error(
                    f"Failed to turn off {self.entity_description.name}"
                )
        except HomeAssistantError:
            raise
        except Exception as e:
            _LOGGER.error(
                "Failed to turn off switch %s: %s", self.entity_description.key, e
            )
            raise HomeAssistantError(f"Failed to turn off switch: {e}") from e

    @staticmethod
    def _raise_switch_error(message: str) -> None:
        """Raise a HomeAssistantError with the given message."""
        raise HomeAssistantError(message)


def should_be_switch_entity(param: dict) -> bool:
    """Check if a parameter should be a switch entity.

    Switch entities are parameters with exactly 2 enum values (On/Off).
    """
    if "enum" not in param:
        return False

    enum_data = param.get("enum", {})
    values = enum_data.get("values", [])

    # Must have exactly 2 values
    if len(values) != 2:
        return False

    # Check if it looks like an On/Off switch
    values_upper = [v.upper() for v in values if v]
    on_off_patterns = [
        {"OFF", "ON"},
        {"0", "1"},
        {"FALSE", "TRUE"},
        {"NO", "YES"},
        {"DISABLED", "ENABLED"},
    ]

    for pattern in on_off_patterns:
        if set(values_upper) == pattern:
            return True

    # Also accept if first value is empty and second is something (like calibration toggle)
    if values[0] == "" and values[1]:
        return True

    return False


def create_dynamic_switches(
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
) -> list[SwitchEntity]:
    """Create dynamic switch entities from mergedData."""
    entities: list[SwitchEntity] = []
    key_counts: dict[str, int] = {}  # Track how many times each key has been used

    if coordinator.data is None:
        _LOGGER.debug("No coordinator data for dynamic switches")
        return entities

    merged_data = coordinator.data.get("mergedData")
    if not merged_data:
        _LOGGER.debug("No mergedData for dynamic switches")
        return entities

    parameters = merged_data.get("parameters", {})
    _LOGGER.debug("Creating dynamic switches from %d parameters", len(parameters))

    # First pass: count duplicates to know which keys need numbering
    key_totals: dict[str, int] = {}
    for param_id, param in parameters.items():
        if not should_be_switch_entity(param):
            continue
        param_name = param.get("name", f"Parameter {param_id}")
        base_key = param.get("key") or camel_to_snake(param_name)
        key_totals[base_key] = key_totals.get(base_key, 0) + 1

    for param_id, param in parameters.items():
        if not should_be_switch_entity(param):
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
                        "Skipping switch %s - mixer %d not connected",
                        param_name,
                        mixer_num,
                    )
                    continue

        # Create entity key - handle duplicates with meaningful suffixes
        base_key = param.get("key") or camel_to_snake(param_name)
        description = param.get("description", "")

        # Only add suffixes if there are duplicates
        if key_totals.get(base_key, 1) > 1:
            key_counts[base_key] = key_counts.get(base_key, 0) + 1
            sequence_num = key_counts[base_key]
            entity_key = get_duplicate_entity_key(base_key, sequence_num, description)
            display_name = get_duplicate_display_name(
                param_name, sequence_num, description
            )
        else:
            sequence_num = None
            entity_key = base_key
            display_name = param_name

        entity_description = SwitchEntityDescription(
            key=entity_key,
            name=display_name,
            translation_key=entity_key,
        )

        entity = EconetDynamicSwitch(
            entity_description,
            coordinator,
            api,
            param_id,
            param,
            sequence_num,
        )

        entities.append(entity)
        _LOGGER.debug(
            "Created dynamic switch: %s (param_id=%s, values=%s)",
            display_name,
            param_id,
            param.get("enum", {}).get("values", []),
        )

    return entities


def create_boiler_switch(
    coordinator: EconetDataCoordinator, api: Econet300Api
) -> EconetSwitch:
    """Create boiler control switch entity."""
    entity_description = SwitchEntityDescription(
        key="boiler_control",
        name="Boiler On/Off",
        translation_key="boiler_control",
    )

    return EconetSwitch(entity_description, coordinator, api)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: EconetDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        SERVICE_COORDINATOR
    ]
    api: Econet300Api = hass.data[DOMAIN][entry.entry_id][SERVICE_API]

    entities: list[SwitchEntity] = []

    # Create boiler control switch (static)
    boiler_switch = create_boiler_switch(coordinator, api)
    entities.append(boiler_switch)
    _LOGGER.info("Created 1 static switch entity (boiler control)")

    # Update the boiler switch state based on current data
    if coordinator.data and "mode" in coordinator.data:
        mode_value = coordinator.data["mode"]
        boiler_switch.update_state_from_mode(mode_value)

    # Create dynamic switch entities from mergedData
    dynamic_switches = create_dynamic_switches(coordinator, api)
    entities.extend(dynamic_switches)
    _LOGGER.info("Created %d dynamic switch entities", len(dynamic_switches))

    _LOGGER.info("Adding %d total switch entities", len(entities))
    async_add_entities(entities)
