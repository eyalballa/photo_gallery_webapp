"""Every API body and every service result. The frontend's types are generated from these via OpenAPI."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

Status = Literal["pending", "ready", "failed", "removed"]


class LoginRequest(BaseModel):
    passcode: str = Field(max_length=256)


class PhotoOut(BaseModel):
    id: str
    w: int
    h: int
    aged: bool
    first_seen: datetime
    version: int
    url: str


class PhotosResponse(BaseModel):
    photos: list[PhotoOut]
    removed: list[str]
    server_time: datetime  # the client passes this back as `since`


class PublicConfig(BaseModel):
    """What the passcode screen may show to anyone with the URL."""

    login_title: str


class WallConfig(BaseModel):
    title: str
    qr_url: HttpUrl
    theme: Literal["kids", "grown", "roses"]
    background: str | None
    decorations: bool
    max_on_screen: int = Field(ge=1, le=4)
    crossing_seconds: int = Field(ge=8, le=60)
    new_marker: bool
    effect_labels: dict[str, str]


class MediaFile(BaseModel):
    path: Path
    version: int


class SyncReport(BaseModel):
    new: int
    removed: int
    total: int
    complete: bool  # False when the source listing looked truncated; removals were skipped


class ProcessReport(BaseModel):
    processed: int
    failed: int
    effects: dict[str, int] = {}


class StatusReport(BaseModel):
    counts: dict[str, int]
    last_sync: datetime | None
    last_sync_error: str | None
    source: str
