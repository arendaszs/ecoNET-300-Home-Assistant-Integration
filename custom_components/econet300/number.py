"""Base entity number for Econet300."""

import asyncio
from dataclasses import dataclass
import logging
import re
import traceback
from typing import Any

import aiohttp
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Limits
from .common import Econet300Api, EconetDataCoordinator, skip_params_edits
from .common_functions import (
    camel_to_snake,
    extract_device_group_from_name,
    get_parameter_type_from_category,
    is_information_category,
    mixer_exists,
)
from .const import (
    AVAILABLE_NUMBER_OF_MIXERS,
    DEVICE_INFO_ADVANCED_PARAMETERS_NAME,
    DEVICE_INFO_MANUFACTURER,
    DEVICE_INFO_MODEL,
    DEVICE_INFO_SERVICE_PARAMETERS_NAME,
    DOMAIN,
    ENTITY_MAX_VALUE,
    ENTITY_MIN_VALUE,
    ENTITY_NUMBER_SENSOR_DEVICE_CLASS_MAP,
    ENTITY_STEP,
    ENTITY_UNIT_MAP,
    MIXER_SET_AVAILABILITY_KEY,
    NUMBER_MAP,
    SENSOR_MIXER_KEY,
    SERVICE_API,
    SERVICE_COORDINATOR,
    UNIT_NAME_TO_HA_UNIT,
)
from .entity import EconetEntity, MenuCategoryEntity, MixerEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EconetNumberEntityDescription(NumberEntityDescription):
    """Describes ecoNET number entity."""

    entity_category: EntityCategory | None = EntityCategory.CONFIG


