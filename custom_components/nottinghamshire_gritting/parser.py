"""Parsers for Nottinghamshire and Nottingham City winter-service updates.

Kept free of Home Assistant imports so the parsing logic can be tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
import re

SOURCE_COUNTY_EMAIL = "county_email"
SOURCE_CITY_EMAIL = "city_email"


@dataclass(slots=True)
class ParsedDecision:
    """Parsed decision from an official gritting update."""

    planned: bool | None
    minimum_road_temperature: float | None
    treatment_time: datetime | None
    excerpt: str | None


NEGATIVE_PATTERNS = (
    re.compile(
        r"\bno\s+(?:precautionary\s+)?(?:gritting|treatment|salting)\s+"
        r"(?:is\s+)?(?:planned|required|scheduled)\b",
        re.I,
    ),
    re.compile(
        r"\bno\s+(?:gritting|treatment|salting)\s+(?:is\s+)?(?:needed|required)\b",
        re.I,
    ),
    re.compile(r"\bno\s+(?:winter\s+)?action\s+(?:is\s+)?required\b", re.I),
    re.compile(r"\bgritters?\s+(?:will\s+)?not\s+be\s+out\b", re.I),
    re.compile(r"\bno\s+gritters?\s+(?:are\s+)?(?:required|planned)\b", re.I),
    re.compile(r"\b(?:we\s+)?(?:will\s+not|won't)\s+be\s+(?:gritting|treating|salting)\b", re.I),
    re.compile(r"\bno\s+plans?\s+to\s+(?:grit|treat|salt)\b", re.I),
)

POSITIVE_PATTERNS = (
    re.compile(r"\bgritters?\s+(?:will\s+be|will\s+go|are\s+going)\s+out\b", re.I),
    re.compile(r"\bgritting\s+teams?\s+(?:will\s+be|are)\s+(?:\w+\s+){0,3}out\b", re.I),
    re.compile(
        r"\bgritting\s+teams?\s+(?:are\s+)?(?:set|scheduled|due)\s+to\s+"
        r"(?:go\s+out|head\s+out|take\s+to\s+the\s+roads|begin\s+salting)\b",
        re.I,
    ),
    re.compile(r"\bgritters?\s+are(?:\s+\w+){0,4}\s+out\b", re.I),
    re.compile(r"\bgritters?\s+(?:are\s+)?heading\s+out\b", re.I),
    re.compile(r"\bgritters?\s+out\s+(?:tonight|this\s+evening|overnight)\b", re.I),
    re.compile(r"\b(?:we(?:'re| are)?\s+)?planning\s+to\s+(?:grit|treat|salt)\b", re.I),
    re.compile(r"\bwe(?:'ll| will)\s+be\s+(?:gritting|treating|salting)\b", re.I),
    re.compile(r"\bwe(?:'re| are)\s+(?:gritting|treating|salting)\b", re.I),
    re.compile(r"\bgritters?\s+(?:will\s+)?(?:treat|grit|salt)\b", re.I),
    re.compile(
        r"\b(?:gritting|treatment|salting)\s+(?:is\s+)?(?:planned|scheduled|required)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:precautionary\s+)?treatment\s+(?:will\s+)?"
        r"(?:take\s+place|be\s+carried\s+out)\b",
        re.I,
    ),
    re.compile(r"\bnext\s+scheduled\s+run\b", re.I),
    re.compile(
        r"\b(?:main\s+)?routes?\s+(?:will\s+be|are\s+being|to\s+be)\s+"
        r"(?:gritted|treated|salted)\b",
        re.I,
    ),
    re.compile(
        r"\broads?\s+(?:will\s+be|are\s+being|to\s+be)\s+"
        r"(?:gritted|treated|salted)\b",
        re.I,
    ),
)

RELEVANCE_MARKERS = (
    "grit",
    "gritter",
    "winter service",
    "winter weather",
    "road temperature",
    "road surface temperature",
    "precautionary treatment",
    "scheduled run",
    "salt",
    "salting",
)

COUNTY_MARKERS = (
    "nottinghamshire county council",
    "nottinghamshire.gov.uk",
    "nottscc",
    "via east midlands",
    "viaem.co.uk",
)

CITY_MARKERS = (
    "nottingham city council",
    "nottinghamcity.gov.uk",
    "nottinghamcity",
    "transport nottingham",
    "nottmtravelwise",
    "my nottingham",
    "mynottingham",
)

TEMP_PATTERNS = (
    re.compile(
        r"road(?:\s+surface)?\s+temperatures?.{0,55}?"
        r"(?:as\s+low\s+as|forecast(?:\s+to)?|down\s+to|minimum(?:\s+of)?|min(?:imum)?\.?\s*)?"
        r"\s*(-?\d{1,2}(?:\.\d+)?)\s*(?:(?:°|º|˚)\s*)?(?:[cC]\b)?",
        re.I | re.S,
    ),
    re.compile(
        r"(?:minimum|min)\s+road(?:\s+surface)?\s+temperature.{0,25}?"
        r"(-?\d{1,2}(?:\.\d+)?)\s*(?:(?:°|º|˚)\s*)?(?:[cC]\b)?",
        re.I | re.S,
    ),
)

TIME_PATTERNS = (
    re.compile(
        r"(?:next\s+scheduled\s+run|gritters?[^\n.]{0,60}?(?:out|route)|"
        r"(?:gritting|treatment|salting)[^\n.]{0,50}?)"
        r"[^\n.]{0,40}?\b(?:from|at|commencing|starts?|start(?:ing)?)?\s*"
        r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:from|at|commencing)\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b",
        re.I,
    ),
)


def normalise_text(value: str | None) -> str:
    """Convert HTML-ish/plain content into compact readable text."""
    if not value:
        return ""
    text = unescape(value)
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(?:p|div|li|tr|h\d)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _combined(subject: str | None, body: str | None, sender: str | None) -> str:
    return " ".join(
        (normalise_text(subject), normalise_text(body), normalise_text(sender))
    ).lower()


def classify_email_source(
    subject: str | None, body: str | None, sender: str | None
) -> str | None:
    """Classify a relevant official winter-service email by authority."""
    combined = _combined(subject, body, sender)
    if not any(marker in combined for marker in RELEVANCE_MARKERS):
        return None

    # Test City first so a City bulletin mentioning the wider county does not
    # accidentally become a Nottinghamshire County decision.
    if any(marker in combined for marker in CITY_MARKERS):
        return SOURCE_CITY_EMAIL
    if any(marker in combined for marker in COUNTY_MARKERS):
        return SOURCE_COUNTY_EMAIL
    return None


def is_relevant_message(
    subject: str | None, body: str | None, sender: str | None
) -> bool:
    """Backward-compatible relevance helper for County messages."""
    return classify_email_source(subject, body, sender) == SOURCE_COUNTY_EMAIL


def is_gritting_update_text(text: str | None) -> bool:
    """Return whether authoritative social text is potentially about gritting."""
    normalised = normalise_text(text).lower()
    return any(marker in normalised for marker in RELEVANCE_MARKERS)


def _first_decision_match(text: str) -> tuple[bool | None, re.Match[str] | None]:
    for pattern in NEGATIVE_PATTERNS:
        if match := pattern.search(text):
            return False, match
    for pattern in POSITIVE_PATTERNS:
        if match := pattern.search(text):
            return True, match
    return None, None


def _extract_temperature(text: str) -> float | None:
    for pattern in TEMP_PATTERNS:
        if match := pattern.search(text):
            try:
                value = float(match.group(1))
            except (TypeError, ValueError):
                continue
            if -30 <= value <= 20:
                return value
    return None


def _extract_treatment_time(text: str, decision_time: datetime) -> datetime | None:
    for pattern in TIME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3).lower()
        if hour < 1 or hour > 12 or minute > 59:
            continue
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        candidate = decision_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        # A treatment clock time substantially earlier than the update time is
        # normally a run after midnight, rather than one already completed.
        if candidate < decision_time - timedelta(hours=4):
            candidate += timedelta(days=1)
        return candidate
    return None


def _make_excerpt(text: str, match: re.Match[str] | None) -> str | None:
    if not text:
        return None
    if match is None:
        return text[:350]
    start = max(0, match.start() - 120)
    end = min(len(text), match.end() + 220)
    return text[start:end].strip()[:500]


def parse_message(
    subject: str | None, body: str | None, decision_time: datetime
) -> ParsedDecision:
    """Parse an official winter-service email or social post."""
    text = normalise_text("\n".join(filter(None, (subject, body))))
    planned, decision_match = _first_decision_match(text)
    return ParsedDecision(
        planned=planned,
        minimum_road_temperature=_extract_temperature(text),
        treatment_time=(
            _extract_treatment_time(text, decision_time) if planned else None
        ),
        excerpt=_make_excerpt(text, decision_match),
    )
