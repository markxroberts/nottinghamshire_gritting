"""Runtime data manager for Nottinghamshire Gritting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SIGNAL_UPDATE, STORAGE_KEY, STORAGE_VERSION
from .parser import is_relevant_message, parse_message

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GrittingData:
    """Last gritting decision."""

    planned: bool | None = None
    decision_time: str | None = None
    subject: str | None = None
    sender: str | None = None
    uid: str | None = None
    minimum_road_temperature: float | None = None
    treatment_time: str | None = None
    excerpt: str | None = None
    recognised: bool = False


class GrittingManager:
    """Receive IMAP events, parse them, and hold the current decision."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.data = GrittingData()
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load the last decision from storage."""
        stored = await self._store.async_load()
        if not stored:
            return
        try:
            self.data = GrittingData(**stored)
        except TypeError:
            _LOGGER.warning("Ignoring incompatible stored Nottinghamshire gritting data")

    async def async_handle_imap_event(self, event: Event) -> None:
        """Handle an imap_content event."""
        payload = event.data

        # IMAP emits another event when a message is removed from the search
        # scope. Only process the initial arrival event.
        if payload.get("initial") is False:
            return

        subject = str(payload.get("subject") or "")
        sender = str(payload.get("sender") or "")
        body = str(payload.get("text") or payload.get("custom") or "")

        if not is_relevant_message(subject, body, sender):
            return

        decision_dt = self._event_datetime(payload.get("date"))
        parsed = parse_message(subject, body, decision_dt)

        self.data = GrittingData(
            planned=parsed.planned,
            decision_time=decision_dt.isoformat(),
            subject=subject or None,
            sender=sender or None,
            uid=str(payload.get("uid")) if payload.get("uid") is not None else None,
            minimum_road_temperature=parsed.minimum_road_temperature,
            treatment_time=parsed.treatment_time.isoformat() if parsed.treatment_time else None,
            excerpt=parsed.excerpt,
            recognised=parsed.planned is not None,
        )
        await self._store.async_save(asdict(self.data))

        if parsed.planned is None:
            _LOGGER.warning(
                "Received a Nottinghamshire winter-service message but could not determine "
                "whether gritting is planned. Subject: %s",
                subject,
            )
        else:
            _LOGGER.info(
                "Nottinghamshire gritting decision updated: %s",
                "planned" if parsed.planned else "not planned",
            )

        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def async_clock_tick(self, _now: datetime) -> None:
        """Refresh entity availability/status as a stored decision expires."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    @staticmethod
    def _event_datetime(value: Any) -> datetime:
        """Normalise the IMAP event date to Home Assistant local time."""
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif value:
            parsed = dt_util.parse_datetime(str(value))

        if parsed is None:
            return dt_util.now()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return dt_util.as_local(parsed)

    @property
    def decision_datetime(self) -> datetime | None:
        if not self.data.decision_time:
            return None
        parsed = dt_util.parse_datetime(self.data.decision_time)
        if parsed is None:
            return None
        return dt_util.as_local(parsed)

    @property
    def treatment_datetime(self) -> datetime | None:
        if not self.data.treatment_time:
            return None
        parsed = dt_util.parse_datetime(self.data.treatment_time)
        if parsed is None:
            return None
        return dt_util.as_local(parsed)

    @property
    def is_current(self) -> bool:
        """Return whether the saved decision still describes the current night.

        A decision received today stays current until 09:00 the following day.
        A decision from yesterday remains current until 09:00 today. This lets
        an overnight run remain visible after midnight without presenting last
        night's decision as tonight's during the following daytime.
        """
        decision = self.decision_datetime
        if decision is None:
            return False

        now = dt_util.now()
        decision_date = decision.date()
        today = now.date()

        if decision_date == today:
            return True
        if decision_date == today - timedelta(days=1) and now.hour < 9:
            return True
        return False

    @property
    def status(self) -> str:
        """Return a compact human-readable state."""
        if not self.is_current:
            return "Awaiting decision"
        if not self.data.recognised or self.data.planned is None:
            return "Decision unclear"
        return "Planned" if self.data.planned else "Not planned"
