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
    crossing_seconds: int = Field(ge=8, le=60)
    new_marker: bool
    effect_labels: dict[str, str]


class EffectSetting(BaseModel):
    id: str
    label: str
    kind: Literal["face", "photo"]  # face: drawn on frontal faces; photo: changes the whole photo
    on: bool


class EffectsSettings(BaseModel):
    """The effect switches in the settings drawer: config.yaml's weights with the drawer's changes on top."""

    effects: list[EffectSetting]
    honoree: str | None


class EffectsUpdate(BaseModel):
    off: list[str]  # effect ids switched off; every other effect is on
    honoree: str | None = Field(None, max_length=60)


class RerollReport(BaseModel):
    queued: int  # photos sent back to processing; the background loop re-picks them on its next pass


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
