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
    async_add_entities(
        [NottinghamshireGrittingOvernightBinarySensor(entry.runtime_data)]
    )


class NottinghamshireGrittingOvernightBinarySensor(
    NottinghamshireGrittingEntity, BinarySensorEntity
):
    """Whether gritting is confirmed or strongly inferred for the current night."""

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
            "source": self.manager.source_label,
            "source_key": data.source,
            "confidence": data.confidence,
            "source_url": data.source_url,
            "x_feed_available": self.manager.x_available,
            "x_last_check": self.manager.x_last_check,
            "x_last_success": self.manager.x_last_success,
            "x_last_error": self.manager.x_last_error,
        }
