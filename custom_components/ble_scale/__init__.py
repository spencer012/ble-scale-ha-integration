"""BLE Scale integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BleScaleCoordinator

PLATFORMS = [Platform.SENSOR]

BleScaleConfigEntry = ConfigEntry[BleScaleCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BleScaleConfigEntry
) -> bool:
    """Set up BLE Scale from a config entry."""
    coordinator = BleScaleCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BleScaleConfigEntry
) -> bool:
    """Unload a BLE Scale config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    return True
