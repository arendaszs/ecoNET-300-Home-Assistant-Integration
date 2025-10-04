"""Base entity number for Econet300."""

import asyncio
from dataclasses import dataclass
import logging

import aiohttp
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Limits
from .common import Econet300Api, EconetDataCoordinator, skip_params_edits
from .common_functions import camel_to_snake
from .const import (
    DOMAIN,
    ENTITY_MAX_VALUE,
    ENTITY_MIN_VALUE,
    ENTITY_NUMBER_SENSOR_DEVICE_CLASS_MAP,
    ENTITY_STEP,
    ENTITY_UNIT_MAP,
    NUMBER_MAP,
    SERVICE_API,
    SERVICE_COORDINATOR,
    UNIT_NAME_TO_HA_UNIT,
)
from .entity import EconetEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EconetNumberEntityDescription(NumberEntityDescription):
    """Describes ecoNET number entity."""


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
        _LOGGER.debug(
            "ecoNETNumber _sync_state for entity %s: %s",
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
            self._set_value_limits(value)
        else:
            _LOGGER.error(
                "ecoNETNumber _sync_state: map_key %s not found in NUMBER_MAP",
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
        number_limits = await self.api.get_param_limits(self.entity_description.key)
        _LOGGER.debug("Number limits retrieved: %s", number_limits)

        if not number_limits:
            _LOGGER.info(
                "Cannot add number entity: %s, numeric limits for this entity is None",
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

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug("Set value: %s", value)

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
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(map_key),
        native_min_value=min_value,
        native_max_value=max_value,
        native_step=ENTITY_STEP.get(map_key, 1),
    )


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


def create_dynamic_number_entity_description(
    param_id: str, param: dict
) -> EconetNumberEntityDescription:
    """Create a number entity description from parameter data.

    Args:
        param_id: Parameter ID (string)
        param: Parameter dictionary from merged data

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

    # Debug translation key generation
    translation_key = param.get("key", f"parameter_{param_id}")
    _LOGGER.debug(
        "DEBUG: Creating entity description for param_id=%s, name=%s, key=%s, translation_key=%s",
        param_id,
        param.get("name", "No name"),
        param.get("key", "No key"),
        translation_key,
    )

    return EconetNumberEntityDescription(
        key=param_id,
        translation_key=translation_key,
        native_unit_of_measurement=ha_unit,
        native_min_value=min_value,
        native_max_value=max_value,
        native_step=step,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][SERVICE_COORDINATOR]
    api = hass.data[DOMAIN][entry.entry_id][SERVICE_API]

    entities: list[EconetNumber] = []

    # Check if we should skip params edits for certain controllers
    sys_params = coordinator.data.get("sysParams", {})
    if skip_params_edits(sys_params):
        _LOGGER.info("Skipping number entity setup for controllerID: ecoMAX360i")
        return async_add_entities(entities)

    # Try to get merged parameter data for dynamic entity creation
    try:
        merged_data = await api.fetch_merged_rm_data_with_names_descs_and_structure()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        _LOGGER.warning("Failed to fetch merged parameter data: %s", e)
        merged_data = None

    if merged_data and "parameters" in merged_data:
        _LOGGER.info("Using dynamic number entity creation from merged parameter data")

        # Create number entities dynamically from merged data
        dynamic_entities = []
        _LOGGER.info(
            "DEBUG: Starting dynamic entity creation. Total parameters: %d",
            len(merged_data["parameters"]),
        )

        for param_id, param in merged_data["parameters"].items():
            _LOGGER.debug("DEBUG: Processing parameter %s: %s", param_id, param)

            if should_be_number_entity(param):
                try:
                    entity_description = create_dynamic_number_entity_description(
                        param_id, param
                    )
                    entity = EconetNumber(entity_description, coordinator, api)
                    dynamic_entities.append(entity)
                    _LOGGER.info(
                        "Created dynamic number entity: %s (%s) - %s to %s %s, translation_key=%s",
                        param.get("name", f"Parameter {param_id}"),
                        param_id,
                        param.get("minv", 0),
                        param.get("maxv", 100),
                        param.get("unit_name", ""),
                        entity_description.translation_key,
                    )
                except (ValueError, KeyError, TypeError) as e:
                    _LOGGER.warning(
                        "Failed to create dynamic number entity for parameter %s: %s",
                        param_id,
                        e,
                    )

        entities.extend(dynamic_entities)
        _LOGGER.info("Created %d dynamic number entities", len(dynamic_entities))

    else:
        _LOGGER.info("Falling back to legacy number entity creation from NUMBER_MAP")

        # Fallback to legacy method using NUMBER_MAP
        for key in NUMBER_MAP:
            number_limits = await api.get_param_limits(key)
            if number_limits is None:
                _LOGGER.info(
                    "Cannot add number entity: %s, numeric limits for this entity is None",
                    key,
                )
                continue

            if can_add(key, coordinator):
                entity_description = create_number_entity_description(
                    key, number_limits
                )
                entities.append(EconetNumber(entity_description, coordinator, api))
            else:
                _LOGGER.info(
                    "Cannot add number entity - availability key: %s does not exist",
                    key,
                )

    # Final check - if no entities were created, log a warning
    if not entities:
        _LOGGER.warning(
            "No number entities could be created. This may indicate that your device "
            "does not support the rmParamsData endpoint for dynamic entities, and "
            "the legacy NUMBER_MAP entities are not available on your device."
        )

    return async_add_entities(entities)