class EconetNumber(EconetEntity, NumberEntity):
    """Describes ecoNET number sensor entity."""

    entity_description: EconetNumberEntityDescription

    def __init__(
        self,
        entity_description: EconetNumberEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize a new ecoNET number entity."""
        self.entity_description = entity_description
        self.api = api
        super().__init__(coordinator, api)

    def _sync_state(self, value):
        """Sync the state of the ecoNET number entity."""
        _LOGGER.info(
            "DEBUG: EconetNumber _sync_state called for entity %s with value: %s",
            self.entity_description.key,
            value,
        )
        _LOGGER.debug(
            "DEBUG: Entity key=%s, translation_key=%s, Value type: %s, Value keys: %s",
            self.entity_description.key,
            self.entity_description.translation_key,
            type(value),
            value.keys() if isinstance(value, dict) else "Not a dict",
        )

        # Handle both dict and direct value
        if isinstance(value, dict) and "value" in value:
            val = value.get("value")
            self._attr_native_value = float(val) if val is not None else None
            _LOGGER.debug(
                "DEBUG: Extracted value from dict: %s", self._attr_native_value
            )
        elif isinstance(value, (int, float, str)) and value is not None:
            self._attr_native_value = float(value)
            _LOGGER.debug("DEBUG: Using direct value: %s", self._attr_native_value)
        else:
            self._attr_native_value = None
            _LOGGER.debug("DEBUG: Invalid value type, setting to None: %s", value)

        map_key = NUMBER_MAP.get(self.entity_description.key)

        if map_key:
            _LOGGER.debug(
                "DEBUG: Found map_key %s for entity %s, setting value limits",
                map_key,
                self.entity_description.key,
            )
            self._set_value_limits(value)
        else:
            _LOGGER.debug(
                "DEBUG: No map_key found for dynamic entity %s (not in NUMBER_MAP), skipping _set_value_limits",
                self.entity_description.key,
            )
        # Ensure the state is updated in Home Assistant.
        self.async_write_ha_state()
        # Create an asynchronous task for setting the limits.
        self.hass.async_create_task(self.async_set_limits_values())

    def _set_value_limits(self, value):
        """Set native min and max values for the entity."""
        if isinstance(value, dict):
            min_val = value.get("min")
            max_val = value.get("max")
            # Only update if we have valid values, otherwise keep existing values
            if min_val is not None:
                self._attr_native_min_value = float(min_val)
            if max_val is not None:
                self._attr_native_max_value = float(max_val)
        _LOGGER.debug(
            "ecoNETNumber _set_value_limits: min=%s, max=%s",
            self._attr_native_min_value,
            self._attr_native_max_value,
        )

    async def async_set_limits_values(self):
        """Async Sync number limits."""
        _LOGGER.debug(
            "DEBUG: Getting limits for entity key: %s", self.entity_description.key
        )
        number_limits = await self.api.get_param_limits(self.entity_description.key)
        _LOGGER.debug("Number limits retrieved: %s", number_limits)

        if not number_limits:
            _LOGGER.warning(
                "DEBUG: Cannot get limits for dynamic entity: %s, numeric limits is None",
                self.entity_description.key,
            )
            return

        # Directly set min and max values based on fetched limits.
        self._attr_native_min_value = (
            float(number_limits.min)
            if number_limits.min is not None
            else self._attr_native_min_value
        )
        self._attr_native_max_value = (
            float(number_limits.max)
            if number_limits.max is not None
            else self._attr_native_max_value
        )
        _LOGGER.debug("Apply number limits: %s", self)
        self.async_write_ha_state()

    def _is_parameter_locked(self) -> bool:
        """Check if the parameter is locked.

        Returns:
            True if parameter is locked, False otherwise

        """
        if self.coordinator.data is None:
            return False

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return False

        merged_parameters = merged_data.get("parameters", {})
        if not merged_parameters:
            return False

        # Try to find parameter by key (string or int)
        entity_key = self.entity_description.key
        param_data = None

        if entity_key in merged_parameters:
            param_data = merged_parameters[entity_key]
        elif str(entity_key).isdigit() and int(entity_key) in merged_parameters:
            param_data = merged_parameters[int(entity_key)]

        if param_data:
            return param_data.get("locked", False)

        return False

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        if self._is_parameter_locked():
            return "mdi:lock"  # Show lock icon for locked parameters
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug("Set value: %s", value)

        # Check if parameter is locked
        if self._is_parameter_locked():
            _LOGGER.warning(
                "Cannot set value for locked parameter: %s (%s)",
                self.entity_description.key,
                self.entity_description.name,
            )
            raise ValueError(
                f"Parameter '{self.entity_description.name}' is locked and cannot be modified"
            )

        # Skip processing if the value is unchanged.
        if value == self._attr_native_value:
            return

        if value > self._attr_native_max_value:
            _LOGGER.warning(
                "Requested value: '%s' exceeds maximum allowed value: '%s'",
                value,
                self._attr_max_value,
            )

        if value < self._attr_native_min_value:
            _LOGGER.warning(
                "Requested value: '%s' is below allowed value: '%s'",
                value,
                self._attr_min_value,
            )
            return

        if not await self.api.set_param(self.entity_description.key, int(value)):
            _LOGGER.warning("Setting value failed")
            return

        self._attr_native_value = value
        self.async_write_ha_state()


class MixerDynamicNumber(MixerEntity, NumberEntity):
    """Mixer-related dynamic number class."""

    entity_description: EconetNumberEntityDescription

    def __init__(
        self,
        description: EconetNumberEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        mixer_idx: int,
    ):
        """Initialize a new instance of the MixerDynamicNumber class."""
        super().__init__(description, coordinator, api, mixer_idx)

    def _sync_state(self, value):
        """Sync the state of the mixer dynamic number entity."""
        _LOGGER.debug(
            "MixerDynamicNumber _sync_state for entity %s: %s",
            self.entity_description.key,
            value,
        )

        # Handle both dict and direct value
        if isinstance(value, dict) and "value" in value:
            val = value.get("value")
            self._attr_native_value = float(val) if val is not None else None
        elif isinstance(value, (int, float, str)) and value is not None:
            self._attr_native_value = float(value)
        else:
            self._attr_native_value = None

        # Ensure the state is updated in Home Assistant.
        self.async_write_ha_state()

    def _is_parameter_locked(self) -> bool:
        """Check if the parameter is locked.

        Returns:
            True if parameter is locked, False otherwise

        """
        if self.coordinator.data is None:
            return False

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return False

        merged_parameters = merged_data.get("parameters", {})
        if not merged_parameters:
            return False

        # Try to find parameter by key (string or int)
        entity_key = self.entity_description.key
        param_data = None

        if entity_key in merged_parameters:
            param_data = merged_parameters[entity_key]
        elif str(entity_key).isdigit() and int(entity_key) in merged_parameters:
            param_data = merged_parameters[int(entity_key)]

        if param_data:
            return param_data.get("locked", False)

        return False

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        if self._is_parameter_locked():
            return "mdi:lock"  # Show lock icon for locked parameters
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug("Set mixer dynamic value: %s", value)

        # Check if parameter is locked
        if self._is_parameter_locked():
            _LOGGER.warning(
                "Cannot set value for locked parameter: %s (%s)",
                self.entity_description.key,
                self.entity_description.name,
            )
            raise ValueError(
                f"Parameter '{self.entity_description.name}' is locked and cannot be modified"
            )

        # Skip processing if the value is unchanged.
        if value == self._attr_native_value:
            return

        if not await self.api.set_param(self.entity_description.key, int(value)):
            _LOGGER.warning("Setting mixer dynamic value failed")
            return

        self._attr_native_value = value
        self.async_write_ha_state()


class MixerNumber(MixerEntity, NumberEntity):
    """Mixer number class."""

    entity_description: EconetNumberEntityDescription

    def __init__(
        self,
        description: EconetNumberEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize a new instance of the MixerNumber class."""
        super().__init__(description, coordinator, api, idx)

    def _sync_state(self, value):
        """Sync the state of the mixer number entity."""
        _LOGGER.debug(
            "MixerNumber _sync_state for entity %s: %s",
            self.entity_description.key,
            value,
        )
        _LOGGER.debug(
            "DEBUG: Entity key=%s, translation_key=%s, Value type: %s, Value keys: %s",
            self.entity_description.key,
            self.entity_description.translation_key,
            type(value),
            value.keys() if isinstance(value, dict) else "Not a dict",
        )

        # Handle both dict and direct value
        if isinstance(value, dict) and "value" in value:
            val = value.get("value")
            self._attr_native_value = float(val) if val is not None else None
            _LOGGER.debug(
                "DEBUG: Extracted value from dict: %s", self._attr_native_value
            )
        elif isinstance(value, (int, float, str)) and value is not None:
            self._attr_native_value = float(value)
            _LOGGER.debug("DEBUG: Using direct value: %s", self._attr_native_value)
        else:
            self._attr_native_value = None
            _LOGGER.debug("DEBUG: Invalid value type, setting to None: %s", value)

        map_key = NUMBER_MAP.get(self.entity_description.key)

        if map_key:
            _LOGGER.debug(
                "DEBUG: Found map_key %s for mixer entity %s, setting value limits",
                map_key,
                self.entity_description.key,
            )
            self._set_value_limits(value)
        else:
            _LOGGER.debug(
                "DEBUG: No map_key found for mixer entity %s (not in NUMBER_MAP), skipping _set_value_limits",
                self.entity_description.key,
            )
        # Ensure the state is updated in Home Assistant.
        self.async_write_ha_state()
        # Create an asynchronous task for setting the limits.
        self.hass.async_create_task(self.async_set_limits_values())

    def _set_value_limits(self, value):
        """Set native min and max values for the entity."""
        if isinstance(value, dict):
            min_val = value.get("min")
            max_val = value.get("max")
            # Only update if we have valid values, otherwise keep existing values
            if min_val is not None:
                self._attr_native_min_value = float(min_val)
            if max_val is not None:
                self._attr_native_max_value = float(max_val)
        _LOGGER.debug(
            "MixerNumber _set_value_limits: min=%s, max=%s",
            self._attr_native_min_value,
            self._attr_native_max_value,
        )

    async def async_set_limits_values(self):
        """Async Sync number limits."""
        number_limits = await self.api.get_param_limits(self.entity_description.key)
        _LOGGER.debug("Number limits retrieved: %s", number_limits)

        if not number_limits:
            _LOGGER.info(
                "Cannot add mixer number entity: %s, numeric limits for this entity is None",
                self.entity_description.key,
            )
            return

        # Directly set min and max values based on fetched limits.
        self._attr_native_min_value = (
            float(number_limits.min)
            if number_limits.min is not None
            else self._attr_native_min_value
        )
        self._attr_native_max_value = (
            float(number_limits.max)
            if number_limits.max is not None
            else self._attr_native_max_value
        )
        _LOGGER.debug("Apply mixer number limits: %s", self)
        self.async_write_ha_state()

    def _is_parameter_locked(self) -> bool:
        """Check if the parameter is locked.

        Returns:
            True if parameter is locked, False otherwise

        """
        if self.coordinator.data is None:
            return False

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return False

        merged_parameters = merged_data.get("parameters", {})
        if not merged_parameters:
            return False

        # Try to find parameter by key (string or int)
        entity_key = self.entity_description.key
        param_data = None

        if entity_key in merged_parameters:
            param_data = merged_parameters[entity_key]
        elif str(entity_key).isdigit() and int(entity_key) in merged_parameters:
            param_data = merged_parameters[int(entity_key)]

        if param_data:
            return param_data.get("locked", False)

        return False

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        if self._is_parameter_locked():
            return "mdi:lock"  # Show lock icon for locked parameters
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug("Set mixer value: %s", value)

        # Check if parameter is locked
        if self._is_parameter_locked():
            _LOGGER.warning(
                "Cannot set value for locked parameter: %s (%s)",
                self.entity_description.key,
                self.entity_description.name,
            )
            raise ValueError(
                f"Parameter '{self.entity_description.name}' is locked and cannot be modified"
            )

        # Skip processing if the value is unchanged.
        if value == self._attr_native_value:
            return

        if value > self._attr_native_max_value:
            _LOGGER.warning(
                "Requested mixer value: '%s' exceeds maximum allowed value: '%s'",
                value,
                self._attr_max_value,
            )

        if value < self._attr_native_min_value:
            _LOGGER.warning(
                "Requested mixer value: '%s' is below allowed value: '%s'",
                value,
                self._attr_min_value,
            )
            return

        if not await self.api.set_param(self.entity_description.key, int(value)):
            _LOGGER.warning("Setting mixer value failed")
            return

        self._attr_native_value = value
        self.async_write_ha_state()


class ServiceParameterNumber(EconetNumber):
    """Service parameter number entity - disabled by default."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for service parameters."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.uid}-service-parameters")},
            name=DEVICE_INFO_SERVICE_PARAMETERS_NAME,
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            via_device=(DOMAIN, self.api.uid),
        )


class AdvancedParameterNumber(EconetNumber):
    """Advanced parameter number entity - disabled by default."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for advanced parameters."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.uid}-advanced-parameters")},
            name=DEVICE_INFO_ADVANCED_PARAMETERS_NAME,
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            via_device=(DOMAIN, self.api.uid),
        )


