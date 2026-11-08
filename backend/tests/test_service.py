from datetime import timedelta, timezone

import pytest

from wall.schemas import LoginRequest
from wall.service import NotFound, RateLimited, WallService


@pytest.fixture
def svc(deps):
    return WallService(deps)


async def ready(svc, clock):
    await svc.sync_once()
    clock.tick(10)
    await svc.process_pending()


async def test_photos_lists_ready_with_versioned_urls(svc, clock):
    await ready(svc, clock)

    res = svc.list_photos(None)

    assert [(p.id, p.url, p.w, p.h) for p in res.photos] == [("a", "/media/a.jpg?v=1", 40, 30), ("b", "/media/b.jpg?v=1", 40, 30)]
    assert res.server_time == clock.now


async def test_since_returns_only_newer_and_removed_ids(svc, deps, clock):
    await ready(svc, clock)
    since = clock.tick(5)
    deps.source.items = deps.source.items[1:]  # "a" deleted from the album
    clock.tick(5)
    await svc.sync_once()

    res = svc.list_photos(since)

    assert (res.photos, res.removed) == ([], ["a"])


async def test_since_in_another_timezone_is_the_same_instant(svc, clock):
    await ready(svc, clock)
    since = clock.tick(5).astimezone(timezone(timedelta(hours=-5)))

    assert svc.list_photos(since).photos == []


async def test_reroll_bumps_version_and_resurfaces_photo(svc, clock):
    await ready(svc, clock)
    since = clock.tick(5)
    clock.tick(5)

    await svc.reroll("b")

    assert [(p.id, p.version) for p in svc.list_photos(since).photos] == [("b", 2)]


async def test_media_for_unknown_or_pending_photo_is_not_found(svc):
    await svc.sync_once()  # pending, not processed yet
    with pytest.raises(NotFound):
        svc.get_media("a")
    with pytest.raises(NotFound):
        svc.get_media("nope")


async def test_status_reports_counts_and_last_sync(svc, clock):
    await svc.sync_once()

    s = svc.status()

    assert (s.counts, s.last_sync, s.last_sync_error, s.source) == ({"pending": 2}, clock.now, None, "list")


async def test_sync_error_is_recorded_in_status(svc, deps):
    async def broken():
        raise RuntimeError("album gone")

    deps.source.list_items = broken
    with pytest.raises(RuntimeError):
        await svc.sync_once()

    assert svc.status().last_sync_error == "RuntimeError: album gone"


def test_passcode_check(svc):
    assert svc.check_passcode(LoginRequest(passcode="cake"))
    assert not svc.check_passcode(LoginRequest(passcode="pie"))


def test_login_issues_a_valid_session_only_for_the_right_passcode(svc):
    token = svc.login(LoginRequest(passcode="cake"), "1.2.3.4")

    assert svc.session_valid(token)
    assert svc.login(LoginRequest(passcode="pie"), "1.2.3.4") is None


def test_sixth_login_attempt_in_a_minute_is_rate_limited(svc, clock):
    for _ in range(5):
        svc.login(LoginRequest(passcode="pie"), "1.2.3.4")

    with pytest.raises(RateLimited):
        svc.login(LoginRequest(passcode="cake"), "1.2.3.4")
    clock.tick(60)
    assert svc.login(LoginRequest(passcode="cake"), "1.2.3.4")


def test_logins_from_many_ips_are_capped_at_30_a_minute(svc):
    for i in range(30):
        svc.login(LoginRequest(passcode="pie"), f"10.0.0.{i}")

    with pytest.raises(RateLimited):
        svc.login(LoginRequest(passcode="cake"), "10.0.1.1")


def test_changing_the_passcode_ends_existing_sessions(deps):
    token = WallService(deps).login(LoginRequest(passcode="cake"), "1.2.3.4")
    deps.passcode = "new-cake"

    assert not WallService(deps).session_valid(token)


def test_without_a_passcode_configured_nobody_gets_in(svc, deps):
    deps.passcode = None

    assert svc.login(LoginRequest(passcode=""), "1.2.3.4") is None


async def test_wipe_clears_store_and_files(svc, deps, clock):
    await ready(svc, clock)

    svc.wipe()

    assert deps.store.counts() == {}
    assert not deps.originals.exists() and not deps.processed.exists()
