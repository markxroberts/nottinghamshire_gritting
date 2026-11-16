"""Nottinghamshire Gritting integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)

from .const import EVENT_IMAP_CONTENT, X_POLL_MINUTES
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
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            manager.async_refresh_x,
            timedelta(minutes=X_POLL_MINUTES),
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Recover a bulletin that arrived before this integration was reloaded.
    # Do this in the background so IMAP/network latency cannot delay HA startup.
    entry.async_create_background_task(
        hass,
        manager.async_recover_imap_decisions(),
        "nottinghamshire_gritting_imap_recovery",
    )

    # X is tertiary context/fallback; do not hold up startup if it is slow.
    entry.async_create_background_task(
        hass,
        manager.async_refresh_x(),
        "nottinghamshire_gritting_initial_x_refresh",
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NottinghamshireGrittingConfigEntry
) -> bool:
    """Unload Nottinghamshire Gritting."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
