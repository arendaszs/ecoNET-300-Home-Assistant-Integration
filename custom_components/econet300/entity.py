"""Base econet entity class."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Econet300Api
from .common import EconetDataCoordinator
from .const import (
    DEVICE_INFO_BUFFER_NAME,
    DEVICE_INFO_CONTROLLER_NAME,
    DEVICE_INFO_ECOSTER_NAME,
    DEVICE_INFO_HUW_NAME,
    DEVICE_INFO_LAMBDA_NAME,
    DEVICE_INFO_MANUFACTURER,
    DEVICE_INFO_MIXER_NAME,
    DEVICE_INFO_MODEL,
    DEVICE_INFO_SOLAR_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _create_base_device_info(
    api: Econet300Api,
    identifier: str,
    name: str,
    parent_device_id: str | None = None,
    include_model_id: bool = False,
    include_hw_version: bool = False,
) -> DeviceInfo:
    """Create base DeviceInfo with common fields.

    Args:
        api: Econet300Api instance
        identifier: Unique device identifier
        name: Device display name
        parent_device_id: Parent device identifier for via_device
        include_model_id: Whether to include model_id
        include_hw_version: Whether to include hw_version

    Returns:
        DeviceInfo with common fields populated

    """
    device_info = {
        "identifiers": {(DOMAIN, identifier)},
        "name": name,
        "manufacturer": DEVICE_INFO_MANUFACTURER,
        "model": DEVICE_INFO_MODEL,
        "configuration_url": api.host,
        "sw_version": api.sw_rev,
    }

    if parent_device_id:
        device_info["via_device"] = (DOMAIN, parent_device_id)

    if include_model_id:
        device_info["model_id"] = api.model_id

    if include_hw_version:
        device_info["hw_version"] = api.hw_ver

    return DeviceInfo(**device_info)


class EconetEntity(CoordinatorEntity):
    """Represents EconetEntity."""

    api: Econet300Api
    _attr_has_entity_name = True  # Required for icon translations from icons.json
    # Note: entity_description type is defined by child classes (NumberEntity, SensorEntity, etc.)
    # to avoid MRO conflicts when multiple inheritance is used

    def __init__(self, coordinator: EconetDataCoordinator, api: Econet300Api):
        """Initialize the EconetEntity."""
        super().__init__(coordinator)
        self.api = api

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the entity."""
        return f"{self.api.uid}-{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return _create_base_device_info(
            api=self.api,
            identifier=self.api.uid,
            name=DEVICE_INFO_CONTROLLER_NAME,
            include_model_id=True,
            include_hw_version=True,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Update EconetEntity, entity name: %s", self.entity_description.name
        )

        # Safety check: ensure coordinator data exists
        if self.coordinator.data is None:
            _LOGGER.info("Coordinator data is None, skipping update")
            return

        # Debug: Check what's available in each data source
        sys_params = self.coordinator.data.get("sysParams", {})
        reg_params = self.coordinator.data.get("regParams", {})
        params_edits = self.coordinator.data.get("paramsEdits", {})
        merged_data = self.coordinator.data.get("mergedData", {})

        # Safety check: ensure all data sources are always dicts
        if sys_params is None:
            sys_params = {}
            _LOGGER.info("sysParams was None, defaulting to empty dict")
        if reg_params is None:
            reg_params = {}
            _LOGGER.info("regParams was None, defaulting to empty dict")
        if params_edits is None:
            params_edits = {}
            _LOGGER.info("paramsEdits was None, defaulting to empty dict")
        if merged_data is None:
            merged_data = {}
            _LOGGER.debug("mergedData was None, defaulting to empty dict")

        # Check if this is a dynamic entity - has param_id in description
        param_id = getattr(self.entity_description, "param_id", None)
        is_dynamic_entity = param_id is not None
        merged_parameters = merged_data.get("parameters", {}) if merged_data else {}

        _LOGGER.debug(
            "Looking for key '%s' (param_id=%s) in data sources - sysParams: %s, regParams: %s, paramsEdits: %s, is_dynamic: %s",
            self.entity_description.key,
            param_id,
            self.entity_description.key in sys_params,
            self.entity_description.key in reg_params,
            self.entity_description.key in params_edits,
            is_dynamic_entity,
        )

        value = None
        if is_dynamic_entity and param_id:
            # For dynamic entities, use param_id to look up in mergedData
            param_data = None

            # Try param_id as-is first (string)
            if param_id in merged_parameters:
                param_data = merged_parameters[param_id]
            # Try string version of param_id
            elif str(param_id) in merged_parameters:
                param_data = merged_parameters[str(param_id)]

            if param_data:
                value = param_data.get("value")
                _LOGGER.debug(
                    "Found dynamic entity value in mergedData[%s]: %s", param_id, value
                )
            else:
                _LOGGER.debug(
                    "Dynamic entity param_id %s not found in mergedData", param_id
                )
        elif self.entity_description.key in sys_params:
            value = sys_params[self.entity_description.key]
            _LOGGER.debug("Found in sysParams: %s", value)
        elif self.entity_description.key in reg_params:
            value = reg_params[self.entity_description.key]
            _LOGGER.debug("Found in regParams: %s", value)
        elif self.entity_description.key in params_edits:
            value = params_edits[self.entity_description.key]
            _LOGGER.debug("Found in paramsEdits: %s", value)

        if value is None:
            _LOGGER.debug(
                "Value for key %s is None - entity will not be updated",
                self.entity_description.key,
            )
            return

        _LOGGER.debug(
            "Updating state for key: %s with value: %s - calling _sync_state",
            self.entity_description.key,
            value,
        )
        # Call _sync_state to update entity state
        self._sync_state(value)

    async def async_added_to_hass(self):
        """Handle added to hass."""
        _LOGGER.debug(
            "Entering async_added_to_hass for entity: %s",
            self.entity_description.key,
        )
        _LOGGER.debug("Added to HASS: %s", self.entity_description)
        _LOGGER.debug("Coordinator: %s", self.coordinator)

        # Check if the coordinator has a 'data' attribute
        if "data" not in dir(self.coordinator):
            _LOGGER.error("Coordinator object does not have a 'data' attribute")
            # Still register for updates - data may become available later
            await super().async_added_to_hass()
            return

        # Safety check: ensure coordinator data exists
        if self.coordinator.data is None:
            _LOGGER.info(
                "Coordinator data is None for %s, will update on next refresh",
                self.entity_description.key,
            )
            # Still register for updates - data may become available later
            await super().async_added_to_hass()
            return

        # Retrieve sysParams and regParams paramsEdits data
        sys_params = self.coordinator.data.get("sysParams", {})
        reg_params = self.coordinator.data.get("regParams", {})
        params_edits = self.coordinator.data.get("paramsEdits", {})
        merged_data = self.coordinator.data.get("mergedData", {})

        # Safety check: ensure all data sources are always dicts
        if sys_params is None:
            sys_params = {}
            _LOGGER.info(
                "async_added_to_hass: sysParams was None, defaulting to empty dict"
            )
        if reg_params is None:
            reg_params = {}
            _LOGGER.info(
                "async_added_to_hass: regParams was None, defaulting to empty dict"
            )
        if params_edits is None:
            params_edits = {}
            _LOGGER.info(
                "async_added_to_hass: paramsEdits was None, defaulting to empty dict"
            )
        if merged_data is None:
            merged_data = {}
            _LOGGER.debug(
                "async_added_to_hass: mergedData was None, defaulting to empty dict"
            )
        _LOGGER.debug(
            "async_added_to_hass: sysParams=%d, regParams=%d, paramsEdits=%d params",
            len(sys_params) if sys_params else 0,
            len(reg_params) if reg_params else 0,
            len(params_edits) if params_edits else 0,
        )

        # Check the available keys in all sources
        sys_keys = sys_params.keys() if sys_params is not None else []
        reg_keys = reg_params.keys() if reg_params is not None else []
        edit_keys = params_edits.keys() if params_edits is not None else []
        merged_keys = merged_data.get("parameters", {}).keys() if merged_data else []
        _LOGGER.debug("Available keys in sysParams: %s", sys_keys)
        _LOGGER.debug("Available keys in regParams: %s", reg_keys)
        _LOGGER.debug("Available keys in paramsEdits: %s", edit_keys)
        _LOGGER.debug("Available keys in mergedData parameters: %s", merged_keys)

        # Expected key from entity_description
        expected_key = self.entity_description.key
        _LOGGER.debug("Expected key: %s", expected_key)

        # Check if this is a dynamic entity - has param_id in description
        param_id = getattr(self.entity_description, "param_id", None)
        is_dynamic_entity = param_id is not None
        merged_parameters = merged_data.get("parameters", {}) if merged_data else {}

        # Retrieve the value from appropriate data source
        value = None
        if is_dynamic_entity and param_id:
            # For dynamic entities, use param_id to look up in mergedData
            param_data = None

            # Try param_id as-is first (string)
            if param_id in merged_parameters:
                param_data = merged_parameters[param_id]
            # Try string version of param_id
            elif str(param_id) in merged_parameters:
                param_data = merged_parameters[str(param_id)]

            if param_data:
                value = param_data.get("value")
                _LOGGER.debug(
                    "Found dynamic entity initial value in mergedData[%s]: %s",
                    param_id,
                    value,
                )
            else:
                _LOGGER.debug(
                    "Dynamic entity param_id %s not found in mergedData", param_id
                )
        else:
            # For legacy entities, use standard logic
            value = (
                sys_params.get(expected_key)
                if sys_params.get(expected_key) is not None
                else (
                    reg_params.get(expected_key)
                    if reg_params.get(expected_key) is not None
                    else params_edits.get(expected_key)
                )
            )

        # ALWAYS call super() to register for coordinator updates
        # This ensures the entity receives future updates even if initial value is missing
        await super().async_added_to_hass()

        if value is not None:
            _LOGGER.debug("Found initial value for entity %s: %s", expected_key, value)
            # Call _sync_state to update entity state with initial value
            self._sync_state(value)
        else:
            _LOGGER.debug(
                "No initial value found for entity %s. Entity will update on next coordinator refresh. "
                "Available sysParams keys: %s, regParams keys: %s, paramsEdits keys: %s",
                expected_key,
                sys_keys,
                reg_keys,
                edit_keys,
            )

    def _sync_state(self, value) -> None:
        """Update entity state with the provided value.

        This method is called when the coordinator provides new data.
        Child classes should override this to handle entity-specific state updates.
        """
        # Base implementation does nothing - child classes handle state updates


