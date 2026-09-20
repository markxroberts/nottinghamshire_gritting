"""Binary sensors for Nottinghamshire Gritting."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NottinghamshireGrittingConfigEntry
from .entity import NottinghamshireGrittingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NottinghamshireGrittingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the gritting binary sensor."""
    async_add_entities([NottinghamshireGrittingOvernightBinarySensor(entry.runtime_data)])


class NottinghamshireGrittingOvernightBinarySensor(
    NottinghamshireGrittingEntity, BinarySensorEntity
):
    """Whether Nottinghamshire has announced gritting for the current night."""

    _attr_name = "Gritting overnight"
    _attr_unique_id = "nottinghamshire_gritting_overnight"
    _attr_translation_key = "gritting_overnight"

    @property
    def available(self) -> bool:
        return self.manager.is_current and self.manager.data.recognised

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        return self.manager.data.planned

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.manager.data
        return {
            "status": self.manager.status,
            "decision_time": data.decision_time,
            "treatment_time": data.treatment_time,
            "minimum_road_temperature": data.minimum_road_temperature,
            "subject": data.subject,
            "sender": data.sender,
            "message_excerpt": data.excerpt,
            "source": "Nottinghamshire County Council winter service email",
        }
