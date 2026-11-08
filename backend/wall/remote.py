"""Typed HTTP client for a running server: same schemas, same calls as WallService (for routed methods)."""

from datetime import datetime

import httpx

from wall.schemas import LoginRequest, PhotosResponse, PublicConfig, WallConfig


class RemoteError(Exception):
    pass


class RemoteWall:
    def __init__(self, base_url: str, passcode: str | None = None, http: httpx.Client | None = None):
        self.http = http or httpx.Client(base_url=base_url, timeout=30)
        if passcode is not None and not self.check_passcode(LoginRequest(passcode=passcode)):
            raise RemoteError("wrong passcode")

    def _get(self, path: str, **params) -> httpx.Response:
        r = self.http.get(path, params={k: v for k, v in params.items() if v is not None})
        if r.status_code >= 400:
            raise RemoteError(f"{r.status_code} {r.text}")
        return r

    def check_passcode(self, req: LoginRequest) -> bool:
        return self.http.post("/api/login", json=req.model_dump()).status_code == 204

    def get_public_config(self) -> PublicConfig:
        return PublicConfig.model_validate_json(self._get("/api/public").content)

    def get_config(self) -> WallConfig:
        return WallConfig.model_validate_json(self._get("/api/config").content)

    def list_photos(self, since: datetime | None) -> PhotosResponse:
        return PhotosResponse.model_validate_json(self._get("/api/photos", since=since.isoformat() if since else None).content)

    def get_media_bytes(self, photo_id: str) -> bytes:
        return self._get(f"/media/{photo_id}.jpg").content