class MenuCategoryNumber(MenuCategoryEntity, NumberEntity):  # type: ignore[misc]
    """Dynamic number entity grouped by menu category.

    This entity type creates number entities that are grouped into
    Home Assistant devices based on the ecoNET controller menu structure.
    Each unique category index creates a separate device.

    Note: type: ignore[misc] is used because of entity_description type
    conflict between MenuCategoryEntity and NumberEntity base classes.
    This is a known limitation with multiple inheritance in Python type checking.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        description: EconetNumberEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        category_index: int,
        category_name: str,
        param_id: str,
    ):
        """Initialize a new instance of the MenuCategoryNumber class.

        Args:
            description: Entity description with key, name, limits, etc.
            coordinator: Data coordinator for updates
            api: API instance for setting values
            category_index: Index into rmCatsNames array
            category_name: Human-readable category name from rmCatsNames
            param_id: Parameter ID for looking up value in merged data

        """
        super().__init__(description, coordinator, api, category_index, category_name)
        self._param_id = param_id
        # Set attributes with defaults for None values
        self._attr_native_min_value = (
            description.native_min_value
            if description.native_min_value is not None
            else 0.0
        )
        self._attr_native_max_value = (
            description.native_max_value
            if description.native_max_value is not None
            else 100.0
        )
        self._attr_native_step = (
            description.native_step if description.native_step is not None else 1.0
        )
        self._attr_mode = (
            description.mode if description.mode is not None else NumberMode.AUTO
        )
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_native_value: float | None = None
        # Lock state tracking
        self._locked: bool = False
        self._lock_reason: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            return

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return

        merged_parameters = merged_data.get("parameters", {})
        if not merged_parameters:
            return

        # Look up value using param_id
        param_data = merged_parameters.get(self._param_id)
        if param_data and isinstance(param_data, dict):
            value = param_data.get("value")
            if value is not None:
                self._sync_state(value)

            # Update lock state
            self._locked = param_data.get("locked", False)
            self._lock_reason = param_data.get("lock_reason")

            self.async_write_ha_state()

    def _sync_state(self, value) -> None:
        """Sync the state of the menu category number entity."""
        _LOGGER.debug(
            "MenuCategoryNumber _sync_state for entity %s (param_id=%s): %s",
            self.entity_description.key,
            self._param_id,
            value,
        )
        if value is not None:
            try:
                self._attr_native_value = float(value)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Could not convert value %s to float for entity %s",
                    value,
                    self.entity_description.key,
                )

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
                self._sync_state(value)

            # Initialize lock state
            self._locked = param_data.get("locked", False)
            self._lock_reason = param_data.get("lock_reason")

            _LOGGER.debug(
                "Initialized MenuCategoryNumber %s with value %s (locked=%s)",
                self.entity_description.key,
                value,
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

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the menu category number entity."""
        _LOGGER.debug("Set menu category number value: %s", value)

        # Check if parameter is locked
        if self._locked:
            reason = self._lock_reason or "Parameter is locked"
            _LOGGER.warning(
                "Cannot set value for %s: %s",
                self.entity_description.key,
                reason,
            )
            raise HomeAssistantError(f"Cannot change value: {reason}")

        try:
            # Validate value is within bounds
            if self._attr_native_max_value is not None:
                if value > self._attr_native_max_value:
                    _LOGGER.warning(
                        "Requested value: '%s' exceeds maximum allowed value: '%s'",
                        value,
                        self._attr_native_max_value,
                    )
                    return

            if self._attr_native_min_value is not None:
                if value < self._attr_native_min_value:
                    _LOGGER.warning(
                        "Requested value: '%s' is below allowed value: '%s'",
                        value,
                        self._attr_native_min_value,
                    )
                    return

            # Use the API to set the parameter value
            if not await self.api.set_param(self.entity_description.key, int(value)):
                _LOGGER.warning("Setting menu category number value failed")
                return

            self._attr_native_value = value
            self.async_write_ha_state()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Error setting menu category number value: %s", e)


