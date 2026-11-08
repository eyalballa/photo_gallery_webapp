"""All behaviour lives here. The API (api.py) and the CLI (cli.py) are thin adapters over WallService."""

import asyncio
import hmac
import logging
import secrets
import shutil
from datetime import datetime

from wall.auth import RateLimiter, Sessions
from wall.deps import Deps
from wall.effects import EFFECTS
from wall.process import process_one
from wall.schemas import LoginRequest, MediaFile, PhotoOut, PhotosResponse, ProcessReport, PublicConfig, StatusReport, SyncReport, WallConfig
from wall.store import ProcessedFields
from wall.sync import describe, sync_once

log = logging.getLogger(__name__)


class NotFound(Exception):
    pass


class RateLimited(Exception):
    pass


class WallService:
    def __init__(self, deps: Deps):
        self.d = deps
        # the passcode is part of the key, so changing PASSCODE ends every existing session
        self.sessions = Sessions(f"{deps.session_secret or secrets.token_hex(32)}:{deps.passcode or ''}", deps.clock)
        self.login_limit = RateLimiter(deps.clock)
        self.global_login_limit = RateLimiter(deps.clock, limit=30)  # caps guessing from many IPs at once

    def get_public_config(self) -> PublicConfig:
        return PublicConfig(login_title=self.d.config.event.login_title)

    def get_config(self) -> WallConfig:
        c = self.d.config
        return WallConfig(
            title=c.event.title,
            qr_url=c.event.qr_url,
            theme=c.display.theme,
            background=c.display.background,
            decorations=c.display.decorations,
            max_on_screen=c.display.max_on_screen,
            crossing_seconds=c.display.crossing_seconds,
            new_marker=c.display.new_marker,
            effect_labels={eid: e.label for eid, e in sorted(EFFECTS.items())},
        )

    def list_photos(self, since: datetime | None) -> PhotosResponse:
        now = self.d.clock()
        rows = self.d.store.ready_since(since)
        return PhotosResponse(
            photos=[
                PhotoOut(
                    id=r.id, w=r.width, h=r.height, aged=r.aged_paper, first_seen=r.first_seen_at,
                    version=r.version, url=f"/media/{r.id}.jpg?v={r.version}",
                )
                for r in rows
            ],
            removed=self.d.store.removed_since(since),
            server_time=now,
        )

    def get_media(self, photo_id: str) -> MediaFile:
        row = self.d.store.get(photo_id)
        path = self.d.processed / f"{photo_id}.jpg"
        if row is None or row.status != "ready" or not path.exists():
            raise NotFound(photo_id)
        return MediaFile(path=path, version=row.version)

    def check_passcode(self, req: LoginRequest) -> bool:
        expected = self.d.passcode
        return expected is not None and hmac.compare_digest(req.passcode.encode(), expected.encode())

    def login(self, req: LoginRequest, client: str) -> str | None:
        """A new session token, or None for a wrong passcode.
        Raises RateLimited past 5 attempts/min per client or 30/min in total."""
        if not self.login_limit.allow(client) or not self.global_login_limit.allow("*"):
            raise RateLimited(client)
        return self.sessions.issue() if self.check_passcode(req) else None

    def session_valid(self, token: str | None) -> bool:
        return self.sessions.valid(token)

    async def sync_once(self) -> SyncReport:
        try:
            report = await sync_once(self.d.source, self.d.store, self.d.clock, self.d.originals)
        except Exception as e:
            self.d.store.set_meta("last_sync_error", describe(e))
            raise
        self.d.store.set_meta("last_sync", self.d.clock().isoformat())
        self.d.store.set_meta("last_sync_error", None)
        return report

    async def process_pending(self, limit: int | None = None) -> ProcessReport:
        report = ProcessReport(processed=0, failed=0)
        for row in self.d.store.pending(limit):
            try:
                # face detection is CPU-bound; keep it off the event loop so the API stays responsive
                fields = await asyncio.to_thread(
                    process_one, row.id, self.d.originals / f"{row.id}.jpg", self.d.processed / f"{row.id}.jpg",
                    self.d.face_detector, self.d.config.effects, row.reroll_salt,
                )
                report.processed += 1
                key = fields.effect or "none"
                report.effects[key] = report.effects.get(key, 0) + 1
            except Exception as e:
                log.exception("processing %s failed", row.id)
                fields = ProcessedFields(status="failed", width=row.width, height=row.height, faces=None,
                                         effect=None, variant=None, aged_paper=False, error=str(e))
                report.failed += 1
            self.d.store.save_processed(row.id, fields, self.d.clock())
        return report

    async def reroll(self, photo_id: str | None) -> ProcessReport:
        if photo_id and self.d.store.get(photo_id) is None:
            raise NotFound(photo_id)
        self.d.store.queue_reroll(photo_id)
        return await self.process_pending()

    def status(self) -> StatusReport:
        last = self.d.store.get_meta("last_sync")
        return StatusReport(
            counts=self.d.store.counts(),
            last_sync=datetime.fromisoformat(last) if last else None,
            last_sync_error=self.d.store.get_meta("last_sync_error"),
            source=self.d.source.id,
        )

    def wipe(self) -> None:
        self.d.store.wipe()
        for folder in (self.d.originals, self.d.processed):
            shutil.rmtree(folder, ignore_errors=True)
