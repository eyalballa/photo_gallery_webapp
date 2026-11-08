from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

from wall.config import AppConfig, EventConfig
from wall.deps import Deps
from wall.faces import NoFaces
from wall.sources.base import SourceItem, SourceListing
from wall.store import PhotoStore

T0 = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, start: datetime = T0):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def tick(self, seconds: float = 1) -> datetime:
        self.now += timedelta(seconds=seconds)
        return self.now


class ListSource:
    """In-memory PhotoSource: set .items / .complete / .fail between passes."""

    id = "list"

    def __init__(self, *ids: str):
        self.items = [item(i) for i in ids]
        self.complete = True
        self.fail: set[str] = set()

    async def list_items(self) -> SourceListing:
        return SourceListing(items=list(self.items), complete=self.complete)

    async def download(self, it: SourceItem, max_px: int) -> bytes:
        if it.id in self.fail:
            raise OSError("boom")
        return jpeg_bytes()


def item(id: str) -> SourceItem:
    return SourceItem(id=id, created=T0, width=40, height=30, url=f"mem://{id}")


def jpeg_bytes(size=(40, 30)) -> bytes:
    import io

    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def deps(tmp_path: Path, clock: Clock) -> Deps:
    cfg = AppConfig(event=EventConfig(title="John is 8!", qr_url="https://example.com/join", album_url="https://example.com/a"),
                    data_dir=tmp_path)
    return Deps(source=ListSource("a", "b"), store=PhotoStore(":memory:"), face_detector=NoFaces(), config=cfg,
                clock=clock, passcode="cake")
