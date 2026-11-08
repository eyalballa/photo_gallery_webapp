from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, ConfigDict, SkipValidation

from wall.config import AppConfig
from wall.faces import FaceDetector
from wall.sources.base import PhotoSource
from wall.store import PhotoStore


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Deps(BaseModel):
    """Everything the service needs, injected so tests can pass fakes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: SkipValidation[PhotoSource]
    store: PhotoStore
    face_detector: SkipValidation[FaceDetector]
    config: AppConfig
    clock: Callable[[], datetime] = utcnow
    passcode: str | None = None
    session_secret: str | None = None
    cookie_secure: bool = True

    @property
    def data_dir(self) -> Path:
        return self.config.data_dir

    @property
    def originals(self) -> Path:
        return self.data_dir / "originals"

    @property
    def processed(self) -> Path:
        return self.data_dir / "processed"
