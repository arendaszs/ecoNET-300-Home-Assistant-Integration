"""Options flow for ecoNET300 integration.

This module provides a UI for configuring category settings through
the Home Assistant interface (Settings → Devices → ecoNET300 → Configure).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    CATEGORY_MODE_API,
    CATEGORY_MODE_NONE,
    CATEGORY_MODE_SIMPLIFIED,
    CONF_CATEGORY_MODE,
    DEFAULT_CATEGORY_MODE,
)

_LOGGER = logging.getLogger(__name__)


class EconetOptionsFlowHandler(OptionsFlow):
    """Handle ecoNET300 options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - category configuration."""
        if user_input is not None:
            _LOGGER.debug("Options flow user input: %s", user_input)
            return self.async_create_entry(title="", data=user_input)

        # Get current options or defaults
        current_mode = self.config_entry.options.get(
            CONF_CATEGORY_MODE, DEFAULT_CATEGORY_MODE
        )

        # Build schema with current values as defaults
        options_schema = vol.Schema(
            {
                vol.Required(CONF_CATEGORY_MODE, default=current_mode): vol.In(
                    {
                        CATEGORY_MODE_SIMPLIFIED: "Simplified (Boiler/HUW/Mixer/Other)",
                        CATEGORY_MODE_API: "API as-is (device menu structure)",
                        CATEGORY_MODE_NONE: "None (flat list, no categories)",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "simplified_desc": "Groups parameters into Boiler, HUW, Mixer, and Other categories",
                "api_desc": "Uses the device's native menu structure for categories",
                "none_desc": "No categories - all parameters in a flat list",
            },
        )


@callback
def async_get_options_flow(config_entry: ConfigEntry) -> EconetOptionsFlowHandler:
    """Get the options flow handler."""
    return EconetOptionsFlowHandler(config_entry)