def can_add(key: str, coordinator: EconetDataCoordinator) -> bool:
    """Check if a given entity can be added based on the availability of data in the coordinator."""
    try:
        return (
            coordinator.has_param_edit_data(key)
            and coordinator.data["paramsEdits"][key]
        )
    except KeyError as e:
        _LOGGER.error("KeyError in can_add: %s", e)
        return False


def create_number_entity_description(
    key: str, limits: Limits | None = None
) -> EconetNumberEntityDescription:
    """Create ecoNET300 number entity description."""
    map_key = NUMBER_MAP.get(str(key), str(key))
    _LOGGER.debug("Creating number entity for key: %s", map_key)

    # Use limits if provided, otherwise use default values
    min_value = (
        float(limits.min)
        if limits and limits.min is not None
        else float(ENTITY_MIN_VALUE.get(map_key, 0))
    )
    max_value = (
        float(limits.max)
        if limits and limits.max is not None
        else float(ENTITY_MAX_VALUE.get(map_key, 100))
    )

    return EconetNumberEntityDescription(
        key=key,
        translation_key=camel_to_snake(map_key),
        device_class=ENTITY_NUMBER_SENSOR_DEVICE_CLASS_MAP.get(map_key),
        mode=NumberMode.AUTO,  # Show as input box instead of slider
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(map_key),
        native_min_value=min_value,
        native_max_value=max_value,
        native_step=ENTITY_STEP.get(map_key, 1),
        entity_category=EntityCategory.CONFIG,
    )


