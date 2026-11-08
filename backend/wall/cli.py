"""`python -m wall …`: thin Typer adapter over WallService (or RemoteWall with --remote)."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
from pydantic import BaseModel

from wall.auth import weak_passcode, weak_session_secret
from wall.config import AppConfig
from wall.deps import Deps
from wall.remote import RemoteError, RemoteWall
from wall.schemas import LoginRequest
from wall.service import NotFound, WallService
from wall.store import PhotoStore

app = typer.Typer(no_args_is_help=True, help="Birthday photo wall.")


class Ctx(BaseModel):
    config: Path
    source: str | None
    remote: str | None
    passcode: str | None
    json_out: bool


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[Path, typer.Option(help="config.yaml path")] = Path("config.yaml"),
    source: Annotated[Optional[str], typer.Option(help="sharelink (default) or fake:<dir>")] = None,
    remote: Annotated[Optional[str], typer.Option(help="URL of a running server")] = None,
    passcode: Annotated[Optional[str], typer.Option(help="passcode for --remote", envvar="WALL_PASSCODE")] = None,
    json_out: Annotated[bool, typer.Option("--json", help="print models as JSON")] = False,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines carry signed photo URLs
    ctx.obj = Ctx(config=config, source=source, remote=remote, passcode=passcode, json_out=json_out)


def build_deps(c: Ctx, detector: bool = True) -> Deps:
    """Wires the real dependencies. Kept here so the API and the CLI build them the same way."""
    from wall.config import AuthSettings
    from wall.faces import MediaPipeDetector, NoFaces
    from wall.sources.fake import FakePhotoSource
    from wall.sources.sharelink import ShareLinkSource

    cfg = AppConfig.load(c.config)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    if c.source and c.source.startswith("fake:"):
        source = FakePhotoSource(Path(c.source[5:]))
    else:
        source = ShareLinkSource(str(cfg.event.album_url), httpx.AsyncClient(timeout=30))
    auth = AuthSettings()
    return Deps(
        source=source,
        store=PhotoStore(cfg.data_dir / "wall.db"),
        face_detector=MediaPipeDetector() if detector else NoFaces(),
        config=cfg,
        passcode=auth.passcode,
        session_secret=auth.session_secret,
        cookie_secure=auth.cookie_secure,
    )


def _svc(ctx: typer.Context, detector: bool = False) -> WallService:
    return WallService(build_deps(ctx.obj, detector))


def _remote(ctx: typer.Context) -> RemoteWall | None:
    c: Ctx = ctx.obj
    return RemoteWall(c.remote, c.passcode) if c.remote else None


def _local_only(ctx: typer.Context, name: str) -> None:
    if ctx.obj.remote:
        typer.secho(f"`{name}` has no route; running locally", fg="yellow", err=True)


def out(ctx: typer.Context, model: BaseModel, human: str | None = None) -> None:
    if ctx.obj.json_out or human is None:
        typer.echo(model.model_dump_json(indent=2))
    else:
        typer.echo(human)


@app.command("public-config")
def public_config(ctx: typer.Context) -> None:
    """Show what the passcode screen shows (GET /api/public, no passcode needed)."""
    r = _remote(ctx)
    out(ctx, r.get_public_config() if r else _svc(ctx).get_public_config())


@app.command()
def config(ctx: typer.Context) -> None:
    """Show the wall config (GET /api/config)."""
    r = _remote(ctx)
    out(ctx, r.get_config() if r else _svc(ctx).get_config())


@app.command()
def photos(ctx: typer.Context, since: Annotated[Optional[datetime], typer.Option()] = None) -> None:
    """List ready photos (GET /api/photos)."""
    r = _remote(ctx)
    res = r.list_photos(since) if r else _svc(ctx).list_photos(since)
    lines = [f"{p.id[:24]:<24} {p.w}x{p.h} v{p.version}{' aged' if p.aged else ''}" for p in res.photos]
    out(ctx, res, "\n".join(lines + [f"{len(res.photos)} photos, {len(res.removed)} removed"]))


@app.command()
def media(ctx: typer.Context, photo_id: str, o: Annotated[Path, typer.Option("-o")] = Path("photo.jpg")) -> None:
    """Save one processed image (GET /media/{id}.jpg)."""
    r = _remote(ctx)
    try:
        data = r.get_media_bytes(photo_id) if r else _svc(ctx).get_media(photo_id).path.read_bytes()
    except NotFound:
        raise typer.BadParameter(f"{photo_id} is not ready")
    except RemoteError as e:
        raise typer.BadParameter(str(e))
    o.write_bytes(data)
    typer.echo(f"wrote {o} ({len(data) // 1024} KB)")


@app.command()
def login(ctx: typer.Context, passcode: str) -> None:
    """Check a passcode (POST /api/login)."""
    r = _remote(ctx)
    ok = (r.check_passcode if r else _svc(ctx).check_passcode)(LoginRequest(passcode=passcode))
    typer.echo("OK" if ok else "wrong passcode")
    raise typer.Exit(0 if ok else 1)


@app.command()
def sync(ctx: typer.Context) -> None:
    """Run one sync pass now."""
    _local_only(ctx, "sync")
    res = asyncio.run(_svc(ctx).sync_once())
    out(ctx, res, f"{res.new} new, {res.removed} removed, {res.total} in album{'' if res.complete else ' (listing incomplete)'}")


@app.command()
def process(ctx: typer.Context, limit: Annotated[Optional[int], typer.Option()] = None) -> None:
    """Process pending photos (faces + effects)."""
    _local_only(ctx, "process")
    res = asyncio.run(_svc(ctx, detector=True).process_pending(limit))
    out(ctx, res, f"{res.processed} processed, {res.failed} failed, effects: {json.dumps(res.effects)}")


@app.command()
def reroll(ctx: typer.Context, id: Annotated[Optional[str], typer.Option("--id")] = None) -> None:
    """Re-pick effects for one photo (or all) and re-process."""
    _local_only(ctx, "reroll")
    try:
        res = asyncio.run(_svc(ctx, detector=True).reroll(id))
    except NotFound:
        raise typer.BadParameter(f"no photo {id}")
    out(ctx, res, f"{res.processed} re-processed, effects: {json.dumps(res.effects)}")


@app.command()
def status(ctx: typer.Context) -> None:
    """Counts per status and last sync."""
    _local_only(ctx, "status")
    s = _svc(ctx).status()
    out(ctx, s, f"source={s.source} counts={s.counts} last_sync={s.last_sync} error={s.last_sync_error}")


@app.command()
def wipe(ctx: typer.Context, yes: Annotated[bool, typer.Option("--yes")] = False) -> None:
    """Delete all photos and state (after the event)."""
    _local_only(ctx, "wipe")
    if not yes:
        typer.confirm("Delete every downloaded and processed photo?", abort=True)
    _svc(ctx).wipe()
    typer.echo("wiped")


@app.command()
def serve(ctx: typer.Context, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the API, the frontend and the background sync + processing.

    Loopback by default: behind Tailscale Serve nothing else should reach the port. `--host 0.0.0.0` only on a trusted LAN."""
    import uvicorn

    from wall.app import create_app
    from wall.config import AuthSettings

    if weak_passcode(AuthSettings().passcode):  # checked before build_deps loads the face model
        typer.secho("Set PASSCODE (8+ characters, not the example) and SESSION_SECRET in .env; see .env.example.",
                    fg="red", err=True)
        raise typer.Exit(1)
    deps = build_deps(ctx.obj)
    if not deps.session_secret:
        typer.secho("SESSION_SECRET is unset: sessions end when the server restarts.", fg="yellow", err=True)
    elif weak_session_secret(deps.session_secret):  # cookies are checked without a rate limit, so a short key can be guessed
        typer.secho("SESSION_SECRET must be 32+ characters (see .env.example).", fg="red", err=True)
        raise typer.Exit(1)
    # proxy headers are trusted from 127.0.0.1 only (the Tailscale proxy), so request.client is the real guest IP
    uvicorn.run(create_app(deps, background=True), host=host, port=port, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1", server_header=False)


@app.command("openapi")
def openapi(o: Annotated[Path, typer.Option("-o")] = Path("../frontend/openapi.json")) -> None:
    """Write the OpenAPI schema (input for the frontend's generated types)."""
    from wall.app import create_app
    from wall.config import AppConfig, EventConfig
    from wall.faces import NoFaces

    cfg = AppConfig(event=EventConfig(qr_url="https://example.com", album_url="https://example.com"))
    deps = Deps(source=None, store=PhotoStore(":memory:"), face_detector=NoFaces(), config=cfg)
    o.write_text(json.dumps(create_app(deps, frontend=None).openapi(), indent=2))
    typer.echo(f"wrote {o}")
