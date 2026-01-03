"""Repairs flow for ecoNET300 integration."""

from __future__ import annotations

from typing import Any

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_delete_issue
import voluptuous as vol

from .api import make_api
from .common import AuthError
from .const import DOMAIN
from .mem_cache import MemCache


class ConnectionFailedRepairFlow(RepairsFlow):
    """Handler for connection failed repair flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of the repair flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the new configuration
            cache = MemCache()
            try:
                await make_api(self.hass, cache, user_input)
            except AuthError:
                errors["base"] = "invalid_auth"
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                # Update the config entry with new data, preserving uid
                new_data = {
                    **self._entry.data,
                    "host": user_input["host"],
                    "username": user_input["username"],
                    "password": user_input["password"],
                }
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data=new_data,
                )
                # Delete the repair issue
                async_delete_issue(
                    self.hass, DOMAIN, f"connection_failed_{self._entry.entry_id}"
                )
                # Reload the entry to apply changes
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_create_entry(data={})

        # Show form with current values as defaults
        repair_schema = vol.Schema(
            {
                vol.Required("host", default=self._entry.data.get("host", "")): str,
                vol.Required(
                    "username", default=self._entry.data.get("username", "")
                ): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="confirm",
            data_schema=repair_schema,
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    # Extract entry_id from issue_id (format: "connection_failed_{entry_id}")
    if issue_id.startswith("connection_failed_"):
        entry_id = issue_id.replace("connection_failed_", "")
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry:
            return ConnectionFailedRepairFlow(entry)

    # Fallback - should not happen
    raise ValueError(f"Unknown issue_id: {issue_id}")