def is_mixer_related_entity(param_name: str, param_key: str) -> tuple[bool, int | None]:
    """Check if a dynamic entity is mixer-related and return the mixer number.

    Args:
        param_name: The parameter name (e.g., "Preset mixer 1 temperature")
        param_key: The parameter key (e.g., "preset_mixer1_temperature")

    Returns:
        Tuple of (is_mixer_related, mixer_number)

    """

    # Check parameter name for mixer patterns
    mixer_patterns = [
        r"mixer\s*(\d+)",  # "mixer 1", "mixer1"
        r"mixer(\d+)",  # "mixer1"
        r"(\d+)\s*mixer",  # "1 mixer"
    ]

    for pattern in mixer_patterns:
        match = re.search(pattern, param_name.lower())
        if match:
            mixer_num = int(match.group(1))
            if 1 <= mixer_num <= AVAILABLE_NUMBER_OF_MIXERS:
                return True, mixer_num

    # Check parameter key for mixer patterns
    mixer_key_patterns = [
        r"mixer(\d+)",  # "mixer1"
        r"(\d+)_mixer",  # "1_mixer"
    ]

    for pattern in mixer_key_patterns:
        match = re.search(pattern, param_key.lower())
        if match:
            mixer_num = int(match.group(1))
            if 1 <= mixer_num <= AVAILABLE_NUMBER_OF_MIXERS:
                return True, mixer_num

    return False, None


def should_be_number_entity(param: dict) -> bool:
    """Check if parameter should be a number entity.

    Args:
        param: Parameter dictionary from merged data

    Returns:
        True if parameter should be a number entity

    """
    unit_name = param.get("unit_name", "")
    has_enum = "enum" in param
    is_editable = param.get("edit", False)

    # Number entity: has unit_name, is editable, no enum
    return bool(unit_name and is_editable and not has_enum)


async def create_mixer_number_entities(
    coordinator: EconetDataCoordinator, api: Econet300Api
) -> list[MixerNumber]:
    """Create mixer number entities dynamically based on available mixers."""
    entities: list[MixerNumber] = []

    try:
        _LOGGER.info("DEBUG: Entering create_mixer_number_entities function")
        _LOGGER.info("Creating mixer number entities dynamically...")

        # Use the same logic as sensor.py - check SENSOR_MIXER_KEY
        for mixer_idx, mixer_keys in SENSOR_MIXER_KEY.items():
            _LOGGER.info(
                "DEBUG: Checking mixer %d with keys: %s", mixer_idx, mixer_keys
            )
            # Check if all required mixer keys have valid (non-null) values
            if any(
                coordinator.data.get("regParams", {}).get(mixer_key) is None
                for mixer_key in mixer_keys
            ):
                _LOGGER.info(
                    "Mixer: %d will not be created due to invalid data.", mixer_idx
                )
                continue

            _LOGGER.info(
                "DEBUG: Mixer %d passed validation, creating entity", mixer_idx
            )
            # Create the mixer set temperature key (e.g., "mixerSetTemp1")
            mixer_set_temp_key = f"{MIXER_SET_AVAILABILITY_KEY}{mixer_idx}"

            # Create entity description with default limits (like mixer sensors)
            # Mixer sensors don't need API limits, they get data from regParams
            entity_description = create_number_entity_description(
                mixer_set_temp_key,
                None,  # No limits needed, like mixer sensors
            )

            # Create and add the entity
            entity = MixerNumber(entity_description, coordinator, api, mixer_idx)
            entities.append(entity)
            _LOGGER.info(
                "Created mixer number entity: %s (Mixer %d)",
                mixer_set_temp_key,
                mixer_idx,
            )
            _LOGGER.info(
                "DEBUG: MixerNumber device_info: %s",
                entity.device_info,
            )

        _LOGGER.info(
            "DEBUG: Exiting create_mixer_number_entities with %d entities",
            len(entities),
        )

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
    ) as e:
        _LOGGER.error("DEBUG: Exception in create_mixer_number_entities: %s", e)
        _LOGGER.error("DEBUG: Exception type: %s", type(e))
        _LOGGER.error("DEBUG: Traceback: %s", traceback.format_exc())

    return entities


def create_dynamic_number_entity_description(
    param_id: str, param: dict, param_type: str = "basic"
) -> EconetNumberEntityDescription:
    """Create a number entity description from parameter data.

    Args:
        param_id: Parameter ID (string)
        param: Parameter dictionary from merged data
        param_type: Parameter type (basic/service/advanced) for entity ID prefix

    Returns:
        EconetNumberEntityDescription for the parameter

    """
    # Get unit mapping
    unit_name = param.get("unit_name", "")
    ha_unit = UNIT_NAME_TO_HA_UNIT.get(unit_name)

    # Get min/max values
    min_value = float(param.get("minv", 0))
    max_value = float(param.get("maxv", 100))

    # Determine step based on unit and range
    if unit_name in {"%", "°C"} or unit_name in ["sek.", "min.", "h."]:
        step = 1.0
    elif max_value - min_value > 100:
        step = 5.0
    else:
        step = 1.0

    # Generate translation key with category prefix
    param_key = param.get("key", f"parameter_{param_id}")
    translation_key = param_key

    # Generate entity key with category prefix to avoid conflicts
    if param_type == "service":
        entity_key = f"service_{param_key}"
    elif param_type == "advanced":
        entity_key = f"advanced_{param_key}"
    else:
        entity_key = f"basic_{param_key}"

    _LOGGER.debug(
        "DEBUG: Creating entity description for param_id=%s, name=%s, key=%s, translation_key=%s, entity_key=%s, type=%s",
        param_id,
        param.get("name", "No name"),
        param_key,
        translation_key,
        entity_key,
        param_type,
    )

    return EconetNumberEntityDescription(
        key=entity_key,  # Use category-prefixed key
        name=param.get("name", f"Parameter {param_id}"),  # Add explicit name
        translation_key=translation_key,
        device_class=None,  # No specific device class for dynamic entities
        mode=NumberMode.BOX,  # Always show as number input box
        native_unit_of_measurement=ha_unit,
        native_min_value=min_value,
        native_max_value=max_value,
        native_step=step,
        entity_category=EntityCategory.CONFIG,
    )


