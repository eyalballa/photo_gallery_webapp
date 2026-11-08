import httpx

from wall.sync import describe, sync_once
from tests.conftest import ListSource, item


async def test_new_items_are_downloaded_and_pending(deps, tmp_path):
    report = await sync_once(deps.source, deps.store, deps.clock, tmp_path / "o")

    assert (report.new, report.removed, report.total) == (2, 0, 2)
    assert deps.store.counts() == {"pending": 2}
    assert sorted(p.name for p in (tmp_path / "o").iterdir()) == ["a.jpg", "b.jpg"]


async def test_items_gone_from_album_are_marked_removed(deps, tmp_path):
    await sync_once(deps.source, deps.store, deps.clock, tmp_path)
    deps.source.items = [item("b")]

    report = await sync_once(deps.source, deps.store, deps.clock, tmp_path)

    assert report.removed == 1
    assert deps.store.get("a").status == "removed"


async def test_incomplete_listing_never_removes(deps, tmp_path):
    await sync_once(deps.source, deps.store, deps.clock, tmp_path)
    deps.source.items, deps.source.complete = [item("b")], False

    report = await sync_once(deps.source, deps.store, deps.clock, tmp_path)

    assert report.removed == 0
    assert deps.store.get("a").status == "pending"


async def test_failed_download_is_retried_next_pass(deps, tmp_path):
    src = ListSource("a")
    src.fail = {"a"}
    assert (await sync_once(src, deps.store, deps.clock, tmp_path)).new == 0

    src.fail = set()
    assert (await sync_once(src, deps.store, deps.clock, tmp_path)).new == 1


async def test_re_added_photo_comes_back(deps, tmp_path):
    await sync_once(deps.source, deps.store, deps.clock, tmp_path)
    deps.source.items = [item("b")]
    await sync_once(deps.source, deps.store, deps.clock, tmp_path)
    deps.source.items = [item("a"), item("b")]

    await sync_once(deps.source, deps.store, deps.clock, tmp_path)

    assert deps.store.get("a").status == "pending"


async def test_items_with_unsafe_ids_are_skipped(deps, tmp_path):
    src = ListSource("ok-1", "../evil", "a.b")

    report = await sync_once(src, deps.store, deps.clock, tmp_path / "o")

    assert (report.new, report.total) == (1, 1)
    assert [p.name for p in (tmp_path / "o").iterdir()] == ["ok-1.jpg"]


def test_error_descriptions_leave_out_urls():
    req = httpx.Request("GET", "https://lh3.googleusercontent.com/pw/secret")
    err = httpx.HTTPStatusError("boom https://lh3.googleusercontent.com/pw/secret", request=req, response=httpx.Response(403))

    assert describe(err) == "HTTP 403"
    assert describe(httpx.ConnectError("to https://x/secret", request=req)) == "ConnectError"
