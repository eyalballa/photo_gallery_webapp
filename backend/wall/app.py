import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from wall.api import router
from wall.deps import Deps
from wall.service import WallService
from wall.sync import run_periodically

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(deps: Deps, background: bool = False, frontend: Path | None = FRONTEND) -> FastAPI:
    """App factory. `background=True` starts the sync + processing loop (off in tests)."""
    svc = WallService(deps)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if background:
            async def tick():
                try:
                    await svc.sync_once()
                finally:  # photos already downloaded still get processed when the album fetch fails
                    await svc.process_pending()

            task = asyncio.create_task(run_periodically(deps.config.sync.every_s, tick, "sync"))
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # no /docs, /redoc or /openapi.json on the public URL (`wall openapi` still exports the schema)
    app = FastAPI(title="Birthday Photo Wall", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.state.service = svc
    app.include_router(router)

    if frontend and frontend.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith(("api/", "media/")):
                raise HTTPException(404)
            file = (frontend / path).resolve()
            inside = file.is_relative_to(frontend.resolve())
            return FileResponse(file if path and inside and file.is_file() else frontend / "index.html")

    return app
