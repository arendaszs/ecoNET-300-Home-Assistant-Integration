"""Econet300 API class describing methods of getting and setting data."""

import asyncio
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
from aiohttp import BasicAuth, ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_EDITABLE_PARAMS_LIMITS_DATA,
    API_EDITABLE_PARAMS_LIMITS_URI,
    API_REG_PARAMS_DATA_PARAM_DATA,
    API_REG_PARAMS_DATA_URI,
    API_REG_PARAMS_PARAM_DATA,
    API_REG_PARAMS_URI,
    API_RM_ALARMS_NAMES_URI,
    API_RM_CATS_DESCS_URI,
    API_RM_CATS_NAMES_URI,
    API_RM_CURRENT_DATA_PARAMS_EDITS_URI,
    API_RM_CURRENT_DATA_PARAMS_URI,
    API_RM_DATA_KEY,
    API_RM_EXISTING_LANGS_URI,
    API_RM_LANGS_URI,
    API_RM_LOCKS_NAMES_URI,
    API_RM_PARAMS_DATA_URI,
    API_RM_PARAMS_DESCS_URI,
    API_RM_PARAMS_ENUMS_URI,
    API_RM_PARAMS_NAMES_URI,
    API_RM_PARAMS_UNITS_NAMES_URI,
    API_RM_STRUCTURE_URI,
    API_SYS_PARAMS_PARAM_HW_VER,
    API_SYS_PARAMS_PARAM_MODEL_ID,
    API_SYS_PARAMS_PARAM_SW_REV,
    API_SYS_PARAMS_PARAM_UID,
    API_SYS_PARAMS_URI,
    CONTROL_PARAMS,
    NUMBER_MAP,
    RMNEWPARAM_PARAMS,
)
from .mem_cache import MemCache

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication fails."""


class ApiError(Exception):
    """Raised when an API error occurs."""


class DataError(Exception):
    """Raised when there is an error with the data."""


class Limits:
    """Class defining entity value set limits."""

    def __init__(self, min_v: int | None, max_v: int | None):
        """Construct the necessary attributes for the Limits object."""
        self.min = min_v
        self.max = max_v


class EconetClient:
    """Econet client class."""

    def __init__(
        self, host: str, username: str, password: str, session: ClientSession
    ) -> None:
        """Initialize the EconetClient."""

        proto = ["http://", "https://"]

        not_contains = all(p not in host for p in proto)

        if not_contains:
            _LOGGER.info("Manually adding 'http' to host")
            host = "http://" + host

        self._host = host
        self._session = session
        self._auth = BasicAuth(username, password)
        self._model_id = "default-model-id"
        self._sw_revision = "default-sw-revision"

    @property
    def host(self) -> str:
        """Get host address."""
        return self._host

    async def get(self, url):
        """Public method for fetching data."""
        attempt = 1
        max_attempts = 5

        while attempt <= max_attempts:
            try:
                _LOGGER.debug("Fetching data from URL: %s (Attempt %d)", url, attempt)

                async with await self._session.get(
                    url, auth=self._auth, timeout=ClientTimeout(total=15)
                ) as resp:
                    _LOGGER.debug("Received response with status: %s", resp.status)
                    if resp.status == HTTPStatus.UNAUTHORIZED:
                        _LOGGER.error("Unauthorized access to URL: %s", url)
                        raise AuthError

                    if resp.status != HTTPStatus.OK:
                        try:
                            error_message = await resp.text()
                        except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
                            error_message = f"Could not retrieve error message: {e}"

                        _LOGGER.error(
                            "Failed to fetch data from URL: %s (Status: %s) - Response: %s",
                            url,
                            resp.status,
                            error_message,
                        )
                        return None

                    data = await resp.json()
                    _LOGGER.debug("Fetched data: %s", data)
                    return data

            except TimeoutError:
                _LOGGER.warning("Timeout error, retry(%i/%i)", attempt, max_attempts)
                await asyncio.sleep(1)
            attempt += 1
        _LOGGER.error(
            "Failed to fetch data from %s after %d attempts", url, max_attempts
        )
        return None


class Econet300Api:
    """Client for interacting with the ecoNET-300 API."""

    def __init__(self, client: EconetClient, cache: MemCache) -> None:
        """Initialize the Econet300Api object with a client, cache, and default values for uid, sw_revision, and hw_version."""
        self._client = client
        self._cache = cache
        self._uid = "default-uid"
        self._model_id = "default-model-id"
        self._sw_revision = "default-sw-revision"
        self._hw_version = "default-hw-version"

    @classmethod
    async def create(cls, client: EconetClient, cache: MemCache):
        """Create and return initial object."""
        c = cls(client, cache)
        await c.init()

        return c

    @property
    def host(self) -> str:
        """Get clients host address."""
        return self._client.host

    @property
    def uid(self) -> str:
        """Get uid."""
        return self._uid

    @property
    def model_id(self) -> str:
        """Get model name."""
        return self._model_id

    @property
    def sw_rev(self) -> str:
        """Get software version."""
        return self._sw_revision

    @property
    def hw_ver(self) -> str:
        """Get hardware version."""
        return self._hw_version

    async def init(self):
        """Econet300 API initialization."""
        sys_params = await self.fetch_sys_params()

        if sys_params is None:
            _LOGGER.error("Failed to fetch system parameters.")
            return

        # Set system parameters by HA device properties
        self._set_device_property(sys_params, API_SYS_PARAMS_PARAM_UID, "_uid", "UUID")
        self._set_device_property(
            sys_params,
            API_SYS_PARAMS_PARAM_MODEL_ID,
            "_model_id",
            "controller model name",
        )
        self._set_device_property(
            sys_params, API_SYS_PARAMS_PARAM_SW_REV, "_sw_revision", "software revision"
        )
        self._set_device_property(
            sys_params, API_SYS_PARAMS_PARAM_HW_VER, "_hw_version", "hardware version"
        )

    def _set_device_property(self, sys_params, param_key, attr_name, param_desc):
        """Set an attribute from system parameters with logging if unavailable."""
        if param_key not in sys_params:
            _LOGGER.info(
                "%s not in sys_params - cannot set proper %s", param_key, param_desc
            )
            setattr(self, attr_name, None)
        else:
            setattr(self, attr_name, sys_params[param_key])

    async def set_param(self, param, value) -> bool:
        """Set param value in Econet300 API."""
        if param is None:
            _LOGGER.info(
                "Requested param set for: '%s' but mapping for this param does not exist",
                param,
            )
            return False

        # Get the appropriate endpoint URL
        # Use rmCurrNewParam for temperature setpoints (parameter keys like 1280)
        # Use newParam for control parameters (parameter names like BOILER_CONTROL)
        # Use rmNewParam for special parameters that need newParamIndex (like heater mode 55)
        if param in RMNEWPARAM_PARAMS:
            url = f"{self.host}/econet/rmNewParam?newParamIndex={param}&newParamValue={value}"
            _LOGGER.debug(
                "Using rmNewParam endpoint for special parameter %s: %s",
                param,
                url,
            )
        elif param in NUMBER_MAP:
            url = f"{self.host}/econet/rmCurrNewParam?newParamKey={param}&newParamValue={value}"
            _LOGGER.debug(
                "Using rmCurrNewParam endpoint for temperature setpoint %s: %s",
                param,
                url,
            )
        elif param in CONTROL_PARAMS:
            url = f"{self.host}/econet/newParam?newParamName={param}&newParamValue={value}"
            _LOGGER.debug(
                "Using newParam endpoint for control parameter %s: %s", param, url
            )
        else:
            # Default to newParam for unknown parameters
            url = f"{self.host}/econet/newParam?newParamName={param}&newParamValue={value}"
            _LOGGER.debug(
                "Using default newParam endpoint for parameter %s: %s", param, url
            )

        # Make the API call
        data = await self._client.get(url)
        if data is None or "result" not in data:
            return False
        if data["result"] != "OK":
            return False

        # Cache the value locally
        self._cache.set(param, value)

        # Force immediate refresh of paramsEdits data
        await self._force_refresh_params_edits()

        return True

    async def _force_refresh_params_edits(self):
        """Force refresh paramsEdits data by fetching fresh data and updating cache."""
        try:
            _LOGGER.debug("Force refreshing paramsEdits data")
            fresh_data = await self._fetch_api_data_by_key(
                API_EDITABLE_PARAMS_LIMITS_URI, API_EDITABLE_PARAMS_LIMITS_DATA
            )
            if fresh_data:
                self._cache.set(API_EDITABLE_PARAMS_LIMITS_DATA, fresh_data)
                _LOGGER.debug("Successfully refreshed paramsEdits data: %s", fresh_data)
            else:
                _LOGGER.info("Failed to refresh paramsEdits data")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error refreshing paramsEdits data: %s", e)

    async def get_param_limits(self, param: str):
        """Fetch and return the limits for a particular parameter from the Econet 300 API, using a cache for efficient retrieval if available."""
        if not self._cache.exists(API_EDITABLE_PARAMS_LIMITS_DATA):
            try:
                # Attempt to fetch the API data
                limits = await self._fetch_api_data_by_key(
                    API_EDITABLE_PARAMS_LIMITS_URI, API_EDITABLE_PARAMS_LIMITS_DATA
                )
                # Cache the fetched data
                self._cache.set(API_EDITABLE_PARAMS_LIMITS_DATA, limits)
            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
                DataError,
            ) as e:
                _LOGGER.error(
                    "API error while fetching data from %s: %s",
                    API_EDITABLE_PARAMS_LIMITS_URI,
                    e,
                )
                return None
            except (TypeError, AttributeError) as e:
                _LOGGER.error(
                    "Data structure error while processing API data from %s: %s",
                    API_EDITABLE_PARAMS_LIMITS_URI,
                    e,
                )
                return None

        # Retrieve limits from the cache
        limits = self._cache.get(API_EDITABLE_PARAMS_LIMITS_DATA)

        if not param:
            _LOGGER.info("Parameter name is None. Unable to fetch limits.")
            return None

        if limits is None or param not in limits:
            _LOGGER.info(
                "Limits for parameter '%s' do not exist. Available limits: %s",
                param,
                limits,
            )
            return None

        # Extract and log the limits
        curr_limits = limits[param]
        # Remove sensitive data from debug logging to prevent information disclosure
        _LOGGER.debug("Limits for edit param '%s' retrieved successfully", param)
        return Limits(curr_limits["min"], curr_limits["max"])

    async def fetch_reg_params_data(self) -> dict[str, Any] | None:
        """Fetch data from econet/regParamsData."""
        try:
            regParamsData = await self._fetch_api_data_by_key(
                API_REG_PARAMS_DATA_URI, API_REG_PARAMS_DATA_PARAM_DATA
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, DataError) as e:
            _LOGGER.error("API error occurred while fetching regParamsData: %s", e)
            return {}
        except (TypeError, AttributeError) as e:
            _LOGGER.error(
                "Data structure error occurred while processing regParamsData: %s", e
            )
            return {}
        else:
            _LOGGER.debug("Fetched regParamsData: %s", regParamsData)
            return regParamsData

    async def fetch_param_edit_data(self):
        """Fetch and return the limits for a particular parameter from the Econet 300 API, using a cache for efficient retrieval if available.

        Note: This endpoint is only supported by certain controllers (e.g., ecoMAX series).
        Controllers like ecoSOL500, ecoSter, SControl MK1 don't support this endpoint.
        The common.py skip_params_edits() function handles controller-specific endpoint support.
        """
        if not self._cache.exists(API_EDITABLE_PARAMS_LIMITS_DATA):
            limits = await self._fetch_api_data_by_key(
                API_EDITABLE_PARAMS_LIMITS_URI, API_EDITABLE_PARAMS_LIMITS_DATA
            )
            # Ensure we always return a dict, not None
            if limits is None:
                limits = {}
            self._cache.set(API_EDITABLE_PARAMS_LIMITS_DATA, limits)

        result = self._cache.get(API_EDITABLE_PARAMS_LIMITS_DATA)
        # Ensure we always return a dict, not None
        return result if result is not None else {}

    async def fetch_reg_params(self) -> dict[str, Any] | None:
        """Fetch and return the regParams data from ip/econet/regParams endpoint."""
        _LOGGER.info("Calling fetch_reg_params method")
        regParams = await self._fetch_api_data_by_key(
            API_REG_PARAMS_URI, API_REG_PARAMS_PARAM_DATA
        )
        _LOGGER.debug("Fetched regParams data: %s", regParams)
        _LOGGER.debug("Type of regParams: %s", type(regParams))
        return regParams

    async def fetch_sys_params(self) -> dict[str, Any] | None:
        """Fetch and return the regParam data from ip/econet/sysParams endpoint."""
        _LOGGER.debug(
            "fetch_sys_params called: Fetching parameters for registry '%s' from host '%s'",
            self.host,
            API_SYS_PARAMS_URI,
        )
        sysParams = await self._fetch_api_data_by_key(API_SYS_PARAMS_URI)
        _LOGGER.debug("Fetched sysParams data: %s", sysParams)
        return sysParams

    async def _fetch_api_data_by_key(self, endpoint: str, data_key: str | None = None):
        """Fetch a key from the json-encoded data returned by the API for a given registry If key is None, then return whole data."""
        try:
            data = await self._client.get(f"{self.host}/econet/{endpoint}")

            if data is None:
                _LOGGER.info("Data fetched by API for endpoint: %s is None", endpoint)
                return None

            if data_key is None:
                return data

            if data_key not in data:
                _LOGGER.info(
                    "Data for key: %s does not exist in endpoint: %s",
                    data_key,
                    endpoint,
                )
                return None

            return data[data_key]
        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Client error occurred while fetching data from endpoint: %s, error: %s",
                endpoint,
                e,
            )
        except asyncio.TimeoutError as e:
            _LOGGER.error(
                "A timeout error occurred while fetching data from endpoint: %s, error: %s",
                endpoint,
                e,
            )
        except ValueError as e:
            _LOGGER.error(
                "A value error occurred while processing data from endpoint: %s, error: %s",
                endpoint,
                e,
            )
        except (TypeError, AttributeError) as e:
            _LOGGER.error(
                "Data structure error occurred while processing response from endpoint: %s, error: %s",
                endpoint,
                e,
            )
        return None

    # =============================================================================
    # RM... ENDPOINT METHODS (Remote Menu API)
    # =============================================================================
    # These methods provide access to the structured data endpoints used by
    # the ecoNET24 web interface. Based on analysis of dev_set1.js and test fixtures.

    async def fetch_rm_params_names(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch parameter names with translations from rmParamsNames endpoint.

        This endpoint provides human-readable parameter names in the specified language.
        Used by the ecoNET24 web interface to display parameter labels.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing parameter names mapped to their translations.
            None if the request fails.

        Example:
            {
                "remoteMenuParamsNamesVer": "61477_1",
                "data": [
                    "100% Blow-in output",
                    "100% Feeder operation",
                    "Boiler hysteresis",
                    "FL airfl. correction",
                    "Minimum boiler output FL"
                ]
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_PARAMS_NAMES_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching parameter names from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch parameter names from rmParamsNames")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching parameter names: %s", e)
            return None

    async def fetch_rm_params_data(self) -> dict[str, Any] | None:
        """Fetch parameter metadata from rmParamsData endpoint.

        This endpoint provides parameter metadata including min/max values, units,
        and other configuration information for each parameter.

        Returns:
            Dictionary containing parameter metadata.
            None if the request fails.

        Example:
            {
                "remoteMenuValuesKonfVer": 14264,
                "remoteMenuValuesVer": 43253,
                "data": [
                    {
                        "value": 60,
                        "maxv": 100,
                        "minv": 15,
                        "edit": true,
                        "unit": 5,
                        "mult": 1,
                        "offset": 0
                    }
                ]
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_PARAMS_DATA_URI}?uid={self.uid}"
            _LOGGER.debug("Fetching parameter data from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch parameter data from rmParamsData")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching parameter data: %s", e)
            return None

    async def fetch_rm_params_descs(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch parameter descriptions from rmParamsDescs endpoint.

        This endpoint provides detailed descriptions of parameters in the specified language.
        Used for help text and parameter explanations in the web interface.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing parameter descriptions.
            None if the request fails.

        Example:
            {
                "remoteMenuParamsDescsVer": "16688_1",
                "data": [
                    "Blow-in output when the burner runs at maximum output.",
                    "Feeder operation time when the burner runs at maximum output.",
                    "If the boiler temperature drops below the present boiler temperature by the boiler hysteresis value, then the automatic burner firing up will take place."
                ]
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_PARAMS_DESCS_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching parameter descriptions from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch parameter descriptions from rmParamsDescs"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching parameter descriptions: %s", e)
            return None

    async def fetch_rm_params_enums(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch parameter enumeration values from rmParamsEnums endpoint.

        This endpoint provides enumeration values for parameters that have
        predefined options (like operation modes, status values, etc.).

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing parameter enumeration values.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_PARAMS_ENUMS_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching parameter enums from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch parameter enums from rmParamsEnums")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching parameter enums: %s", e)
            return None

    async def fetch_rm_params_units_names(
        self, lang: str = "en"
    ) -> dict[str, Any] | None:
        """Fetch parameter unit names from rmParamsUnitsNames endpoint.

        This endpoint provides unit names and symbols for parameters.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing parameter unit names.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_PARAMS_UNITS_NAMES_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching parameter units from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch parameter units from rmParamsUnitsNames"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching parameter units: %s", e)
            return None

    async def fetch_rm_cats_names(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch category names from rmCatsNames endpoint.

        This endpoint provides category names for organizing parameters in the web interface.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing category names.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_CATS_NAMES_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching category names from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch category names from rmCatsNames")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching category names: %s", e)
            return None

    async def fetch_rm_cats_descs(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch category descriptions from rmCatsDescs endpoint.

        This endpoint provides detailed descriptions of parameter categories.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing category descriptions.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_CATS_DESCS_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching category descriptions from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch category descriptions from rmCatsDescs"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching category descriptions: %s", e)
            return None

    async def fetch_rm_structure(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch menu structure from rmStructure endpoint.

        This endpoint provides the hierarchical menu structure for the web interface,
        showing how parameters are organized and grouped.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing menu structure.
            None if the request fails.

        """
        try:
            url = (
                f"{self.host}/service/{API_RM_STRUCTURE_URI}?uid={self.uid}&lang={lang}"
            )
            _LOGGER.debug("Fetching menu structure from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch menu structure from rmStructure")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching menu structure: %s", e)
            return None

    async def fetch_rm_current_data_params(
        self, lang: str = "en"
    ) -> dict[str, Any] | None:
        """Fetch current parameter values from rmCurrentDataParams endpoint.

        This endpoint provides the current values of all parameters.
        This is the main data source for sensor values in Home Assistant.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing current parameter values.
            None if the request fails.

        Example:
            {
                "remoteMenuCurrDataParamsVer": "17127_1",
                "data": {
                    "1": {
                        "unit": 31,
                        "name": "Lighter",
                        "special": 1
                    },
                    "26": {
                        "unit": 1,
                        "name": "Feeder temperature",
                        "special": 1
                    }
                }
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_CURRENT_DATA_PARAMS_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching current data params from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch current data params from rmCurrentDataParams"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching current data params: %s", e)
            return None

    async def fetch_rm_current_data_params_edits(self) -> dict[str, Any] | None:
        """Fetch editable parameter data from rmCurrentDataParamsEdits endpoint.

        This endpoint provides information about which parameters can be edited
        and their current values. Used for number entities and controls.

        Returns:
            Dictionary containing editable parameter data.
            None if the request fails.

        Example:
            {
                "currentDataParamsEditsVer": 1,
                "data": {
                    "1280": {
                        "max": 68,
                        "type": 4,
                        "value": 40,
                        "min": 27
                    },
                    "2048": {
                        "max": 2,
                        "type": 4,
                        "value": 0,
                        "min": 0
                    }
                }
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_CURRENT_DATA_PARAMS_EDITS_URI}?uid={self.uid}"
            _LOGGER.debug("Fetching current data params edits from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch current data params edits from rmCurrentDataParamsEdits"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching current data params edits: %s", e)
            return None

    async def fetch_rm_langs(self) -> dict[str, Any] | None:
        """Fetch available languages from rmLangs endpoint.

        This endpoint provides information about available languages for translations.

        Returns:
            Dictionary containing available languages.
            None if the request fails.

        Example:
            {
                "remoteMenuLangsVer": "20028",
                "defaultLang": "default",
                "data": [
                    {
                        "code": "pl",
                        "name": "Polski",
                        "version": "3EDBB76"
                    },
                    {
                        "default": true,
                        "code": "en",
                        "name": "English",
                        "version": "3ACA62B1"
                    }
                ]
            }

        """
        try:
            url = f"{self.host}/service/{API_RM_LANGS_URI}?uid={self.uid}"
            _LOGGER.debug("Fetching available languages from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch available languages from rmLangs")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching available languages: %s", e)
            return None

    async def fetch_rm_existing_langs(self) -> dict[str, Any] | None:
        """Fetch existing language list from rmExistingLangs endpoint.

        This endpoint provides a list of languages that are actually available
        on the controller (as opposed to all possible languages).

        Returns:
            Dictionary containing existing language list.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_EXISTING_LANGS_URI}?uid={self.uid}"
            _LOGGER.debug("Fetching existing languages from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning(
                    "Failed to fetch existing languages from rmExistingLangs"
                )
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching existing languages: %s", e)
            return None

    async def fetch_rm_locks_names(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch lock/restriction messages from rmLocksNames endpoint.

        This endpoint provides messages about parameter locks and restrictions.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing lock/restriction messages.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_LOCKS_NAMES_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching lock names from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch lock names from rmLocksNames")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching lock names: %s", e)
            return None

    async def fetch_rm_alarms_names(self, lang: str = "en") -> dict[str, Any] | None:
        """Fetch alarm descriptions from rmAlarmsNames endpoint.

        This endpoint provides descriptions of alarm conditions and messages.

        Args:
            lang: Language code (e.g., 'en', 'pl', 'fr'). Defaults to 'en'.

        Returns:
            Dictionary containing alarm descriptions.
            None if the request fails.

        """
        try:
            url = f"{self.host}/service/{API_RM_ALARMS_NAMES_URI}?uid={self.uid}&lang={lang}"
            _LOGGER.debug("Fetching alarm names from: %s", url)

            data = await self._client.get(url)
            if data is None:
                _LOGGER.warning("Failed to fetch alarm names from rmAlarmsNames")
                return None

            return data.get(API_RM_DATA_KEY, {})

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.error("Error fetching alarm names: %s", e)
            return None


async def make_api(hass: HomeAssistant, cache: MemCache, data: dict):
    """Create api object."""
    return await Econet300Api.create(
        EconetClient(
            data["host"],
            data["username"],
            data["password"],
            async_get_clientsession(hass),
        ),
        cache,
    )
