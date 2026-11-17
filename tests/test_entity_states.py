"""Regressions for available entities without a current nightly decision."""

from datetime import datetime
import logging
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers import entity_registry, device_registry, area_registry
from homeassistant.util import dt as dt_util

from custom_components.nottinghamshire_gritting.binary_sensor import (
    NottinghamshireGrittingOvernightBinarySensor,
)
from custom_components.nottinghamshire_gritting.const import (
    SOURCE_CITY_EMAIL, SOURCE_COUNTY_EMAIL, SOURCE_COUNTY_X,
)
from custom_components.nottinghamshire_gritting.manager import GrittingData, GrittingManager
from custom_components.nottinghamshire_gritting.sensor import (
    GrittingStatusSensor, LastDecisionSensor, MinimumRoadTemperatureSensor,
    TreatmentTimeSensor,
)
from custom_components.nottinghamshire_gritting.xfeed import XFeedError

LONDON = ZoneInfo("Europe/London")


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=LONDON)


@pytest_asyncio.fixture
async def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(dt_util, "DEFAULT_TIME_ZONE", LONDON)
    monkeypatch.setattr(dt_util, "now", lambda: at("2026-11-17T10:00:00"))
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    await area_registry.async_load(hass)
    device_registry.async_setup(hass)
    await device_registry.async_load(hass)
    await entity_registry.async_load(hass, load_empty=True)
    yield GrittingManager(hass)
    await hass.async_stop()


async def entities(manager):
    items = [GrittingStatusSensor(manager),
            NottinghamshireGrittingOvernightBinarySensor(manager),
            MinimumRoadTemperatureSensor(manager), TreatmentTimeSensor(manager),
            LastDecisionSensor(manager)]
    for entity in items:
        # Device registration is outside these entity-state tests.
        entity._attr_device_info = None
        entity._attr_translation_key = None
    for domain, group in [("sensor", [items[0], *items[2:]]),
                          ("binary_sensor", [items[1]])]:
        component = EntityComponent(logging.getLogger(__name__), domain, manager.hass)
        await component.async_add_entities(group)
    return items


def states(manager, items):
    """Write through real HA entities to verify unknown versus unavailable."""
    result = []
    for entity in items:
        entity.async_write_ha_state()
        assert entity.available
        result.append(manager.hass.states.get(entity.entity_id).state)
    return result


def decision(source, timestamp, planned=True, **kwargs):
    return GrittingData(source=source, decision_time=timestamp,
                       planned=planned, recognised=True, **kwargs)


@pytest.mark.asyncio
async def test_empty_startup(manager):
    assert states(manager, await entities(manager)) == [
        "Awaiting decision", "unknown", "unknown", "unknown", "unknown"]


@pytest.mark.asyncio
@pytest.mark.parametrize("timestamp", ["2026-11-16T17:00:00+00:00", "2026-11-17T05:00:00+00:00"])
@pytest.mark.parametrize("source", [SOURCE_COUNTY_EMAIL, SOURCE_CITY_EMAIL, SOURCE_COUNTY_X])
async def test_expiry_and_next_decision(manager, monkeypatch, timestamp, source):
    manager._decisions[source] = decision(
        source, timestamp, minimum_road_temperature=-2.0,
        treatment_time="2026-11-17T06:00:00+00:00")
    items = await entities(manager)
    monkeypatch.setattr(dt_util, "now", lambda: at("2026-11-17T08:59:59"))
    before = states(manager, items)
    assert before[1] == "on"
    assert "unknown" not in before
    for clock in ["09:00:00", "14:00:00"]:
        monkeypatch.setattr(dt_util, "now", lambda: at(f"2026-11-17T{clock}"))
        await manager.async_clock_tick(dt_util.now())
        assert states(manager, items) == [
            "Awaiting decision", "unknown", "unknown", "unknown", "unknown"]
        assert items[1].is_on is None
        assert items[0].extra_state_attributes["source"] is None
    manager._decisions[source] = decision(source, "2026-11-17T14:00:00+00:00", False)
    after = states(manager, items)
    assert after[0] == ("Likely not — City says no grit" if source == SOURCE_CITY_EMAIL else "Not planned")
    assert after[1:] == ["off", "unknown", "unknown", "2026-11-17T14:00:00+00:00"]


@pytest.mark.asyncio
@pytest.mark.parametrize("recognised,planned", [(False, True), (True, None)])
async def test_unclear_decision(manager, recognised, planned):
    manager._decisions[SOURCE_COUNTY_EMAIL] = GrittingData(
        source=SOURCE_COUNTY_EMAIL, decision_time="2026-11-17T09:30:00+00:00",
        recognised=recognised, planned=planned)
    assert states(manager, await entities(manager))[:2] == ["Decision unclear", "unknown"]


@pytest.mark.asyncio
async def test_x_failure_keeps_diagnostics_and_email_available(manager, monkeypatch):
    manager.x_last_success = "2026-11-17T08:00:00+00:00"
    manager.x_latest_post_text = "Latest public post"
    monkeypatch.setattr(
        "custom_components.nottinghamshire_gritting.manager.async_fetch_nottscc_posts",
        AsyncMock(side_effect=XFeedError("Feed unavailable")))
    await manager.async_refresh_x()
    items = await entities(manager)
    assert states(manager, items)[:2] == ["Awaiting decision", "unknown"]
    for entity in items[:2]:
        attrs = entity.extra_state_attributes
        assert attrs["x_feed_available"] is False
        assert attrs["x_last_error"] == "Feed unavailable"
        assert attrs["x_last_success"] == "2026-11-17T08:00:00+00:00"
        assert attrs["x_latest_post_text"] == "Latest public post"
    manager._decisions[SOURCE_COUNTY_EMAIL] = decision(
        SOURCE_COUNTY_EMAIL, "2026-11-17T09:30:00+00:00")
    assert states(manager, items)[:2] == ["Planned", "on"]
