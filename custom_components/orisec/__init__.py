"""The Orisec Alarm Panel integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import OrisecClient, OrisecError
from .const import CONF_HOST, CONF_PIN, CONF_PORT, DEFAULT_TIMEOUT, DOMAIN
from .coordinator import OrisecDataUpdateCoordinator

PLATFORMS = ["alarm_control_panel", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Orisec from a config entry."""
    client = OrisecClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_PIN],
        timeout=DEFAULT_TIMEOUT,
    )

    coordinator = OrisecDataUpdateCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except OrisecError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