async def _create_basic_entities(
    api: Econet300Api, coordinator: EconetDataCoordinator
) -> list[EconetNumber]:
    """Create basic NUMBER_MAP entities.

    Args:
        api: API instance
        coordinator: Data coordinator

    Returns:
        List of basic number entities

    """
    entities: list[EconetNumber] = []
    _LOGGER.info("Creating basic NUMBER_MAP entities (always shown)")
    for key in NUMBER_MAP:
        # Skip mixer entities as they are created dynamically
        map_value = NUMBER_MAP.get(key)
        if map_value and map_value.startswith("mixerSetTemp"):
            continue
        number_limits = await api.get_param_limits(key)
        if number_limits is None:
            _LOGGER.info(
                "Cannot add basic number entity: %s, numeric limits for this entity is None",
                key,
            )
            continue

        if can_add(key, coordinator):
            entity_description = create_number_entity_description(key, number_limits)
            entities.append(EconetNumber(entity_description, coordinator, api))
            _LOGGER.info("Created basic number entity: %s (%s)", key, map_value)
        else:
            _LOGGER.info(
                "Cannot add basic number entity - availability key: %s does not exist",
                key,
            )
    _LOGGER.info("Created %d basic NUMBER_MAP entities", len(entities))
    return entities


def _create_mixer_entity_by_category(
    entity_description: EconetNumberEntityDescription,
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
    mixer_num: int,
    param_type: str,
    param_name: str,
    category: str,
    param_id: str,
) -> NumberEntity:
    """Create mixer entity based on category type.

    All mixer entities are now grouped into their respective "Mixer X settings"
    devices using MenuCategoryNumber. Service/advanced params are disabled by default.

    Args:
        entity_description: Entity description
        coordinator: Data coordinator
        api: API instance
        mixer_num: Mixer number (1-4)
        param_type: Parameter type (service/advanced/basic)
        param_name: Parameter name
        category: Category name
        param_id: Parameter ID for value lookup

    Returns:
        MenuCategoryNumber entity grouped under Mixer device

    """
    # Mixer settings devices are at index 5-8 (4 + mixer_num)
    category_index = 4 + mixer_num
    category_name = f"Mixer {mixer_num} settings"

    # Create MenuCategoryNumber entity - grouped by mixer device
    entity = MenuCategoryNumber(
        entity_description,
        coordinator,
        api,
        category_index,
        category_name,
        param_id,
    )

    # Set disabled by default for service/advanced params
    if param_type in ("service", "advanced"):
        entity._attr_entity_registry_enabled_default = False  # noqa: SLF001

    _LOGGER.info(
        "Created mixer number entity: %s (Mixer %d, type: %s, category: %s)",
        param_name,
        mixer_num,
        param_type,
        category_name,
    )

    return entity


def _create_regular_entity_by_category(
    entity_description: EconetNumberEntityDescription,
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
    param_type: str,
    param_name: str,
    param_id: str,
    category: str,
    param: dict,
) -> NumberEntity:
    """Create regular entity based on category type.

    Uses MenuCategoryNumber to group entities by their menu category index,
    creating separate Home Assistant devices for each menu section.

    First tries to extract device group from parameter name (for better grouping
    when parameters are miscategorized in rmStructure), then falls back to
    structure-based category.

    Args:
        entity_description: Entity description
        coordinator: Data coordinator
        api: API instance
        param_type: Parameter type (service/advanced/basic)
        param_name: Parameter name
        param_id: Parameter ID
        category: Category name
        param: Parameter dictionary (should contain category_index)

    Returns:
        MenuCategoryNumber entity grouped by menu category

    """
    # First, try to extract device group from parameter name (for better grouping)
    name_based_index, name_based_category = extract_device_group_from_name(
        param_name, for_information=False
    )

    # Use name-based grouping if found, otherwise fall back to structure-based
    if name_based_index is not None and name_based_category is not None:
        category_index = name_based_index
        effective_category = name_based_category
        _LOGGER.debug(
            "Using name-based grouping for %s: %s (index %d)",
            param_name,
            effective_category,
            category_index,
        )
    else:
        # Get category index from param (added by API merge process)
        category_index = param.get("category_index", 0)
        effective_category = category

    # Create MenuCategoryNumber entity - grouped by menu category
    entity = MenuCategoryNumber(
        entity_description,
        coordinator,
        api,
        category_index,
        effective_category,
        param_id,  # Pass param_id for value lookup
    )

    _LOGGER.info(
        "Created menu category number entity: %s (%s) - category[%d]: %s, type: %s, %s to %s %s",
        param_name,
        param_id,
        category_index,
        effective_category,
        param_type,
        param.get("minv", 0),
        param.get("maxv", 100),
        param.get("unit_name", ""),
    )

    return entity


