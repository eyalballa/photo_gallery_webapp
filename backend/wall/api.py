"""HTTP routes: parse the request, call WallService, return its model. No logic of its own."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from wall.schemas import EffectsSettings, EffectsUpdate, LoginRequest, PhotosResponse, PublicConfig, RerollReport, WallConfig
from wall.service import NotFound, RateLimited, UnknownEffect, WallService

COOKIE = "wall_session"

router = APIRouter()


def get_service(request: Request) -> WallService:
    return request.app.state.service


def require_session(request: Request, svc: WallService = Depends(get_service)) -> WallService:
    if not svc.session_valid(request.cookies.get(COOKIE)):
        raise HTTPException(401, "passcode required")
    return svc


@router.post("/api/login", status_code=204)
def login(req: LoginRequest, request: Request, response: Response, svc: WallService = Depends(get_service)) -> None:
    # behind Tailscale Funnel the peer is the local proxy; uvicorn takes the real IP from X-Forwarded-For
    try:
        token = svc.login(req, request.client.host if request.client else "unknown")
    except RateLimited:
        raise HTTPException(429, "too many attempts, wait a minute", headers={"Retry-After": "60"})
    if token is None:
        raise HTTPException(401, "wrong passcode")
    response.set_cookie(COOKIE, token, max_age=svc.sessions.ttl_seconds, httponly=True,
                        secure=svc.d.cookie_secure, samesite="lax")


@router.get("/api/public", response_model=PublicConfig)
def public_config(svc: WallService = Depends(get_service)) -> PublicConfig:
    return svc.get_public_config()


@router.get("/api/config", response_model=WallConfig)
def config(svc: WallService = Depends(require_session)) -> WallConfig:
    return svc.get_config()


@router.get("/api/photos", response_model=PhotosResponse)
def photos(since: datetime | None = None, svc: WallService = Depends(require_session)) -> PhotosResponse:
    return svc.list_photos(since)


@router.get("/api/effects", response_model=EffectsSettings)
def effects(svc: WallService = Depends(require_session)) -> EffectsSettings:
    return svc.get_effects()


@router.put("/api/effects", response_model=EffectsSettings)
def set_effects(req: EffectsUpdate, svc: WallService = Depends(require_session)) -> EffectsSettings:
    try:
        return svc.set_effects(req)
    except UnknownEffect as e:
        raise HTTPException(422, f"unknown effect: {e}")


@router.post("/api/effects/reroll", response_model=RerollReport)
def reroll_effects(tasks: BackgroundTasks, svc: WallService = Depends(require_session)) -> RerollReport:
    report = svc.reroll_all()
    tasks.add_task(svc.process_pending)  # now, rather than on the next sync pass (up to every_s away)
    return report


@router.get("/media/{photo_id}.jpg", response_class=FileResponse)
def media(photo_id: str, svc: WallService = Depends(require_session)) -> FileResponse:
    try:
        f = svc.get_media(photo_id)
    except NotFound:
        raise HTTPException(404, "no such photo")
    return FileResponse(f.path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
