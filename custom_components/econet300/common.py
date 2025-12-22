"""Common code for econet300 integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from aiohttp import ClientError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthError, Econet300Api
from .const import (
    CONF_CATEGORY_MODE,
    DEFAULT_CATEGORY_MODE,
    DOMAIN,
    ECOSOL_CONTROLLER_IDS,
)

_LOGGER = logging.getLogger(__name__)


def skip_params_edits(sys_params: dict[str, Any] | None) -> bool:
    """Determine whether paramsEdits should be skipped based on controllerID."""
    if sys_params is None:
        return False
    controller_id = sys_params.get("controllerID")

    # Controllers that don't support rmCurrentDataParamsEdits endpoint
    unsupported_controllers = {
        "ecoMAX360i",  # Known to not support the endpoint
        *ECOSOL_CONTROLLER_IDS,  # All ecoSOL controllers don't support this endpoint
        "ecoSter",  # ecoSter controllers
        "SControl MK1",  # SControl controllers
    }

    if controller_id in unsupported_controllers:
        _LOGGER.info(
            "Skipping paramsEdits due to controllerID: %s (endpoint not supported)",
            controller_id,
        )
        return True

    # Log which controllers do support the endpoint
    _LOGGER.debug("Controller %s supports paramsEdits endpoint", controller_id)
    return False


class EconetDataCoordinator(DataUpdateCoordinator):
    """Econet data coordinator to handle data updates."""

    def __init__(
        self, hass, api: Econet300Api, options: dict[str, Any] | None = None
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_data_coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self._api = api
        self._options = options or {}
        self._category_mode = self._options.get(
            CONF_CATEGORY_MODE, DEFAULT_CATEGORY_MODE
        )

    def has_sys_data(self, key: str) -> bool:
        """Check if data key is present in sysParams."""
        if self.data is None:
            return False
        return key in self.data["sysParams"]

    def has_reg_data(self, key: str) -> bool:
        """Check if data key is present in regParams."""
        if self.data is None:
            return False

        return key in self.data["regParams"]

    def has_param_edit_data(self, key: str) -> bool:
        """Check if parameter edit data key is present in paramsEdits."""
        if self.data is None:
            return False

        return key in self.data["paramsEdits"]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""

        _LOGGER.debug("Fetching data from API")

        try:
            async with asyncio.timeout(10):
                # Fetch system parameters from ../econet/sysParams
                sys_params = await self._api.fetch_sys_params()

                # Determine whether to fetch paramsEdits from ../econet/rmCurrentDataParamsEdits
                if sys_params is None or skip_params_edits(sys_params):
                    params_edits = {}
                else:
                    params_edits = await self._api.fetch_param_edit_data()

                # Fetch regular parameters from ../econet/regParams
                reg_params = await self._api.fetch_reg_params()

                # Fetch regParamsData from ../econet/regParamsData
                reg_params_data = await self._api.fetch_reg_params_data()

                # Optionally fetch RM... endpoint data for enhanced functionality
                # These provide structured data used by the ecoNET24 web interface
                rm_data = await self._fetch_rm_endpoint_data()

                # Fetch merged parameter data for dynamic entities
                # Pass sys_params to enable service authentication if available
                merged_data = None
                try:
                    merged_data = await self._api.fetch_merged_rm_data_with_names_descs_and_structure(
                        category_mode=self._category_mode,
                        sys_params=sys_params,
                    )
                    _LOGGER.info(
                        "Coordinator fetched merged data: %s parameters (category_mode: %s)",
                        len(merged_data.get("parameters", {})) if merged_data else 0,
                        self._category_mode,
                    )
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                    _LOGGER.warning(
                        "Failed to fetch merged parameter data in coordinator: %s", e
                    )

                result = {
                    "sysParams": sys_params,
                    "regParams": reg_params,
                    "regParamsData": reg_params_data,
                    "paramsEdits": params_edits,
                    "rmData": rm_data,
                    "mergedData": merged_data,
                }

                # Debug: Log merged data structure
                if merged_data and "parameters" in merged_data:
                    param_keys = list(merged_data["parameters"].keys())[
                        :5
                    ]  # First 5 keys
                    _LOGGER.debug(
                        "Coordinator merged data keys (first 5): %s", param_keys
                    )

                return result
        except AuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.warning("Connection failed (device offline?): %s", err)
            raise UpdateFailed(f"Connection failed: {err}") from err

    async def _fetch_rm_endpoint_data(self) -> dict[str, Any]:
        """Fetch data from RM... endpoints for enhanced functionality.

        This method fetches structured data from the RM... endpoints that are
        used by the ecoNET24 web interface. This data can be used for:
        - Better parameter names and descriptions
        - Language support
        - Menu structure information
        - Alarm and lock information

        Returns:
            Dictionary containing RM endpoint data.

        """
        rm_data = {}

        try:
            # Fetch core RM data that's most useful for Home Assistant
            # These calls are made in parallel for better performance
            tasks = [
                self._api.fetch_rm_current_data_params(),
                self._api.fetch_rm_params_names(),
                self._api.fetch_rm_params_data(),
                self._api.fetch_rm_langs(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            rm_data["currentDataParams"] = (
                results[0] if not isinstance(results[0], Exception) else {}
            )
            rm_data["paramsNames"] = (
                results[1] if not isinstance(results[1], Exception) else {}
            )
            rm_data["paramsData"] = (
                results[2] if not isinstance(results[2], Exception) else {}
            )
            rm_data["langs"] = (
                results[3] if not isinstance(results[3], Exception) else {}
            )

            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_names = [
                        "currentDataParams",
                        "paramsNames",
                        "paramsData",
                        "langs",
                    ]
                    _LOGGER.warning("Failed to fetch %s: %s", task_names[i], result)

            # Only fetch additional data if core data was successful
            if rm_data["currentDataParams"]:
                # Fetch additional useful data
                additional_tasks = [
                    self._api.fetch_rm_params_descs(),
                    self._api.fetch_rm_params_enums(),
                    self._api.fetch_rm_alarms_names(),
                ]

                additional_results = await asyncio.gather(
                    *additional_tasks, return_exceptions=True
                )

                rm_data["paramsDescs"] = (
                    additional_results[0]
                    if not isinstance(additional_results[0], Exception)
                    else {}
                )
                rm_data["paramsEnums"] = (
                    additional_results[1]
                    if not isinstance(additional_results[1], Exception)
                    else {}
                )
                rm_data["alarmsNames"] = (
                    additional_results[2]
                    if not isinstance(additional_results[2], Exception)
                    else {}
                )

                # Log any additional errors
                additional_names = ["paramsDescs", "paramsEnums", "alarmsNames"]
                for i, result in enumerate(additional_results):
                    if isinstance(result, Exception):
                        _LOGGER.warning(
                            "Failed to fetch %s: %s", additional_names[i], result
                        )

            _LOGGER.debug(
                "Successfully fetched RM endpoint data: %s", list(rm_data.keys())
            )

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.warning("Error fetching RM endpoint data: %s", e)
            # Return empty dict to avoid breaking the coordinator

        return rm_data

    def has_rm_data(self, key: str) -> bool:
        """Check if RM data key is present in rmData."""
        if self.data is None or "rmData" not in self.data:
            return False
        return key in self.data["rmData"]

    def get_rm_data(self, key: str) -> dict[str, Any] | None:
        """Get RM data by key."""
        if not self.has_rm_data(key):
            return None
        return self.data["rmData"][key]
