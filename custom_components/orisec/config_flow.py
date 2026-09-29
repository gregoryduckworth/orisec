"""Config flow for the Orisec Alarm Panel integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .api import (
    PIN_MAX_LENGTH,
    OrisecAuthError,
    OrisecClient,
    OrisecConnectionError,
)
from .const import CONF_PIN, DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_PIN): vol.All(str, vol.Length(min=1, max=PIN_MAX_LENGTH)),
    }
)


async def _validate_input(data: dict[str, Any]) -> None:
    """Validate that we can connect to the panel with the given details."""
    client = OrisecClient(
        data[CONF_HOST], data[CONF_PORT], data[CONF_PIN], timeout=DEFAULT_TIMEOUT
    )
    await client.async_get_status()


class OrisecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Orisec Alarm Panel."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                await _validate_input(user_input)
            except OrisecAuthError:
                errors["base"] = "invalid_auth"
            except OrisecConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
