"""A folder of local images as a photo source (`--source fake:<dir>`), used by tests and offline runs."""

import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from wall.sources.base import SourceItem, SourceListing

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class FakePhotoSource:
    id = "fake"

    def __init__(self, folder: Path):
        self.folder = folder

    async def list_items(self) -> SourceListing:
        items = []
        for p in sorted(self.folder.iterdir()):
            if p.suffix.lower() not in EXTENSIONS:
                continue
            with Image.open(p) as im:
                w, h = im.size
            items.append(
                SourceItem(
                    id=p.stem,
                    created=datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc),
                    width=w,
                    height=h,
                    url=str(p),
                )
            )
        return SourceListing(items=items, complete=True)

    async def download(self, item: SourceItem, max_px: int) -> bytes:
        with Image.open(item.url) as im:
            im.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=90, exif=im.info.get("exif", b""))
            return buf.getvalue()
