import json

import pytest

from wall.sources.base import SourceItem
from wall.sources.sharelink import ShareLinkFormatError, ShareLinkSource, parse_album


def page(items: list, token: str = "", total: int | None = None) -> str:
    meta = ["albumId", "Party"] + [None] * 19 + [len(items) if total is None else total]
    data = [None, items, token, meta, None, 0]
    return f"<script>AF_initDataCallback({{key: 'ds:1', hash: '2', data:{json.dumps(data)}, sideChannel: {{}}}});</script>"


def photo(id: str, added_ms: int = 1_793_996_097_704, extra: dict | None = None) -> list:
    return [id, [f"https://lh3/{id}", 1600, 1200, None, None, None, None, None, [None, None, 1], [5000]],
            1_793_816_224_206, "x", 7_200_000, added_ms, ["owner"], [], 2, extra or {"15": 1}]


def test_parses_photo_fields():
    listing = parse_album(page([photo("p1")]))

    it = listing.items[0]
    assert (it.id, it.url, it.width, it.height) == ("p1", "https://lh3/p1", 1600, 1200)
    assert it.created.isoformat() == "2026-11-06T20:14:57.704000+00:00"
    assert listing.complete


def test_skips_videos():
    video = photo("v1", extra={"76647426": [50881, None, 1080, 1920]})

    listing = parse_album(page([photo("p1"), video]))

    assert [i.id for i in listing.items] == ["p1"]
    assert listing.complete  # the video still counts towards the album total


def test_next_page_token_marks_listing_incomplete():
    assert not parse_album(page([photo("p1")], token="more")).complete


def test_count_mismatch_marks_listing_incomplete():
    assert not parse_album(page([photo("p1")], total=300)).complete


def test_malformed_item_raises():
    with pytest.raises(ShareLinkFormatError):
        parse_album(page([["p1"]]))


def test_missing_data_block_raises():
    with pytest.raises(ShareLinkFormatError):
        parse_album("<html>sign in</html>")


@pytest.mark.parametrize("url", ["http://lh3.googleusercontent.com/x", "https://169.254.169.254/x", "https://googleusercontent.com.evil/x"])
async def test_download_refuses_urls_off_googles_image_host(url):
    src = ShareLinkSource("https://photos.app.goo.gl/x", http=None)
    item = SourceItem(id="p1", created="2026-11-06T00:00:00Z", width=1, height=1, url=url)

    with pytest.raises(ShareLinkFormatError):
        await src.download(item, 1600)
