"""Switch for Econet300."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import Econet300Api, EconetDataCoordinator
from .common_functions import (
    extract_device_group_from_name,
    generate_translation_key,
    get_lock_reason,
    get_on_off_values,
    get_parameter_type_from_category,
    is_information_category,
    is_parameter_locked,
    mixer_exists,
    requires_service_password,
    should_be_switch_entity,
    validate_parameter_data,
)
from .const import BOILER_CONTROL, DOMAIN, SERVICE_API, SERVICE_COORDINATOR
from .entity import EconetEntity, MenuCategoryEntity

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


class MenuCategorySwitchError(HomeAssistantError):
    """Raised when menu category switch operation fails."""


class MenuCategorySwitch(MenuCategoryEntity, SwitchEntity):  # type: ignore[misc]
    """Dynamic switch entity grouped by menu category.

    This entity type creates switch entities from parameters with binary enum
    data (2 values: ON/OFF, Yes/No, etc.), grouped into Home Assistant devices
    based on the ecoNET controller menu structure or name-based heuristics.

    Note: type: ignore[misc] is used because of entity_description type
    conflict between MenuCategoryEntity and SwitchEntity base classes.
    """

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        entity_description: SwitchEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        category_index: int,
        category_name: str,
        param_id: str,
        param_number: int,
        off_value: int,
        on_value: int,
    ):
        """Initialize a new MenuCategorySwitch entity.

        Args:
            entity_description: Entity description with key, name, etc.
            coordinator: Data coordinator for updates
            api: API instance for device info and API calls
            category_index: Index into rmCatsNames array
            category_name: Human-readable category name
            param_id: Parameter ID for value lookup in merged data
            param_number: Parameter number for API set_param calls
            off_value: API value representing OFF state
            on_value: API value representing ON state

        """
        super().__init__(
            entity_description, coordinator, api, category_index, category_name
        )
        self._param_id = param_id
        self._param_number = param_number
        self._off_value = off_value
        self._on_value = on_value
        self._attr_is_on: bool = False
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
        """Update is_on state from numeric value."""
        self._attr_is_on = value == self._on_value
        self._attr_available = True

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
                "Initialized MenuCategorySwitch %s: is_on=%s (locked=%s)",
                self.entity_description.key,
                self._attr_is_on,
                self._locked,
            )

    @property
    def icon(self) -> str | None:
        """Return icon for entity."""
        if self._locked:
            return "mdi:lock"  # Show lock icon for locked parameters
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including lock information."""
        attrs: dict[str, Any] = {}
        if self._locked:
            attrs["locked"] = True
            if self._lock_reason:
                attrs["lock_reason"] = self._lock_reason
        return attrs

    @staticmethod
    def _raise_switch_error(message: str) -> None:
        """Raise a MenuCategorySwitchError with the given message."""
        raise MenuCategorySwitchError(message)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Check if parameter is locked
        if self._locked:
            reason = self._lock_reason or "Parameter is locked"
            _LOGGER.warning(
                "Cannot turn ON %s: %s",
                self.entity_description.key,
                reason,
            )
            raise HomeAssistantError(f"Cannot turn ON: {reason}")

        try:
            _LOGGER.debug(
                "Turning ON %s (param %d = value %d)",
                self.entity_description.key,
                self._param_number,
                self._on_value,
            )

            success = await self.api.set_param(str(self._param_number), self._on_value)

            if success:
                self._attr_is_on = True
                self.async_write_ha_state()
                _LOGGER.info("%s turned ON", self.entity_description.key)
            else:
                self._raise_switch_error(
                    f"Failed to turn ON {self.entity_description.key}"
                )

        except MenuCategorySwitchError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to turn ON %s: %s", self.entity_description.key, e)
            raise MenuCategorySwitchError(f"Failed to turn ON: {e}") from e

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Check if parameter is locked
        if self._locked:
            reason = self._lock_reason or "Parameter is locked"
            _LOGGER.warning(
                "Cannot turn OFF %s: %s",
                self.entity_description.key,
                reason,
            )
            raise HomeAssistantError(f"Cannot turn OFF: {reason}")

        try:
            _LOGGER.debug(
                "Turning OFF %s (param %d = value %d)",
                self.entity_description.key,
                self._param_number,
                self._off_value,
            )

            success = await self.api.set_param(str(self._param_number), self._off_value)

            if success:
                self._attr_is_on = False
                self.async_write_ha_state()
                _LOGGER.info("%s turned OFF", self.entity_description.key)
            else:
                self._raise_switch_error(
                    f"Failed to turn OFF {self.entity_description.key}"
                )

        except MenuCategorySwitchError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to turn OFF %s: %s", self.entity_description.key, e)
            raise MenuCategorySwitchError(f"Failed to turn OFF: {e}") from e


