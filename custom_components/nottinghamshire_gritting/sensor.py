"""Sensors for Nottinghamshire Gritting."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NottinghamshireGrittingConfigEntry
from .entity import NottinghamshireGrittingEntity
from .manager import GrittingManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NottinghamshireGrittingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Nottinghamshire Gritting sensors."""
    manager = entry.runtime_data
    async_add_entities(
        [
            GrittingStatusSensor(manager),
            MinimumRoadTemperatureSensor(manager),
            TreatmentTimeSensor(manager),
            LastDecisionSensor(manager),
        ]
    )


class GrittingStatusSensor(NottinghamshireGrittingEntity, SensorEntity):
    """Human-readable status."""

    _attr_name = "Gritting status"
    _attr_unique_id = "nottinghamshire_gritting_status"
    _attr_icon = "mdi:road-variant"

    @property
    def native_value(self) -> str:
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.manager.data
        return {
            "decision_time": data.decision_time,
            "recognised": data.recognised,
            "subject": data.subject,
            "source": self.manager.source_label,
            "source_key": data.source,
            "confidence": data.confidence,
            "source_url": data.source_url,
            "x_feed_available": self.manager.x_available,
            "x_last_check": self.manager.x_last_check,
            "x_last_success": self.manager.x_last_success,
            "x_last_error": self.manager.x_last_error,
        }


class MinimumRoadTemperatureSensor(NottinghamshireGrittingEntity, SensorEntity):
    """Minimum forecast road temperature quoted in the current update."""

    entity_description = SensorEntityDescription(
        key="minimum_road_temperature",
        name="Minimum road temperature",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    )
    _attr_unique_id = "nottinghamshire_gritting_minimum_road_temperature"

    @property
    def available(self) -> bool:
        return (
            self.manager.is_current
            and self.manager.data.minimum_road_temperature is not None
        )

    @property
    def native_value(self) -> float | None:
        return self.manager.data.minimum_road_temperature


class TreatmentTimeSensor(NottinghamshireGrittingEntity, SensorEntity):
    """First treatment time parsed from the current update."""

    entity_description = SensorEntityDescription(
        key="treatment_time",
        name="Treatment time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    _attr_unique_id = "nottinghamshire_gritting_treatment_time"

    @property
    def available(self) -> bool:
        return (
            self.manager.is_current
            and self.manager.treatment_datetime is not None
        )

    @property
    def native_value(self) -> datetime | None:
        return self.manager.treatment_datetime


class LastDecisionSensor(NottinghamshireGrittingEntity, SensorEntity):
    """Timestamp of the last effective decision."""

    entity_description = SensorEntityDescription(
        key="last_decision",
        name="Last decision",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    _attr_unique_id = "nottinghamshire_gritting_last_decision"

    @property
    def available(self) -> bool:
        return self.manager.decision_datetime is not None

    @property
    def native_value(self) -> datetime | None:
        return self.manager.decision_datetime
