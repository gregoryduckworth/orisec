"""Binary sensor platform for Orisec zones."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrisecDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Orisec zone binary sensors from a config entry."""
    coordinator: OrisecDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    status = coordinator.data
    zone_numbers = sorted(status.zones) if status else []

    async_add_entities(
        OrisecZoneBinarySensor(coordinator, entry, zone_number)
        for zone_number in zone_numbers
    )


class OrisecZoneBinarySensor(
    CoordinatorEntity[OrisecDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a single Orisec zone."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: OrisecDataUpdateCoordinator,
        entry: ConfigEntry,
        zone_number: int,
    ) -> None:
        super().__init__(coordinator)
        self._zone_number = zone_number
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_number}"
        self._attr_name = f"Zone {zone_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="ControlPlus",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the zone is currently open/triggered."""
        status = self.coordinator.data
        if status is None:
            return None
        return status.zones.get(self._zone_number)