def create_dynamic_switches(
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
) -> list[MenuCategorySwitch]:
    """Create dynamic switch entities from mergedData parameters with binary enum.

    Creates MenuCategorySwitch entities for parameters that have enum data
    with exactly 2 values (ON/OFF, Yes/No, etc.) and are editable.

    Args:
        coordinator: Data coordinator with mergedData
        api: API instance

    Returns:
        List of MenuCategorySwitch entities

    """
    entities: list[MenuCategorySwitch] = []

    if coordinator.data is None:
        return entities

    merged_data = coordinator.data.get("mergedData", {})
    if not merged_data or "parameters" not in merged_data:
        return entities

    parameters = merged_data.get("parameters", {})
    _LOGGER.debug("Checking %d parameters for switch entities", len(parameters))

    # Track created keys to avoid duplicates
    created_keys: set[str] = set()

    for param_id, param in parameters.items():
        if not isinstance(param, dict):
            continue

        # Validate parameter data first
        is_valid, error_msg = validate_parameter_data(param)
        if not is_valid:
            _LOGGER.debug(
                "Skipping invalid switch parameter %s: %s", param_id, error_msg
            )
            continue

        # Check if this should be a switch entity (includes lock check)
        if not should_be_switch_entity(param):
            continue

        # Log if parameter is locked (should not reach here due to should_be_switch_entity)
        if is_parameter_locked(param):
            lock_reason = get_lock_reason(param) or "Parameter is locked"
            _LOGGER.debug(
                "Skipping locked switch parameter %s (reason: %s)",
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

        # Get ON/OFF values
        on_off = get_on_off_values(enum_values, enum_first)
        if on_off is None:
            continue

        off_value, on_value = on_off

        # Get parameter info
        param_name = param.get("name", f"Switch {param_id}")
        param_key = param.get("key", f"switch_{param_id}")
        param_number = param.get("number")

        if param_number is None:
            continue

        # Avoid duplicates
        if param_key in created_keys:
            _LOGGER.debug("Skipping duplicate switch key: %s", param_key)
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
                    "Skipping switch '%s' - Mixer %d does not exist",
                    param_name,
                    mixer_num,
                )
                continue

        # Create entity description
        entity_description = SwitchEntityDescription(
            key=param_key,
            name=param_name,
            translation_key=generate_translation_key(param_name),
        )

        # Create entity
        entity = MenuCategorySwitch(
            entity_description=entity_description,
            coordinator=coordinator,
            api=api,
            category_index=category_index,
            category_name=category_name,
            param_id=param_id,
            param_number=param_number,
            off_value=off_value,
            on_value=on_value,
        )

        # Hide service/advanced params by default per HA documentation
        param_type = get_parameter_type_from_category(category_name)
        if param_type in ("service", "advanced"):
            entity._attr_entity_registry_visible_default = False  # noqa: SLF001

        # Disable params requiring service password (pass_index > 0)
        if requires_service_password(param):
            entity._attr_entity_registry_enabled_default = False  # noqa: SLF001

        entities.append(entity)
        created_keys.add(param_key)

        _LOGGER.debug(
            "Created dynamic switch: %s (param %d) -> %s (off=%d, on=%d, enabled_default=%s)",
            param_name,
            param_number,
            category_name,
            off_value,
            on_value,
            getattr(entity, "_attr_entity_registry_enabled_default", True),
        )

    _LOGGER.info("Created %d dynamic switch entities", len(entities))
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

    _LOGGER.info("Adding %d total switch entities", len(entities))
    async_add_entities(entities)