def _create_dynamic_entity_from_param(
    param_id: str,
    param: dict,
    category: str,
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
    basic_param_ids: set[str],
    show_service: bool,
) -> NumberEntity | None:
    """Create a dynamic entity from a parameter.

    Args:
        param_id: Parameter ID
        param: Parameter dictionary
        category: Category name for this entity
        coordinator: Data coordinator
        api: API instance
        basic_param_ids: Set of basic parameter IDs to skip
        show_service: Whether to show service parameters

    Returns:
        Created entity or None if skipped

    """
    # Skip basic parameters (already created from NUMBER_MAP)
    if param_id in basic_param_ids:
        _LOGGER.debug(
            "Skipping parameter %s - already created as basic NUMBER_MAP entity",
            param_id,
        )
        return None

    # Skip Information categories (handled by sensors)
    if is_information_category(category):
        _LOGGER.debug(
            "Skipping Information category '%s' for parameter %s",
            category,
            param_id,
        )
        return None

    # Determine parameter type from category
    param_type = get_parameter_type_from_category(category)

    # Skip service/advanced parameters if show_service is False
    if param_type in ("service", "advanced") and not show_service:
        _LOGGER.debug(
            "Skipping %s parameter %s - show_service_parameters is False",
            param_type,
            param_id,
        )
        return None

    if not should_be_number_entity(param):
        return None

    param_name = param.get("name", f"Parameter {param_id}")

    _LOGGER.info(
        "DEBUG: Parameter %s qualifies as number entity: name=%s, unit_name=%s, edit=%s, category=%s, type=%s",
        param_id,
        param_name,
        param.get("unit_name", "No unit"),
        param.get("edit", False),
        category,
        param_type,
    )

    try:
        entity_description = create_dynamic_number_entity_description(
            param_id, param, param_type
        )

        # Check if this is a mixer-related entity
        param_key = param.get("key", f"parameter_{param_id}")
        is_mixer_related, mixer_num = is_mixer_related_entity(param_name, param_key)

        if is_mixer_related:
            _LOGGER.info(
                "DEBUG: Found mixer-related entity: '%s' -> Mixer %d",
                param_name,
                mixer_num,
            )

        # Create entity based on type and category
        if is_mixer_related and mixer_num is not None:
            # Check if the mixer actually exists in the boiler
            if not mixer_exists(coordinator.data, mixer_num):
                _LOGGER.debug(
                    "Skipping mixer entity '%s' - Mixer %d does not exist",
                    param_name,
                    mixer_num,
                )
                return None

            return _create_mixer_entity_by_category(
                entity_description,
                coordinator,
                api,
                mixer_num,
                param_type,
                param_name,
                category,
                param_id,
            )

        return _create_regular_entity_by_category(
            entity_description,
            coordinator,
            api,
            param_type,
            param_name,
            param_id,
            category,
            param,
        )

    except (ValueError, KeyError, TypeError) as e:
        _LOGGER.warning(
            "Failed to create dynamic number entity for parameter %s: %s",
            param_id,
            e,
        )
        return None


async def _create_dynamic_entities_from_merged_data(
    merged_data: dict,
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
    basic_param_ids: set[str],
    show_service: bool,
) -> list[NumberEntity]:
    """Create dynamic entities from merged parameter data.

    Args:
        merged_data: Merged parameter data
        coordinator: Data coordinator
        api: API instance
        basic_param_ids: Set of basic parameter IDs to skip
        show_service: Whether to show service parameters

    Returns:
        List of dynamic entities

    """
    entities: list[NumberEntity] = []
    _LOGGER.info("Using dynamic number entity creation from merged parameter data")

    _LOGGER.info(
        "DEBUG: Starting dynamic entity creation. Total parameters: %d",
        len(merged_data["parameters"]),
    )

    # Debug: Log first few parameters to understand structure
    for param_count, (param_id, param) in enumerate(merged_data["parameters"].items()):
        if param_count < 5:  # Log first 5 parameters for debugging
            categories = param.get("categories", [param.get("category", "")])
            _LOGGER.info(
                "DEBUG: Sample parameter %s: name=%s, unit_name=%s, edit=%s, has_enum=%s, categories=%s",
                param_id,
                param.get("name", "No name"),
                param.get("unit_name", "No unit"),
                param.get("edit", False),
                "enum" in param,
                categories,
            )

    number_entity_count = 0
    created_entity_keys: set[str] = (
        set()
    )  # Track created entity keys to avoid duplicates

    for param_id, param in merged_data["parameters"].items():
        _LOGGER.debug("DEBUG: Processing parameter %s: %s", param_id, param)

        # Get parameter key - this is what determines uniqueness
        param_key = param.get("key", f"parameter_{param_id}")

        # Skip if we've already created an entity for this parameter key
        if param_key in created_entity_keys:
            _LOGGER.debug(
                "Skipping parameter %s - entity for key '%s' already created",
                param_id,
                param_key,
            )
            continue

        # Get all categories for this parameter
        categories = param.get("categories", [param.get("category", "")])
        if not categories:
            categories = [param.get("category", "")]

        _LOGGER.debug("Parameter %s has categories: %s", param_id, categories)

        # Iterate through all categories, skip Information (handled by sensors)
        for category in categories:
            # Skip Information categories (create read-only sensors instead)
            if is_information_category(category):
                _LOGGER.debug(
                    "Skipping Information category '%s' for parameter %s (will be created as sensor)",
                    category,
                    param_id,
                )
                continue

            # Create number entity for this category
            entity = _create_dynamic_entity_from_param(
                param_id,
                param,
                category,
                coordinator,
                api,
                basic_param_ids,
                show_service,
            )
            if entity:
                entities.append(entity)
                number_entity_count += 1
                # Track parameter key to avoid duplicates
                created_entity_keys.add(param_key)
                break  # Only create one number entity per parameter (first non-Information category)

    _LOGGER.info(
        "DEBUG: Found %d parameters that qualify as number entities",
        number_entity_count,
    )
    _LOGGER.info(
        "Created %d dynamic number entities (Information categories handled as sensors)",
        len(entities),
    )
    if show_service:
        _LOGGER.info(
            "Service/advanced parameters enabled (show_service_parameters=True)"
        )
    else:
        _LOGGER.info(
            "Service/advanced parameters disabled (show_service_parameters=False). "
            "Only basic parameters are shown."
        )

    return entities


