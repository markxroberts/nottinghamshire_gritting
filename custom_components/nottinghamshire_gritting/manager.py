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

from .const import (
    SIGNAL_UPDATE,
    SOURCE_CITY_EMAIL,
    SOURCE_COUNTY_EMAIL,
    SOURCE_COUNTY_X,
    SOURCE_LABELS,
    SOURCE_PRIORITY,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .parser import (
    classify_email_source,
    is_gritting_update_text,
    parse_message,
)
from .xfeed import XFeedError, async_fetch_nottscc_posts

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GrittingData:
    """One gritting decision from one source."""

    planned: bool | None = None
    decision_time: str | None = None
    subject: str | None = None
    sender: str | None = None
    uid: str | None = None
    minimum_road_temperature: float | None = None
    treatment_time: str | None = None
    excerpt: str | None = None
    recognised: bool = False
    source: str | None = None
    confidence: str | None = None
    source_url: str | None = None


class GrittingManager:
    """Combine County X, County email and City proxy decisions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._decisions: dict[str, GrittingData] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

        self.x_available: bool | None = None
        self.x_last_check: str | None = None
        self.x_last_success: str | None = None
        self.x_last_error: str | None = None

    async def async_load(self) -> None:
        """Load stored decisions, including migration from the v0.1 flat format."""
        stored = await self._store.async_load()
        if not stored:
            return

        try:
            sources = stored.get("sources")
            if isinstance(sources, dict):
                for source, payload in sources.items():
                    if isinstance(payload, dict):
                        self._decisions[source] = GrittingData(**payload)
                return

            # v0.1.x stored one flat County-email decision.
            legacy = dict(stored)
            legacy.setdefault("source", SOURCE_COUNTY_EMAIL)
            legacy.setdefault("confidence", "confirmed")
            self._decisions[SOURCE_COUNTY_EMAIL] = GrittingData(**legacy)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Ignoring incompatible stored Nottinghamshire gritting data"
            )

    async def async_handle_imap_event(self, event: Event) -> None:
        """Handle an imap_content event from County or City."""
        payload = event.data

        # Home Assistant sets initial=False when the same last message is
        # emitted again; only act on the initial arrival.
        if payload.get("initial") is False:
            return

        subject = str(payload.get("subject") or "")
        sender = str(payload.get("sender") or "")
        body = str(payload.get("text") or payload.get("custom") or "")

        source = classify_email_source(subject, body, sender)
        if source is None:
            return

        decision_dt = self._event_datetime(payload.get("date"))
        parsed = parse_message(subject, body, decision_dt)

        # Nottingham City is only a positive proxy. Different parts of the
        # county can be colder than the city, so a City "no grit" decision must
        # never turn the County sensor off.
        if source == SOURCE_CITY_EMAIL and parsed.planned is not True:
            _LOGGER.debug(
                "Ignoring Nottingham City winter-service email as a County "
                "fallback because it does not positively announce gritting"
            )
            return

        data = GrittingData(
            planned=parsed.planned,
            decision_time=decision_dt.isoformat(),
            subject=subject or None,
            sender=sender or None,
            uid=(
                str(payload.get("uid"))
                if payload.get("uid") is not None
                else None
            ),
            minimum_road_temperature=parsed.minimum_road_temperature,
            treatment_time=(
                parsed.treatment_time.isoformat()
                if parsed.treatment_time
                else None
            ),
            excerpt=parsed.excerpt,
            recognised=parsed.planned is not None,
            source=source,
            confidence=(
                "inferred" if source == SOURCE_CITY_EMAIL else "confirmed"
            ),
        )
        self._decisions[source] = data
        await self._async_save()

        if parsed.planned is None:
            _LOGGER.warning(
                "Received a Nottinghamshire County winter-service message but "
                "could not determine whether gritting is planned. Subject: %s",
                subject,
            )
        else:
            _LOGGER.info(
                "%s gritting decision updated: %s",
                SOURCE_LABELS[source],
                "planned" if parsed.planned else "not planned",
            )

        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def async_refresh_x(self, _now: datetime | None = None) -> None:
        """Refresh the preferred @NottsCC X source."""
        now = dt_util.now()
        self.x_last_check = now.isoformat()

        try:
            posts = await async_fetch_nottscc_posts(self.hass)
        except XFeedError as err:
            self.x_available = False
            self.x_last_error = str(err)
            _LOGGER.debug("Unable to refresh @NottsCC X feed: %s", err)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE)
            return

        self.x_available = True
        self.x_last_success = now.isoformat()
        self.x_last_error = None

        selected: GrittingData | None = None
        for post in posts:
            if not self._is_datetime_current(post.created_at):
                continue
            if not is_gritting_update_text(post.text):
                continue

            parsed = parse_message(None, post.text, post.created_at)
            if parsed.planned is None:
                # The account often posts general winter/gritting information;
                # only an explicit operational decision should be authoritative.
                continue

            selected = GrittingData(
                planned=parsed.planned,
                decision_time=post.created_at.isoformat(),
                subject="@NottsCC on X",
                sender="@NottsCC",
                uid=post.post_id,
                minimum_road_temperature=parsed.minimum_road_temperature,
                treatment_time=(
                    parsed.treatment_time.isoformat()
                    if parsed.treatment_time
                    else None
                ),
                excerpt=parsed.excerpt,
                recognised=True,
                source=SOURCE_COUNTY_X,
                confidence="confirmed",
                source_url=post.url,
            )
            break

        if selected is not None:
            existing = self._decisions.get(SOURCE_COUNTY_X)
            if existing != selected:
                self._decisions[SOURCE_COUNTY_X] = selected
                await self._async_save()
                _LOGGER.info(
                    "@NottsCC X gritting decision updated: %s",
                    "planned" if selected.planned else "not planned",
                )

        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def async_clock_tick(self, _now: datetime) -> None:
        """Refresh entity availability/status as stored decisions expire."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def _async_save(self) -> None:
        """Persist all source decisions."""
        await self._store.async_save(
            {
                "sources": {
                    source: asdict(data)
                    for source, data in self._decisions.items()
                }
            }
        )

    @staticmethod
    def _event_datetime(value: Any) -> datetime:
        """Normalise an IMAP event date to Home Assistant local time."""
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

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return dt_util.as_local(parsed)

    @staticmethod
    def _is_datetime_current(decision: datetime) -> bool:
        """Return whether a timestamp still describes the current night."""
        decision = dt_util.as_local(decision)
        now = dt_util.now()
        decision_date = decision.date()
        today = now.date()

        if decision_date == today:
            # Before 09:00, a post/update from the early hours still belongs to
            # the overnight period just ending. After 09:00, do not let a 02:00
            # or 06:00 operational update remain displayed as tonight's plan.
            if now.hour < 9:
                return True
            return decision.hour >= 9

        if decision_date == today - timedelta(days=1) and now.hour < 9:
            return True
        return False

    def _is_current_decision(self, data: GrittingData) -> bool:
        decision = self._parse_datetime(data.decision_time)
        return decision is not None and self._is_datetime_current(decision)

    @property
    def data(self) -> GrittingData:
        """Return the highest-priority current decision."""
        for source in SOURCE_PRIORITY:
            candidate = self._decisions.get(source)
            if candidate is None or not self._is_current_decision(candidate):
                continue
            if source == SOURCE_CITY_EMAIL and candidate.planned is not True:
                continue
            return candidate
        return GrittingData()

    @property
    def decision_datetime(self) -> datetime | None:
        return self._parse_datetime(self.data.decision_time)

    @property
    def treatment_datetime(self) -> datetime | None:
        return self._parse_datetime(self.data.treatment_time)

    @property
    def is_current(self) -> bool:
        """Return whether there is a current effective decision."""
        return self.decision_datetime is not None

    @property
    def status(self) -> str:
        """Return a compact human-readable state."""
        data = self.data
        if not self.is_current:
            return "Awaiting decision"
        if not data.recognised or data.planned is None:
            return "Decision unclear"
        if data.source == SOURCE_CITY_EMAIL:
            return "Likely — Nottingham City proxy"
        return "Planned" if data.planned else "Not planned"

    @property
    def source_label(self) -> str | None:
        """Human-readable effective source."""
        source = self.data.source
        return SOURCE_LABELS.get(source) if source else None
