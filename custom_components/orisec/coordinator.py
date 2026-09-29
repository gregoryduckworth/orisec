"""DataUpdateCoordinator for the Orisec integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OrisecClient, OrisecError, OrisecStatus
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OrisecDataUpdateCoordinator(DataUpdateCoordinator[OrisecStatus]):
    """Polls the Orisec panel for its current state."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OrisecClient,
        update_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> OrisecStatus:
        try:
            return await self.client.async_get_status()
        except OrisecError as err:
            raise UpdateFailed(f"Error communicating with panel: {err}") from err
