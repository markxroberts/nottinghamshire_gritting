"""Base entity for Nottinghamshire Gritting."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import COUNCIL_GRITTING_URL, DOMAIN, SIGNAL_UPDATE
from .manager import GrittingManager


class NottinghamshireGrittingEntity(Entity):
    """Base class for Nottinghamshire Gritting entities."""

    _attr_has_entity_name = True

    def __init__(self, manager: GrittingManager) -> None:
        self.manager = manager
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "nottinghamshire_winter_service")},
            name="Nottinghamshire Winter Service",
            manufacturer="Nottinghamshire County Council / Via East Midlands",
            model="Winter Service",
            configuration_url=COUNCIL_GRITTING_URL,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        """Write updated state from the Home Assistant event loop."""
        self.async_write_ha_state()
