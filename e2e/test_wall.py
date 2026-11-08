"""End to end: the real image serving over HTTP, with the real face model and the golden photos as its album.

Run through e2e/run.sh, which starts the app container and runs this file from the test image.
"""

import io
import os
import re
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

from wall.remote import RemoteWall

URL = os.environ["WALL_URL"]
PASSCODE = os.environ["WALL_PASSCODE"]
PHOTOS = len(list(Path("/photos").glob("*.jpg")))
PROCESS_TIMEOUT_S = 300


@pytest.fixture(scope="session")
def anon() -> httpx.Client:
    http = httpx.Client(base_url=URL, timeout=30)
    deadline = time.monotonic() + 120  # the server starts once the face model has loaded
    while True:
        try:
            http.get("/api/public").raise_for_status()
            return http
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


@pytest.fixture(scope="session")
def wall(anon) -> RemoteWall:
    return RemoteWall(URL, PASSCODE)


@pytest.fixture(scope="session")
def photos(wall):
    """Every golden photo, once synced and processed (polls like the wall does)."""
    deadline = time.monotonic() + PROCESS_TIMEOUT_S
    while len((res := wall.list_photos(None)).photos) < PHOTOS:
        assert time.monotonic() < deadline, f"{len(res.photos)}/{PHOTOS} photos ready after {PROCESS_TIMEOUT_S}s"
        time.sleep(3)
    return res


def test_frontend_is_served_with_security_headers(anon):
    page = anon.get("/")
    script = re.search(r'src="(/assets/[^"]+\.js)"', page.text)

    assert page.status_code == 200 and script
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert anon.get(script.group(1)).status_code == 200


def test_login_screen_shows_only_the_login_title(anon):
    assert anon.get("/api/public").json() == {"login_title": "E2E login"}


@pytest.mark.parametrize("path", ["/api/config", "/api/photos", "/media/anything.jpg"])
def test_data_needs_a_session(anon, path):
    assert anon.get(path).status_code == 401


def test_wrong_passcode_is_refused(anon):
    assert anon.post("/api/login", json={"passcode": "not-it"}).status_code == 401


def test_config_after_login(wall):
    assert wall.get_config().title == "E2E wall"


def test_every_photo_is_processed_and_served(wall, photos):
    for p in photos.photos:
        img = Image.open(io.BytesIO(wall.get_media_bytes(p.id)))
        assert img.format == "JPEG" and (img.width, img.height) == (p.w, p.h) and max(p.w, p.h) <= 1600


def test_polling_since_server_time_returns_nothing_new(wall, photos):
    later = wall.list_photos(photos.server_time)
    assert later.photos == [] and later.removed == []
