"""Wiring only: routes and commands return what the service returns. Behaviour is tested in test_service."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wall import cli
from wall.app import create_app
from wall.service import WallService


@pytest.fixture
def anon(deps):
    return TestClient(create_app(deps, frontend=None), base_url="https://testserver")  # https: the cookie is Secure


@pytest.fixture
def client(anon):
    assert anon.post("/api/login", json={"passcode": "cake"}).status_code == 204
    return anon


async def test_photos_route_returns_service_result(client, deps, clock):
    svc = WallService(deps)
    await svc.sync_once()
    clock.tick()
    await svc.process_pending()

    body = client.get("/api/photos").json()

    assert [p["id"] for p in body["photos"]] == ["a", "b"]
    assert client.get(body["photos"][0]["url"]).headers["content-type"] == "image/jpeg"


def test_public_route_needs_no_session_and_shows_only_the_login_title(anon):
    assert anon.get("/api/public").json() == {"login_title": "Photo wall"}


def test_config_route(client):
    assert client.get("/api/config").json()["title"] == "John is 8!"


def test_effects_routes(client):
    res = client.put("/api/effects", json={"off": ["pop_art"], "honoree": "John"})

    assert res.status_code == 200
    assert [e["id"] for e in res.json()["effects"] if not e["on"]] == ["pop_art"]
    assert client.get("/api/effects").json()["honoree"] == "John"
    assert client.put("/api/effects", json={"off": ["nope"]}).status_code == 422
    assert client.post("/api/effects/reroll").json() == {"queued": 0}


async def test_repick_route_processes_right_away(client, deps, clock):
    svc = WallService(deps)
    await svc.sync_once()
    await svc.process_pending()
    clock.tick()

    assert client.post("/api/effects/reroll").json() == {"queued": 2}

    # TestClient runs background tasks before returning: both photos are ready again, at version 2
    assert [p["version"] for p in client.get("/api/photos").json()["photos"]] == [2, 2]


def test_effects_changes_need_a_session(anon):
    assert anon.put("/api/effects", json={"off": []}).status_code == 401
    assert anon.post("/api/effects/reroll").status_code == 401


def test_unknown_media_is_404(client):
    assert client.get("/media/nope.jpg").status_code == 404


def test_login_sets_an_httponly_secure_session_cookie(anon):
    res = anon.post("/api/login", json={"passcode": "cake"})

    cookie = res.headers["set-cookie"]
    assert res.status_code == 204
    assert cookie.startswith("wall_session=")
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie and "Max-Age=2592000" in cookie


def test_wrong_passcode_is_401_then_429(anon):
    codes = [anon.post("/api/login", json={"passcode": "pie"}).status_code for _ in range(6)]

    assert codes == [401] * 5 + [429]


@pytest.mark.parametrize("path", ["/api/config", "/api/photos", "/api/effects", "/media/a.jpg"])
def test_data_routes_need_a_session(anon, path):
    assert anon.get(path).status_code == 401
    anon.cookies.set("wall_session", "9999999999.forged")
    assert anon.get(path).status_code == 401


def test_security_headers_and_no_public_api_docs(anon):
    res = anon.get("/docs")

    assert res.status_code == 404
    assert anon.get("/openapi.json").status_code == 404
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"


def test_cli_status_prints_service_model(deps, monkeypatch):
    monkeypatch.setattr(cli, "build_deps", lambda c, detector=True: deps)

    result = CliRunner().invoke(cli.app, ["--json", "status"])

    assert result.exit_code == 0
    assert '"source": "list"' in result.output


def test_cli_sync_runs_service(deps, monkeypatch):
    monkeypatch.setattr(cli, "build_deps", lambda c, detector=True: deps)

    result = CliRunner().invoke(cli.app, ["sync"])

    assert result.output.strip() == "2 new, 0 removed, 2 in album"
