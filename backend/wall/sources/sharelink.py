"""Reads a Google Photos shared album through its public link (see docs/M0.md, "Share-link spike").

The album page embeds its items as JSON in an `AF_initDataCallback({key: 'ds:1', ...})` block. The
format is undocumented, so parsing is kept in one small pure function tested against a saved page.
"""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from wall.sources.base import SourceItem, SourceListing

log = logging.getLogger(__name__)

# The short link only redirects for non-browser clients; the album page only renders data for browsers.
RESOLVE_UA = "python-httpx"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
VIDEO_KEY = "76647426"
_DS1 = re.compile(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", re.S)


class ShareLinkFormatError(Exception):
    pass


def parse_album(html: str) -> SourceListing:
    """Extracts photo items (videos skipped) from an album page."""
    m = _DS1.search(html)
    if not m:
        raise ShareLinkFormatError("ds:1 data block not found")
    try:
        data = json.loads(m.group(1))
        raw_items = data[1] or []
        has_more = bool(data[2])
        total = data[3][21] if isinstance(data[3], list) and len(data[3]) > 21 else None
    except (ValueError, IndexError, TypeError) as e:
        raise ShareLinkFormatError(f"unexpected ds:1 layout: {e}") from e

    items = []
    for it in raw_items:
        try:
            extra = it[-1] if isinstance(it[-1], dict) else {}
            if VIDEO_KEY in extra:
                continue
            items.append(
                SourceItem(
                    id=it[0],
                    created=datetime.fromtimestamp(it[5] / 1000, tz=timezone.utc),
                    width=it[1][1],
                    height=it[1][2],
                    url=it[1][0],
                )
            )
        except (ValueError, IndexError, TypeError) as e:
            raise ShareLinkFormatError(f"unexpected item layout: {e}") from e
    complete = not has_more and (total is None or total == len(raw_items))
    if not complete:
        log.warning("album listing looks truncated: %d items on page, total=%s, more=%s", len(raw_items), total, has_more)
    return SourceListing(items=items, complete=complete)


class ShareLinkSource:
    id = "sharelink"

    def __init__(self, album_url: str, http: httpx.AsyncClient):
        self.album_url, self.http = album_url, http
        self._page_url: str | None = None

    async def _resolve(self) -> str:
        if self._page_url is None:
            r = await self.http.get(self.album_url, headers={"User-Agent": RESOLVE_UA}, follow_redirects=False)
            self._page_url = str(r.url.join(r.headers["location"])) if r.is_redirect else self.album_url
        return self._page_url

    async def list_items(self) -> SourceListing:
        r = await self.http.get(await self._resolve(), headers={"User-Agent": BROWSER_UA}, follow_redirects=True)
        r.raise_for_status()
        return parse_album(r.text)

    async def download(self, item: SourceItem, max_px: int) -> bytes:
        url = httpx.URL(item.url)
        if url.scheme != "https" or not url.host.endswith(".googleusercontent.com"):
            raise ShareLinkFormatError(f"refusing photo URL on host {url.host!r}")  # the server must not fetch arbitrary URLs
        r = await self.http.get(f"{item.url}=w{max_px}-h{max_px}", follow_redirects=True)
        r.raise_for_status()
        return r.content
