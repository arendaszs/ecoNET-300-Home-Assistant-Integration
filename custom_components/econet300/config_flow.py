"""Config flow for ecoNET300 integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol

from .api import make_api
from .common import AuthError
from .const import CONF_ENTRY_DESCRIPTION, CONF_ENTRY_TITLE, DOMAIN
from .mem_cache import MemCache

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    cache = MemCache()
    info = {}

    try:
        api = await make_api(hass, cache, data)
        info["uid"] = api.uid
    except AuthError as auth_error:
        raise InvalidAuth from auth_error
    except TimeoutError as timeout_error:
        raise CannotConnect from timeout_error

    return info


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ecoNET300 integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return EconetOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            user_input["uid"] = info["uid"]

            await self.async_set_unique_id(user_input["uid"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=CONF_ENTRY_TITLE,
                description=CONF_ENTRY_DESCRIPTION,
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="reconfigure_failed")
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="reconfigure_failed")

        if user_input is None:
            # Pre-fill the form with current values (password not shown for security)
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required("host", default=entry.data.get("host", "")): str,
                        vol.Required(
                            "username", default=entry.data.get("username", "")
                        ): str,
                        vol.Required("password"): str,
                    }
                ),
                description_placeholders={"device_name": entry.title},
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception during reconfigure")
            errors["base"] = "unknown"
        else:
            # Update the config entry with new data
            return self.async_update_reload_and_abort(
                entry,
                data={
                    **entry.data,
                    "host": user_input["host"],
                    "username": user_input["username"],
                    "password": user_input["password"],
                    "uid": info["uid"],
                },
            )

        # Show form again with errors
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=user_input.get("host", "")): str,
                    vol.Required(
                        "username", default=user_input.get("username", "")
                    ): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
            description_placeholders={"device_name": entry.title},
        )


class EconetOptionsFlowHandler(OptionsFlow):
    """Handle options flow for ecoNET300."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the new configuration
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                # Update the config entry with new data, preserving uid
                new_data = {
                    **self.config_entry.data,
                    "host": user_input["host"],
                    "username": user_input["username"],
                    "password": user_input["password"],
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                # Schedule reload as background task to avoid blocking the flow
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
                return self.async_create_entry(title="", data={})

        # Show form with current values as defaults
        options_schema = vol.Schema(
            {
                vol.Required(
                    "host", default=self.config_entry.data.get("host", "")
                ): str,
                vol.Required(
                    "username", default=self.config_entry.data.get("username", "")
                ): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
