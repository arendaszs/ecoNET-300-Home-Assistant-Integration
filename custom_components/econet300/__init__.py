"""The ecoNET300 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.issue_registry import async_delete_issue

from .api import make_api
from .common import AuthError, EconetDataCoordinator
from .const import DOMAIN, SERVICE_API, SERVICE_COORDINATOR
from .mem_cache import MemCache

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]

# Required for polling integrations
PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Econet300 Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    cache = MemCache()

    try:
        data: dict[str, str] = dict(entry.data)
        api = await make_api(hass, cache, data)

        coordinator = EconetDataCoordinator(hass, api, entry)
        await coordinator.async_config_entry_first_refresh()

        hass.data[DOMAIN][entry.entry_id] = {
            SERVICE_API: api,
            SERVICE_COORDINATOR: coordinator,
        }
    except AuthError as auth_error:
        raise ConfigEntryAuthFailed("Client not authenticated") from auth_error
    except TimeoutError as timeout_error:
        raise ConfigEntryNotReady("Target not found") from timeout_error
    else:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry - clean up any repair issues."""
    async_delete_issue(hass, DOMAIN, f"connection_failed_{entry.entry_id}")
