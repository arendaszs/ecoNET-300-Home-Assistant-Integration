"""Sensor for Econet300."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Econet300Api
from .common import EconetDataCoordinator
from .common_functions import (
    camel_to_snake,
    extract_device_group_from_name,
    is_information_category,
)
from .const import (
    DOMAIN,
    ENTITY_CATEGORY,
    ENTITY_PRECISION,
    ENTITY_SENSOR_DEVICE_CLASS_MAP,
    ENTITY_UNIT_MAP,
    ENTITY_VALUE_PROCESSOR,
    SENSOR_MAP_KEY,
    SENSOR_MIXER_KEY,
    SERVICE_API,
    SERVICE_COORDINATOR,
    STATE_CLASS_MAP,
)
from .entity import (
    EconetEntity,
    EcoSterEntity,
    LambdaEntity,
    MenuCategoryEntity,
    MixerEntity,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EconetSensorEntityDescription(SensorEntityDescription):
    """Describes ecoNET sensor entity."""

    process_val: Callable[[Any], Any] = lambda x: x  # noqa: E731


class EconetSensor(EconetEntity, SensorEntity):
    """Represents an ecoNET sensor entity."""

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        entity_description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize a new ecoNET sensor entity."""
        self.entity_description = entity_description
        self.api = api
        self._attr_native_value = None
        super().__init__(coordinator, api)

    def _sync_state(self, value) -> None:
        """Synchronize the state of the sensor entity."""
        self._attr_native_value = self.entity_description.process_val(value)
        self.async_write_ha_state()


class MixerSensor(MixerEntity, SensorEntity):
    """Mixer sensor class."""

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize a new instance of the MixerSensor class."""
        super().__init__(description, coordinator, api, idx)
        self._attr_native_value = None

    def _sync_state(self, value) -> None:
        """Synchronize the state of the sensor entity."""
        self._attr_native_value = self.entity_description.process_val(value)
        self.async_write_ha_state()


class LambdaSensors(LambdaEntity, SensorEntity):
    """Lambda sensor class."""

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize a new instance of the LambdaSensors class."""
        super().__init__(description, coordinator, api)
        self._attr_native_value = None

    def _sync_state(self, value) -> None:
        """Synchronize the state of the sensor entity."""
        self._attr_native_value = self.entity_description.process_val(value)
        self.async_write_ha_state()


