"""Best-effort reader for the public @NottsCC X timeline.

X does not provide a free RSS feed. This uses the same public syndication
timeline endpoint used by X's embedded timeline widget. It requires no API key,
but it is intentionally treated as best-effort because the endpoint is
undocumented and may rate-limit or change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
import json
import logging
import re
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import X_TIMELINE_URL

_LOGGER = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class XPost:
    """One public post from @NottsCC."""

    post_id: str
    text: str
    created_at: datetime
    url: str


class XFeedError(Exception):
    """Base error for the best-effort X feed."""


class XFeedRateLimited(XFeedError):
    """The X syndication endpoint rate-limited the request."""


async def async_fetch_nottscc_posts(hass: HomeAssistant) -> list[XPost]:
    """Fetch recent public posts from @NottsCC."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            X_TIMELINE_URL,
            headers={"User-Agent": _USER_AGENT},
            timeout=ClientTimeout(total=12),
        ) as response:
            if response.status == 429:
                raise XFeedRateLimited("X syndication returned HTTP 429")
            if response.status != 200:
                raise XFeedError(
                    f"X syndication returned HTTP {response.status}"
                )
            payload = await response.text()
    except XFeedError:
        raise
    except (ClientError, TimeoutError) as err:
        raise XFeedError(str(err)) from err

    return parse_timeline_html(payload)


def parse_timeline_html(payload: str) -> list[XPost]:
    """Parse X's embedded timeline HTML into recent @NottsCC posts."""
    match = _NEXT_DATA_RE.search(payload)
    if not match:
        raise XFeedError("X syndication response did not contain __NEXT_DATA__")

    try:
        data = json.loads(unescape(match.group(1)))
        entries = data["props"]["pageProps"]["timeline"]["entries"]
    except (KeyError, TypeError, json.JSONDecodeError) as err:
        raise XFeedError("X syndication timeline format was not recognised") from err

    posts: list[XPost] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            tweet = entry["content"]["tweet"]
        except (KeyError, TypeError):
            continue
        if not isinstance(tweet, dict):
            continue

        user = tweet.get("user")
        if not isinstance(user, dict):
            continue
        if str(user.get("screen_name") or "").lower() != "nottscc":
            # Avoid treating a retweet of another account as a County decision.
            continue

        post_id = str(tweet.get("id_str") or tweet.get("id") or "")
        text = str(tweet.get("full_text") or tweet.get("text") or "").strip()
        created = _parse_created_at(tweet.get("created_at"))
        if not post_id or not text or created is None:
            continue

        permalink = str(tweet.get("permalink") or "").strip()
        if permalink.startswith("http://") or permalink.startswith("https://"):
            url = permalink
        elif permalink:
            url = f"https://x.com{permalink if permalink.startswith('/') else '/' + permalink}"
        else:
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


def _parse_created_at(value: Any) -> datetime | None:
    """Parse the timestamp used in the syndication timeline."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return dt_util.as_local(parsed)
