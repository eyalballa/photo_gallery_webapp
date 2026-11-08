from wall.auth import RateLimiter, Sessions, weak_passcode, weak_session_secret
from tests.conftest import Clock


def test_session_token_is_valid_until_it_expires():
    clock = Clock()
    s = Sessions("k", clock)
    token = s.issue()

    assert token.split(".")[0] == "1796666400"  # T0 + 30 days
    assert s.valid(token)
    clock.tick(30 * 86400)
    assert not s.valid(token)


def test_forged_or_foreign_tokens_are_rejected():
    clock = Clock()
    token = Sessions("k", clock).issue()
    exp, sig = token.split(".")

    assert not Sessions("other", clock).valid(token)
    assert not Sessions("k", clock).valid(f"9999999999.{sig}")
    assert not Sessions("k", clock).valid(None)
    assert not Sessions("k", clock).valid("garbage")
    assert not Sessions("k", clock).valid("١٢٣.é")  # non-ASCII digits and signature


def test_rate_limit_allows_five_per_minute_per_key():
    clock = Clock()
    limit = RateLimiter(clock)

    assert [limit.allow("1.2.3.4") for _ in range(6)] == [True] * 5 + [False]
    assert limit.allow("5.6.7.8")
    clock.tick(60)
    assert limit.allow("1.2.3.4")


def test_weak_passcodes():
    assert [weak_passcode(p) for p in (None, "", "cake", "change-me", "ron-is-8!")] == [True, True, True, True, False]


def test_session_secret_needs_32_characters():
    assert (weak_session_secret("x" * 31), weak_session_secret("x" * 32)) == (True, False)