class EcoSterSensor(EcoSterEntity, SensorEntity):
    """EcoSter sensor class."""

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize the EcoSter sensor."""
        self.entity_description = description
        self.api = api
        self._idx = idx
        super().__init__(description, coordinator, api, idx)

    def _sync_state(self, value) -> None:
        """Sync state."""
        _LOGGER.debug("EcoSter sensor sync state: %s", value)
        self._attr_native_value = self.entity_description.process_val(value)
        self.async_write_ha_state()


class InformationDynamicSensor(EconetEntity, SensorEntity):
    """Dynamic sensor entity for Information category parameters (read-only)."""

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        entity_description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        param_number: int,
    ):
        """Initialize a new Information dynamic sensor entity.

        Args:
            entity_description: Entity description
            coordinator: Data coordinator
            api: API instance
            param_number: Parameter number from merged data

        """
        self.entity_description = entity_description
        self.api = api
        self._param_number = param_number
        self._attr_native_value = None
        super().__init__(coordinator, api)

    def _sync_state(self, value) -> None:
        """Synchronize the state of the Information sensor entity."""
        _LOGGER.debug(
            "InformationDynamicSensor _sync_state for entity %s: %s",
            self.entity_description.key,
            value,
        )

        # Handle both dict and direct value
        if isinstance(value, dict) and "value" in value:
            val = value.get("value")
            self._attr_native_value = float(val) if val is not None else None
        elif isinstance(value, (int, float, str)) and value is not None:
            try:
                self._attr_native_value = float(value)
            except (ValueError, TypeError):
                self._attr_native_value = value
        else:
            self._attr_native_value = None

        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        if self.coordinator.data is None:
            return None

        merged_data = self.coordinator.data.get("mergedData", {})
        if not merged_data:
            return None

        merged_parameters = merged_data.get("parameters", {})
        if not merged_parameters:
            return None

        # Find parameter by number
        for param in merged_parameters.values():
            if isinstance(param, dict) and param.get("number") == self._param_number:
                param_value = param.get("value")
                if param_value is not None:
                    try:
                        return float(param_value)
                    except (ValueError, TypeError):
                        return param_value
                break

        return None


class MenuCategorySensor(MenuCategoryEntity, SensorEntity):  # type: ignore[misc]
    """Dynamic sensor entity grouped by menu category.

    This entity type creates sensor entities that are grouped into
    Home Assistant devices based on the ecoNET controller menu structure.
    Each unique category index creates a separate device.

    Note: type: ignore[misc] is used because of entity_description type
    conflict between MenuCategoryEntity and SensorEntity base classes.
    """

    entity_description: EconetSensorEntityDescription

    def __init__(
        self,
        entity_description: EconetSensorEntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        category_index: int,
        category_name: str,
        param_id: str,
    ):
        """Initialize a new MenuCategorySensor.

        Args:
            entity_description: Entity description with key, name, etc.
            coordinator: Data coordinator for updates
            api: API instance for device info
            category_index: Index into rmCatsNames array
            category_name: Human-readable category name from rmCatsNames
            param_id: Parameter ID for looking up value in merged data

        """
        super().__init__(
            entity_description, coordinator, api, category_index, category_name
        )
        self._param_id = param_id
        self._attr_native_value: float | str | None = None

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
                self.async_write_ha_state()

    def _sync_state(self, value) -> None:
        """Sync the state of the menu category sensor entity."""
        _LOGGER.debug(
            "MenuCategorySensor _sync_state for entity %s (param_id=%s): %s",
            self.entity_description.key,
            self._param_id,
            value,
        )
        if value is not None:
            try:
                self._attr_native_value = float(value)
            except (ValueError, TypeError):
                # Keep as string if can't convert to float
                self._attr_native_value = value

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
                _LOGGER.debug(
                    "Initialized MenuCategorySensor %s with value %s",
                    self.entity_description.key,
                    value,
                )


def create_sensor_entity_description(key: str) -> EconetSensorEntityDescription:
    """Create ecoNET300 sensor entity based on supplied key."""
    _LOGGER.debug("Creating sensor entity description for key: %s", key)
    entity_description = EconetSensorEntityDescription(
        key=key,
        device_class=ENTITY_SENSOR_DEVICE_CLASS_MAP.get(key, None),
        entity_category=ENTITY_CATEGORY.get(key, None),
        translation_key=camel_to_snake(key),
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(key, None),
        state_class=STATE_CLASS_MAP.get(key, SensorStateClass.MEASUREMENT),
        suggested_display_precision=ENTITY_PRECISION.get(key, 0),
        process_val=ENTITY_VALUE_PROCESSOR.get(key, lambda x: x),  # noqa: E731
    )
    _LOGGER.debug("Created sensor entity description: %s", entity_description)
    return entity_description


def create_controller_sensors(
    coordinator: EconetDataCoordinator, api: Econet300Api
) -> list[EconetSensor]:
    """Create controller sensor entities."""
    entities: list[EconetSensor] = []

    # Get the system and regular parameters from the coordinator
    if coordinator.data is None:
        _LOGGER.info("Coordinator data is None, no controller sensors will be created")
        return entities

    data_regParams = coordinator.data.get("regParams", {})
    if data_regParams is None:
        data_regParams = {}

    data_sysParams = coordinator.data.get("sysParams", {})
    if data_sysParams is None:
        data_sysParams = {}

    # Extract the controllerID from sysParams
    controller_id = data_sysParams.get("controllerID")

    # Always use default sensor mapping for all controllers
    sensor_keys = SENSOR_MAP_KEY["_default"].copy()
    if controller_id and controller_id in SENSOR_MAP_KEY:
        _LOGGER.info(
            "ControllerID '%s' found in mapping, but using default sensor mapping",
            controller_id,
        )
    else:
        _LOGGER.info(
            "ControllerID '%s' not found in mapping, using default sensor mapping",
            controller_id if controller_id else "None",
        )

    # Always filter out ecoSTER sensors from controller sensors since they are created as separate devices
    ecoSTER_sensors = SENSOR_MAP_KEY.get("ecoSter", set())
    sensor_keys = sensor_keys - ecoSTER_sensors
    _LOGGER.info(
        "Filtered out ecoSTER sensors from controller sensors: %s", ecoSTER_sensors
    )

    # Iterate through the selected keys and create sensors if valid data is found
    for data_key in sensor_keys:
        _LOGGER.debug(
            "Processing entity sensor data_key: %s from regParams & sysParams", data_key
        )
        if data_key in data_regParams:
            # Check if the value is not null before creating the sensor
            if data_regParams.get(data_key) is None:
                _LOGGER.info(
                    "%s in regParams is null, sensor will not be created.", data_key
                )
                continue
            entity = EconetSensor(
                create_sensor_entity_description(data_key), coordinator, api
            )
            entities.append(entity)
            _LOGGER.debug(
                "Created and appended sensor entity from regParams: %s", entity
            )
        elif data_key in data_sysParams:
            if data_sysParams.get(data_key) is None:
                _LOGGER.info(
                    "%s in sysParams sensor value is null, sensor will not be created.",
                    data_key,
                )
                continue
            entity = EconetSensor(
                create_sensor_entity_description(data_key), coordinator, api
            )
            entities.append(entity)
            _LOGGER.debug(
                "Created and appended sensor entity from sysParams: %s", entity
            )
        else:
            _LOGGER.debug(
                "Key: %s is not mapped in regParams or sysParams, sensor entity will not be added.",
                data_key,
            )
    _LOGGER.info("Total sensor entities created: %d", len(entities))
    return entities


def can_add_mixer(key: str, coordinator: EconetDataCoordinator) -> bool:
    """Check if a mixer can be added."""
    if coordinator.data is None:
        return False

    reg_params = coordinator.data.get("regParams")
    if reg_params is None:
        reg_params = {}

    _LOGGER.debug(
        "Checking if mixer can be added for key: %s, data %s",
        key,
        reg_params,
    )
    return coordinator.has_reg_data(key) and reg_params.get(key) is not None


def create_mixer_sensor_entity_description(key: str) -> EconetSensorEntityDescription:
    """Create a sensor entity description for a mixer."""
    _LOGGER.debug("Creating Mixer entity sensor description for key: %s", key)
    entity_description = EconetSensorEntityDescription(
        key=key,
        translation_key=camel_to_snake(key),
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(key, None),
        state_class=STATE_CLASS_MAP.get(key, SensorStateClass.MEASUREMENT),
        device_class=ENTITY_SENSOR_DEVICE_CLASS_MAP.get(key, None),
        suggested_display_precision=ENTITY_PRECISION.get(key, 0),
        process_val=ENTITY_VALUE_PROCESSOR.get(key, lambda x: x),  # noqa: E731
    )
    _LOGGER.debug("Created Mixer entity description: %s", entity_description)
    return entity_description


def create_mixer_sensors(
    coordinator: EconetDataCoordinator, api: Econet300Api
) -> list[MixerSensor]:
    """Create individual sensor descriptions for mixer sensors."""
    entities: list[MixerSensor] = []

    if coordinator.data is None:
        _LOGGER.info("Coordinator data is None, no mixer sensors will be created")
        return entities

    reg_params = coordinator.data.get("regParams")
    if reg_params is None:
        reg_params = {}

    for key, mixer_keys in SENSOR_MIXER_KEY.items():
        # Check if all required mixer keys have valid (non-null) values
        if any(reg_params.get(mixer_key) is None for mixer_key in mixer_keys):
            _LOGGER.info("Mixer: %s will not be created due to invalid data.", key)
            continue

        # Create sensors for this mixer
        for mixer_key in mixer_keys:
            mixer_sensor_entity = create_mixer_sensor_entity_description(mixer_key)
            entities.append(MixerSensor(mixer_sensor_entity, coordinator, api, key))
            _LOGGER.debug("Added Mixer: %s, Sensor: %s", key, mixer_key)

    return entities


# Create Lambda sensor entity description and Lambda sensor


def create_lambda_sensor_entity_description(key: str) -> EconetSensorEntityDescription:
    """Create a sensor entity description for a Lambda."""
    _LOGGER.debug("Creating Lambda entity sensor description for key: %s", key)
    entity_description = EconetSensorEntityDescription(
        key=key,
        translation_key=camel_to_snake(key),
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(key, None),
        state_class=STATE_CLASS_MAP.get(key, None),
        device_class=ENTITY_SENSOR_DEVICE_CLASS_MAP.get(key, None),
        suggested_display_precision=ENTITY_PRECISION.get(key, 0),
        process_val=ENTITY_VALUE_PROCESSOR.get(key, lambda x: x / 10),  # noqa: E731
    )
    _LOGGER.debug("Created LambdaSensors entity description: %s", entity_description)
    return entity_description


def create_lambda_sensors(coordinator: EconetDataCoordinator, api: Econet300Api):
    """Create controller sensor entities."""
    entities: list[LambdaSensors] = []
    if coordinator.data is None:
        _LOGGER.info("Coordinator data is None, no lambda sensors will be created")
        return entities

    sys_params = coordinator.data.get("sysParams", {})
    if sys_params is None:
        sys_params = {}

    # Check if moduleLambdaSoftVer is None
    if sys_params.get("moduleLambdaSoftVer") is None:
        _LOGGER.info("moduleLambdaSoftVer is None, no lambda sensors will be created")
        return entities

    coordinator_data = coordinator.data.get("regParams", {})
    if coordinator_data is None:
        coordinator_data = {}

    for data_key in SENSOR_MAP_KEY["lambda"]:
        if data_key in coordinator_data:
            entities.append(
                LambdaSensors(
                    create_lambda_sensor_entity_description(data_key), coordinator, api
                )
            )
            _LOGGER.debug(
                "Key: %s mapped, lamda sensor entity will be added",
                data_key,
            )
            continue
        _LOGGER.debug(
            "Key: %s is not mapped, lamda sensor entity will not be added",
            data_key,
        )

    return entities


def create_ecoster_sensor_entity_description(key: str) -> EconetSensorEntityDescription:
    """Create a sensor entity description for an ecoSTER sensor."""
    _LOGGER.debug("Creating ecoSTER entity sensor description for key: %s", key)
    entity_description = EconetSensorEntityDescription(
        key=key,
        translation_key=camel_to_snake(key),
        native_unit_of_measurement=ENTITY_UNIT_MAP.get(key, None),
        state_class=STATE_CLASS_MAP.get(key, SensorStateClass.MEASUREMENT),
        device_class=ENTITY_SENSOR_DEVICE_CLASS_MAP.get(key, None),
        suggested_display_precision=ENTITY_PRECISION.get(key, 0),
        process_val=ENTITY_VALUE_PROCESSOR.get(key, lambda x: x),  # noqa: E731
    )
    _LOGGER.debug("Created ecoSTER entity description: %s", entity_description)
    return entity_description


def create_ecoster_sensors(coordinator: EconetDataCoordinator, api: Econet300Api):
    """Create ecoSTER sensor entities."""
    entities: list[EcoSterSensor] = []
    if coordinator.data is None:
        _LOGGER.info("Coordinator data is None, no ecoSTER sensors will be created")
        return entities

    sys_params = coordinator.data.get("sysParams", {})
    if sys_params is None:
        sys_params = {}

    # Check if moduleEcoSTERSoftVer is None
    if sys_params.get("moduleEcoSTERSoftVer") is None:
        _LOGGER.info("moduleEcoSTERSoftVer is None, no ecoSTER sensors will be created")
        return entities

    coordinator_data = coordinator.data.get("regParams", {})
    if coordinator_data is None:
        coordinator_data = {}

    # Create ecoSTER sensors for each thermostat (1-8)
    for thermostat_idx in range(1, 9):  # 1-8
        # Create temperature sensor
        temp_key = f"ecoSterTemp{thermostat_idx}"
        if temp_key in coordinator_data and coordinator_data.get(temp_key) is not None:
            entities.append(
                EcoSterSensor(
                    create_ecoster_sensor_entity_description(temp_key),
                    coordinator,
                    api,
                    thermostat_idx,
                )
            )
            _LOGGER.debug("Created ecoSTER temperature sensor: %s", temp_key)

        # Create setpoint sensor
        set_temp_key = f"ecoSterSetTemp{thermostat_idx}"
        if (
            set_temp_key in coordinator_data
            and coordinator_data.get(set_temp_key) is not None
        ):
            entities.append(
                EcoSterSensor(
                    create_ecoster_sensor_entity_description(set_temp_key),
                    coordinator,
                    api,
                    thermostat_idx,
                )
            )
            _LOGGER.debug("Created ecoSTER setpoint sensor: %s", set_temp_key)

        # Create mode sensor
        mode_key = f"ecoSterMode{thermostat_idx}"
        if mode_key in coordinator_data and coordinator_data.get(mode_key) is not None:
            entities.append(
                EcoSterSensor(
                    create_ecoster_sensor_entity_description(mode_key),
                    coordinator,
                    api,
                    thermostat_idx,
                )
            )
            _LOGGER.debug("Created ecoSTER mode sensor: %s", mode_key)

    _LOGGER.info("Created %d ecoSTER sensors", len(entities))
    return entities


def create_dynamic_information_sensor_entity_description(
    param_id: str, param: dict[str, Any]
) -> EconetSensorEntityDescription:
    """Create sensor entity description for Information category parameter.

    Args:
        param_id: Parameter ID
        param: Parameter dictionary from merged data

    Returns:
        Sensor entity description

    """
    param_name = param.get("name", f"Parameter {param_id}")
    unit_name = param.get("unit_name", "")
    param_key = param.get("key", f"info_{param_id}")

    return EconetSensorEntityDescription(
        key=f"info_{param_key}",
        name=param_name,
        translation_key=param_key,
        native_unit_of_measurement=unit_name if unit_name else None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1 if unit_name else 0,
    )


def create_information_sensors(
    merged_data: dict[str, Any],
    coordinator: EconetDataCoordinator,
    api: Econet300Api,
) -> list[SensorEntity]:
    """Create read-only sensor entities for Information category parameters.

    Creates MenuCategorySensor entities grouped by menu category index when
    available, falling back to InformationDynamicSensor for parameters
    without category index.

    Args:
        merged_data: Merged parameter data
        coordinator: Data coordinator
        api: API instance

    Returns:
        List of Information sensor entities (MenuCategorySensor or InformationDynamicSensor)

    """
    entities: list[SensorEntity] = []

    if not merged_data or "parameters" not in merged_data:
        return entities

    parameters = merged_data.get("parameters", {})
    _LOGGER.info(
        "Creating Information sensor entities from %d parameters", len(parameters)
    )

    # Track created entity keys to avoid duplicates
    created_entity_keys: set[str] = set()

    for param_id, param in parameters.items():
        if not isinstance(param, dict):
            continue

        # Get parameter key - this is what determines uniqueness
        param_key = param.get("key", f"info_{param_id}")

        # Skip if we've already created an entity for this parameter key
        if param_key in created_entity_keys:
            _LOGGER.debug(
                "Skipping parameter %s - sensor for key '%s' already created",
                param_id,
                param_key,
            )
            continue

        # Get all categories for this parameter
        categories = param.get("categories", [param.get("category", "")])
        if not categories:
            continue

        # Check if any category is Information
        has_information_category = any(
            is_information_category(cat) for cat in categories
        )

        if not has_information_category:
            continue

        # Create sensor entity for Information category
        param_number = param.get("number")
        if param_number is None:
            continue

        entity_description = create_dynamic_information_sensor_entity_description(
            param_id, param
        )

        # Get category info for menu-based device grouping
        category_index = param.get("category_index")
        category_indices = param.get("category_indices", [])

        # First, try to extract device group from parameter name (for better grouping)
        param_name = param.get("name", "")
        name_based_index, name_based_category = extract_device_group_from_name(
            param_name, for_information=True
        )

        # Use name-based grouping if found, otherwise fall back to structure-based
        info_category_index = name_based_index
        info_category_name = name_based_category

        if info_category_index is None:
            # Fall back to finding the first Information category from structure
            for i, cat in enumerate(categories):
                if is_information_category(cat):
                    # Use the corresponding index from category_indices
                    if i < len(category_indices):
                        info_category_index = category_indices[i]
                    elif category_index is not None:
                        info_category_index = category_index
                    info_category_name = cat
                    break

        # Create entity - use MenuCategorySensor if we have category info
        entity: SensorEntity
        if info_category_index is not None and info_category_name:
            entity = MenuCategorySensor(
                entity_description,
                coordinator,
                api,
                info_category_index,
                info_category_name,
                param_id,
            )
            _LOGGER.debug(
                "Created MenuCategorySensor: %s (param %d, category: %s, index: %d)",
                entity_description.key,
                param_number,
                info_category_name,
                info_category_index,
            )
        else:
            entity = InformationDynamicSensor(
                entity_description, coordinator, api, param_number
            )
            _LOGGER.debug(
                "Created InformationDynamicSensor: %s (param %d, categories: %s)",
                entity_description.key,
                param_number,
                categories,
            )

        entities.append(entity)

        # Track parameter key to avoid duplicates
        created_entity_keys.add(param_key)

    _LOGGER.info("Created %d Information sensor entities", len(entities))
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""

    def gather_entities(
        coordinator: EconetDataCoordinator, api: Econet300Api
    ) -> list[SensorEntity]:
        """Collect all sensor entities."""
        entities: list[SensorEntity] = []
        _LOGGER.info("Starting entity collection for sensors...")

        # Gather sensors dynamically based on the controller
        controller_sensors = create_controller_sensors(coordinator, api)
        _LOGGER.info("Collected %d controller sensors", len(controller_sensors))
        entities.extend(controller_sensors)

        # Gather mixer sensors
        mixer_sensors = create_mixer_sensors(coordinator, api)
        _LOGGER.info("Collected %d mixer sensors", len(mixer_sensors))
        entities.extend(mixer_sensors)

        # Gather lambda sensors
        lambda_sensors = create_lambda_sensors(coordinator, api)
        _LOGGER.info("Collected %d lambda sensors", len(lambda_sensors))
        entities.extend(lambda_sensors)

        # Gather ecoSTER sensors
        ecoster_sensors = create_ecoster_sensors(coordinator, api)
        _LOGGER.info("Collected %d ecoSTER sensors", len(ecoster_sensors))
        entities.extend(ecoster_sensors)

        # Gather Information category sensors (read-only from merged data)
        if coordinator.data:
            merged_data = coordinator.data.get("mergedData")
            if merged_data:
                information_sensors = create_information_sensors(
                    merged_data, coordinator, api
                )
                _LOGGER.info(
                    "Collected %d Information sensors", len(information_sensors)
                )
                entities.extend(information_sensors)

        _LOGGER.info("Total entities collected: %d", len(entities))
        return entities

    coordinator = hass.data[DOMAIN][entry.entry_id][SERVICE_COORDINATOR]
    api = hass.data[DOMAIN][entry.entry_id][SERVICE_API]

    # Collect entities synchronously
    entities = await hass.async_add_executor_job(gather_entities, coordinator, api)

    # Add entities to Home Assistant
    async_add_entities(entities)
    _LOGGER.info("Entities successfully added to Home Assistant")
    return True
