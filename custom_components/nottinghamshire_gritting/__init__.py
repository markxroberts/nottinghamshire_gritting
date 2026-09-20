"""Nottinghamshire Gritting integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import EVENT_IMAP_CONTENT
from .manager import GrittingManager

PLATFORMS = ["binary_sensor", "sensor"]


type NottinghamshireGrittingConfigEntry = ConfigEntry[GrittingManager]


async def async_setup_entry(
    hass: HomeAssistant, entry: NottinghamshireGrittingConfigEntry
) -> bool:
    """Set up Nottinghamshire Gritting from a config entry."""
    manager = GrittingManager(hass)
    await manager.async_load()
    entry.runtime_data = manager

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_IMAP_CONTENT, manager.async_handle_imap_event)
    )
    entry.async_on_unload(
        async_track_time_change(
            hass,
            manager.async_clock_tick,
            minute=0,
            second=0,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NottinghamshireGrittingConfigEntry
) -> bool:
    """Unload Nottinghamshire Gritting."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