async def _create_legacy_entities(
    api: Econet300Api, coordinator: EconetDataCoordinator
) -> list[NumberEntity]:
    """Create legacy entities from NUMBER_MAP (fallback).

    Args:
        api: API instance
        coordinator: Data coordinator

    Returns:
        List of legacy entities

    """
    entities: list[NumberEntity] = []
    _LOGGER.info("Falling back to legacy number entity creation from NUMBER_MAP")

    # Create mixer number entities dynamically
    _LOGGER.info("DEBUG: Creating mixer number entities...")
    mixer_entities = await create_mixer_number_entities(coordinator, api)
    _LOGGER.info("DEBUG: Created %d mixer number entities", len(mixer_entities))
    entities.extend(mixer_entities)

    # Create other number entities from NUMBER_MAP (excluding mixer entities)
    for key in NUMBER_MAP:
        # Skip mixer entities as they are created dynamically above
        map_value = NUMBER_MAP.get(key)
        if map_value and map_value.startswith("mixerSetTemp"):
            continue
        number_limits = await api.get_param_limits(key)
        if number_limits is None:
            _LOGGER.info(
                "Cannot add number entity: %s, numeric limits for this entity is None",
                key,
            )
            continue

        if can_add(key, coordinator):
            entity_description = create_number_entity_description(key, number_limits)
            entities.append(EconetNumber(entity_description, coordinator, api))
        else:
            _LOGGER.info(
                "Cannot add number entity - availability key: %s does not exist",
                key,
            )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][SERVICE_COORDINATOR]
    api = hass.data[DOMAIN][entry.entry_id][SERVICE_API]

    entities: list[NumberEntity] = []

    # Read options for entity filtering
    options = dict(entry.options) if entry.options else {}  # type: ignore[arg-type]
    show_service = options.get("show_service_parameters", False)
    enable_dynamic = options.get("enable_dynamic_entities", True)

    # Define basic parameter IDs from NUMBER_MAP (always shown)
    basic_param_ids = set(NUMBER_MAP.keys())

    # Check if we should skip params edits for certain controllers
    sys_params = None
    if coordinator.data is not None:
        sys_params = coordinator.data.get("sysParams")
    if sys_params is None:
        sys_params = {}
    if skip_params_edits(sys_params):
        _LOGGER.info("Skipping number entity setup for controllerID: ecoMAX360i")
        return async_add_entities(entities)

    # Always create basic NUMBER_MAP entities first
    basic_entities = await _create_basic_entities(api, coordinator)
    entities.extend(basic_entities)

    # Try to get merged parameter data for dynamic entity creation
    if not enable_dynamic:
        _LOGGER.info("Dynamic entities disabled in options, skipping dynamic creation")
        return async_add_entities(entities)

    try:
        merged_data = await api.fetch_merged_rm_data_with_names_descs_and_structure()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        _LOGGER.warning("Failed to fetch merged parameter data: %s", e)
        merged_data = None

    if merged_data and "parameters" in merged_data:
        # Create dynamic entities from merged data
        dynamic_entities = await _create_dynamic_entities_from_merged_data(
            merged_data, coordinator, api, basic_param_ids, show_service
        )
        entities.extend(dynamic_entities)

        # Create mixer number entities dynamically (even in dynamic mode)
        _LOGGER.info("DEBUG: About to call create_mixer_number_entities...")
        mixer_entities = await create_mixer_number_entities(coordinator, api)
        _LOGGER.info(
            "DEBUG: create_mixer_number_entities returned %d entities",
            len(mixer_entities),
        )
        entities.extend(mixer_entities)
        _LOGGER.info(
            "DEBUG: Total entities after adding mixer entities: %d", len(entities)
        )
    else:
        # Fallback to legacy entity creation
        legacy_entities = await _create_legacy_entities(api, coordinator)
        entities.extend(legacy_entities)

    # Final check - if no entities were created, log a warning
    mixer_count = len(
        [e for e in entities if isinstance(e, (MixerNumber, MixerDynamicNumber))]
    )
    dynamic_count = len([e for e in entities if e not in basic_entities])
    _LOGGER.info(
        "Final entity count: %d total entities created (%d basic + %d advanced + %d mixer)",
        len(entities),
        len(basic_entities),
        dynamic_count,
        mixer_count,
    )
    if not entities:
        _LOGGER.warning(
            "No number entities could be created. This may indicate that your device "
            "does not support the rmParamsData endpoint for dynamic entities, and "
            "the legacy NUMBER_MAP entities are not available on your device."
        )

    return async_add_entities(entities)