class MixerEntity(EconetEntity):
    """Represents MixerEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize the MixerEntity."""
        self.entity_description = description
        self.api = api
        self._idx = idx
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return _create_base_device_info(
            api=self.api,
            identifier=f"{self.api.uid}-mixer-{self._idx}",
            name=f"{DEVICE_INFO_MIXER_NAME}{self._idx}",
            parent_device_id=self.api.uid,
            include_model_id=True,
        )


class LambdaEntity(EconetEntity):
    """Initialize the LambdaEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize the LambdaEntity."""
        self.entity_description = description
        self.api = api
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return _create_base_device_info(
            api=self.api,
            identifier=f"{self.api.uid}-lambda",
            name=DEVICE_INFO_LAMBDA_NAME,
            parent_device_id=self.api.uid,
        )


class EcoSterEntity(EconetEntity):
    """Represents EcoSterEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize the EcoSterEntity."""
        self.entity_description = description
        self.api = api
        self._idx = idx
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return _create_base_device_info(
            api=self.api,
            identifier=f"{self.api.uid}-ecoster-{self._idx}",
            name=f"{DEVICE_INFO_ECOSTER_NAME} {self._idx}",
            parent_device_id=self.api.uid,
            include_model_id=True,
        )


def get_device_info_for_component(
    component: str, api: Econet300Api, mixer_idx: int | None = None
) -> DeviceInfo:
    """Return DeviceInfo for a specific component.

    Creates device identifiers based on component type, allowing entities
    to be grouped under their respective physical components in Home Assistant.

    Args:
        component: Component identifier ("boiler", "huw", "mixer_1", etc.)
        api: Econet300Api instance for device information
        mixer_idx: Optional mixer index (1-4) for mixer components

    Returns:
        DeviceInfo for the specified component

    """
    # Main boiler device (parent of all others)
    if component == "boiler":
        return _create_base_device_info(
            api=api,
            identifier=api.uid,
            name=DEVICE_INFO_CONTROLLER_NAME,
            include_model_id=True,
            include_hw_version=True,
        )

    # HUW Tank device
    if component == "huw":
        return _create_base_device_info(
            api=api,
            identifier=f"{api.uid}-huw",
            name=DEVICE_INFO_HUW_NAME,
            parent_device_id=api.uid,
        )

    # Mixer devices (1-4)
    if component.startswith("mixer_"):
        idx = mixer_idx or int(component.split("_")[1])
        return _create_base_device_info(
            api=api,
            identifier=f"{api.uid}-mixer-{idx}",
            name=f"{DEVICE_INFO_MIXER_NAME}{idx}",
            parent_device_id=api.uid,
            include_model_id=True,
        )

    # Lambda sensor device
    if component == "lambda":
        return _create_base_device_info(
            api=api,
            identifier=f"{api.uid}-lambda",
            name=DEVICE_INFO_LAMBDA_NAME,
            parent_device_id=api.uid,
        )

    # Buffer device
    if component == "buffer":
        return _create_base_device_info(
            api=api,
            identifier=f"{api.uid}-buffer",
            name=DEVICE_INFO_BUFFER_NAME,
            parent_device_id=api.uid,
        )

    # Solar device
    if component == "solar":
        return _create_base_device_info(
            api=api,
            identifier=f"{api.uid}-solar",
            name=DEVICE_INFO_SOLAR_NAME,
            parent_device_id=api.uid,
        )

    # Default to main boiler device
    return _create_base_device_info(
        api=api,
        identifier=api.uid,
        name=DEVICE_INFO_CONTROLLER_NAME,
        include_model_id=True,
        include_hw_version=True,
    )
