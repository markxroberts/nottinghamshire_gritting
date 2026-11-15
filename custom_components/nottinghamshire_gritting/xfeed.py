"""Best-effort reader for recent public @NottsCC posts.

The official X embedded-timeline syndication endpoint is heavily rate-limited
and returned HTTP 429 from Home Assistant. This reader instead uses FxTwitter's
documented public API to retrieve the @NottsCC timeline. FxTwitter is a
third-party bridge to public X data, so failure always falls through to the
email sources rather than making the integration unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import X_TIMELINE_URL

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class XPost:
    """One public post from @NottsCC."""

    post_id: str
    text: str
    created_at: datetime
    url: str


class XFeedError(Exception):
    """Error reading the best-effort X bridge."""


class XFeedRateLimited(XFeedError):
    """The X bridge rate-limited the request."""


async def async_fetch_nottscc_posts(hass: HomeAssistant) -> list[XPost]:
    """Fetch recent public posts from @NottsCC via FxTwitter."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            X_TIMELINE_URL,
            timeout=ClientTimeout(total=12),
        ) as response:
            if response.status == 204:
                return []
            if response.status == 429:
                raise XFeedRateLimited("FxTwitter returned HTTP 429")
            if response.status != 200:
                raise XFeedError(
                    f"FxTwitter returned HTTP {response.status}"
                )
            try:
                payload = await response.json(content_type=None)
            except (json.JSONDecodeError, TypeError, ValueError) as err:
                raise XFeedError(
                    "FxTwitter returned invalid JSON"
                ) from err
    except XFeedError:
        raise
    except (ClientError, TimeoutError) as err:
        raise XFeedError(str(err)) from err

    return parse_timeline_json(payload)


def parse_timeline_json(payload: Any) -> list[XPost]:
    """Parse the FxTwitter v2 profile-statuses response."""
    if not isinstance(payload, dict):
        raise XFeedError("FxTwitter response was not an object")

    code = payload.get("code")
    if code not in (None, 200):
        raise XFeedError(f"FxTwitter API returned code {code}")

    results = payload.get("results")
    if not isinstance(results, list):
        raise XFeedError("FxTwitter response did not contain a results list")

    posts: list[XPost] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in (None, "status"):
            continue

        author = item.get("author")
        if not isinstance(author, dict):
            continue
        if str(author.get("screen_name") or "").lower() != "nottscc":
            # Avoid treating reposted content from another account as an
            # authoritative County gritting decision.
            continue

        post_id = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        created = _parse_created_at(
            item.get("created_at"),
            item.get("created_timestamp"),
        )
        if not post_id or not text or created is None:
            continue

        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://x.com/NottsCC/status/{post_id}"

        posts.append(
            XPost(
                post_id=post_id,
                text=text,
                created_at=created,
                url=url,
            )
        )

    posts.sort(key=lambda post: post.created_at, reverse=True)
    return posts


def _parse_created_at(
    value: Any, timestamp: Any = None
) -> datetime | None:
    """Parse FxTwitter's status timestamp."""
    if timestamp is not None:
        try:
            parsed = datetime.fromtimestamp(float(timestamp), tz=dt_util.UTC)
        except (TypeError, ValueError, OSError, OverflowError):
            parsed = None
        if parsed is not None:
            return dt_util.as_local(parsed)

    if not value:
        return None

    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return dt_util.as_local(parsed)
