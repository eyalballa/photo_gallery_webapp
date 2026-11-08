"""Session tokens and the login rate limit. Pure: time comes from an injected clock."""

import hashlib
import hmac
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta


class Sessions:
    """Stateless session tokens: `<expiry unix seconds>.<hex HMAC-SHA256 of the expiry>`."""

    def __init__(self, secret: str, clock: Callable[[], datetime], ttl: timedelta = timedelta(days=30)):
        self.key = secret.encode()
        self.clock = clock
        self.ttl = ttl

    @property
    def ttl_seconds(self) -> int:
        return int(self.ttl.total_seconds())

    def _sign(self, exp: str) -> str:
        return hmac.new(self.key, exp.encode(), hashlib.sha256).hexdigest()

    def issue(self) -> str:
        exp = str(int((self.clock() + self.ttl).timestamp()))
        return f"{exp}.{self._sign(exp)}"

    def valid(self, token: str | None) -> bool:
        exp, _, sig = (token or "").partition(".")
        # bytes, and ASCII digits only: compare_digest and int() raise on other unicode
        if not (exp.isascii() and exp.isdigit()) or not hmac.compare_digest(sig.encode(), self._sign(exp).encode()):
            return False
        return int(exp) > self.clock().timestamp()


class RateLimiter:
    """At most `limit` attempts per key in any sliding `window`."""

    def __init__(self, clock: Callable[[], datetime], limit: int = 5, window: timedelta = timedelta(minutes=1)):
        self.clock, self.limit, self.window = clock, limit, window
        self.hits: dict[str, deque[datetime]] = {}

    def allow(self, key: str) -> bool:
        now = self.clock()
        if len(self.hits) > 1000:  # forget idle keys, so rotating IPs can't grow this without bound
            self.hits = {k: q for k, q in self.hits.items() if q and q[-1] > now - self.window}
        q = self.hits.setdefault(key, deque())
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def weak_session_secret(secret: str) -> bool:
    """Session cookies are HMACs under this key; anything short is guessable by trying forged cookies."""
    return len(secret) < 32


def weak_passcode(passcode: str | None) -> bool:
    """The Funnel URL is public, so the passcode is the real gate: at least 8 characters, not the example."""
    return not passcode or len(passcode) < 8 or passcode == "change-me"
