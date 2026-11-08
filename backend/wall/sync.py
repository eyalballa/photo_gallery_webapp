"""One sync pass: diff the album against the store, download new photos, mark missing ones removed."""

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx

from wall.schemas import SyncReport
from wall.sources.base import PhotoSource, SourceItem
from wall.store import PhotoRow, PhotoStore

log = logging.getLogger(__name__)
DOWNLOAD_PX = 1600
DOWNLOAD_CONCURRENCY = 6
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,200}")  # ids become file names, so no dots or slashes


def describe(e: Exception) -> str:
    """An error message without URLs: httpx puts the request URL (signed photo links, the album key) in its errors."""
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    if isinstance(e, httpx.HTTPError):
        return type(e).__name__
    return f"{type(e).__name__}: {e}"


async def sync_once(source: PhotoSource, store: PhotoStore, clock: Callable[[], datetime], originals: Path) -> SyncReport:
    listing = await source.list_items()
    for bad in [i.id for i in listing.items if not SAFE_ID.fullmatch(i.id)]:
        log.warning("skipping item with unsafe id %r", bad)
    listing = listing.model_copy(update={"items": [i for i in listing.items if SAFE_ID.fullmatch(i.id)]})
    known = store.known_ids()
    seen = {i.id for i in listing.items}
    originals.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

    async def fetch(item: SourceItem) -> bool:
        async with sem:
            try:
                # Share-link URLs can expire, so download as soon as an item shows up.
                (originals / f"{item.id}.jpg").write_bytes(await source.download(item, DOWNLOAD_PX))
            except Exception as e:  # retried on the next pass, since the item is still unknown
                log.warning("download failed for %s: %s", item.id, describe(e))
                return False
        store.insert_pending(
            PhotoRow(
                id=item.id, source=source.id, url=item.url, created_at=item.created, first_seen_at=clock(),
                status="pending", width=item.width, height=item.height,
            )
        )
        return True

    results = await asyncio.gather(*(fetch(i) for i in listing.items if i.id not in known))
    new = sum(results)

    removed = 0
    if listing.complete:  # a truncated listing must not make photos vanish from the wall
        for gone in known - seen:
            store.mark_removed(gone, clock())
            removed += 1
    return SyncReport(new=new, removed=removed, total=len(seen), complete=listing.complete)


async def run_periodically(every_s: float, job: Callable[[], object], name: str) -> None:
    """Runs `job` forever, logging (not raising) its errors so one bad pass doesn't stop the wall."""
    while True:
        try:
            result = job()
            if asyncio.iscoroutine(result):
                await result
        except httpx.HTTPError as e:  # no traceback: it would carry the request URL
            log.error("%s failed: %s", name, describe(e))
        except Exception:
            log.exception("%s failed", name)
        await asyncio.sleep(every_s)
