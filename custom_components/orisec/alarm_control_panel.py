"""Alarm control panel platform for Orisec."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OrisecError
from .const import DOMAIN, MANUFACTURER
from .coordinator import OrisecDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orisec alarm control panel from a config entry."""
    coordinator: OrisecDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OrisecAlarmPanel(coordinator, entry)])


class OrisecAlarmPanel(CoordinatorEntity[OrisecDataUpdateCoordinator], AlarmControlPanelEntity):
    """Representation of an Orisec alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_HOME
    )

    def __init__(
        self, coordinator: OrisecDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_panel"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="ControlPlus",
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        status = self.coordinator.data
        if status is None:
            return None
        if status.triggered:
            return AlarmControlPanelState.TRIGGERED
        if status.armed_away:
            return AlarmControlPanelState.ARMED_AWAY
        if status.armed_home:
            return AlarmControlPanelState.ARMED_HOME
        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_send_command(self.coordinator.client.async_disarm)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_send_command(self.coordinator.client.async_arm_away)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_send_command(self.coordinator.client.async_arm_home)

    async def _async_send_command(self, command) -> None:  # noqa: ANN001
        """Send a command to the panel, surfacing failures to the UI."""
        try:
            await command()
        except OrisecError as err:
            raise HomeAssistantError(
                f"Failed to send command to the Orisec panel: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
