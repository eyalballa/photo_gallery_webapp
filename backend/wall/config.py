from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILES = (".env", "../.env")


class AuthSettings(BaseSettings):
    """Wall access, from `.env` / the environment. `serve` refuses to start without a passcode."""

    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    passcode: str | None = None
    session_secret: str | None = None  # unset: a random one per process, so sessions end on restart
    cookie_secure: bool = True  # false only for plain-http testing on a LAN IP


class EventConfig(BaseModel):
    title: str = "Happy Birthday!"  # the wall's header and tab, after login
    login_title: str = "Photo wall"  # the passcode screen: public, so keep names out of it
    qr_url: HttpUrl
    album_url: HttpUrl  # the shared album's link; read by ShareLinkSource


class DisplayConfig(BaseModel):
    theme: Literal["kids", "grown", "roses"] = "kids"
    background: str | None = None
    decorations: bool = True
    crossing_seconds: int = Field(24, ge=8, le=60)
    new_marker: bool = True


class EffectsConfig(BaseModel):
    # Every live effect, by id (`python -m wall effects` lists them). 0 turns one off; a missing id uses the effect's
    # own default weight.
    weights: dict[str, float] = {
        "glasses": 25, "circus_glasses": 15, "mustache": 25, "party_hat": 25, "vintage": 25,
        "pop_art": 10, "sketch": 10, "wanted": 10, "big_eyes": 10, "confetti": 10, "cake_frame": 10,
    }
    honoree: str | None = None  # the name on the cake frame; None prints "Happy Birthday!" alone
    min_face_px: int = 60
    max_yaw: float = 0.35  # |yaw proxy| above this skips accessories and falls back to vintage


class SyncConfig(BaseModel):
    every_s: int = Field(90, ge=10)


class AppConfig(BaseModel):
    event: EventConfig
    display: DisplayConfig = DisplayConfig()
    effects: EffectsConfig = EffectsConfig()
    sync: SyncConfig = SyncConfig()
    data_dir: Path = Path("data")

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        return cls.model_validate(yaml.safe_load(path.read_text()) or {})
