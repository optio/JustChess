"""Join-request rate limit and the client address behind it (P2 U3, BR3.1, NFR4).

``RateLimiter`` keeps, in memory, a sliding window of attempt times per client
address: at most ``limit`` (5) attempts in ``window`` (60) seconds. A refused
attempt is not recorded, so a visitor who waits is let in again as the window
slides. Windows left empty are dropped, and at most ``max_addresses`` (10,000)
addresses are tracked; the address used least recently is evicted first. A
restart forgets every window (accepted: FR3 edge cases).

``client_address(request, trusted)`` is the address the limit is keyed on:

- by default the ASGI client address the server reports
  (``request.client.host``). Uvicorn already rewrites it from
  ``X-Forwarded-For`` when the peer is in its own ``--forwarded-allow-ips``
  (127.0.0.1 by default), so JustChess parses no header itself;
- only when ``JUSTCHESS_TRUSTED_PROXIES`` lists that reported address does it
  read ``X-Forwarded-For``, taking the rightmost entry that is not itself a
  trusted proxy (entries further left can be written by the client).

``parse_trusted_proxies`` reads that setting: comma-separated IP addresses or
CIDR networks, default empty. An invalid entry is logged (its text only, it is
not a secret) and ignored.
"""

from __future__ import annotations

import ipaddress
import logging
import hashlib
from collections import OrderedDict, deque
from collections.abc import Iterable, Mapping
from typing import Protocol

logger = logging.getLogger("justchess.ratelimit")

TRUSTED_PROXIES_ENV = "JUSTCHESS_TRUSTED_PROXIES"
WINDOW_SECONDS = 60.0
MAX_ATTEMPTS = 5  # fallback; the app passes gameplay.yaml's rate_limits.join_request
MAX_ADDRESSES = 10_000
UNKNOWN_ADDRESS = "unknown"

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class RateLimiter:
    """A sliding-window limit per key, in memory, with bounded size."""

    def __init__(self, limit: int = MAX_ATTEMPTS, window: float = WINDOW_SECONDS,
                 max_addresses: int = MAX_ADDRESSES) -> None:
        if limit < 1 or window <= 0 or max_addresses < 1:
            raise ValueError("limit, window and max_addresses must be positive")
        self.limit = limit
        self.window = window
        self.max_addresses = max_addresses
        self._windows: OrderedDict[str, deque[float]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._windows)

    def _prune(self, key: str, now: float) -> deque[float] | None:
        times = self._windows.get(key)
        if times is None:
            return None
        while times and now - times[0] >= self.window:
            times.popleft()
        if not times:
            del self._windows[key]
            return None
        return times

    def allow(self, key: str, now: float) -> bool:
        """Record an attempt for ``key`` and return True, or return False when the window is full."""
        times = self._prune(key, now)
        if times is not None and len(times) >= self.limit:
            return False
        if times is None:
            times = deque()
            self._windows[key] = times
        times.append(now)
        self._windows.move_to_end(key)
        self._drop_stale(now)
        while len(self._windows) > self.max_addresses:
            self._windows.popitem(last=False)
        return True

    def _drop_stale(self, now: float) -> None:
        """Drop expired windows, starting with the least recently used."""
        while self._windows:
            times = next(iter(self._windows.values()))
            if now - times[-1] < self.window:
                return
            self._windows.popitem(last=False)


class SharedRateLimiter:
    """PostgreSQL fixed-window cap shared across instances; keys are hashed."""

    def __init__(self, db, name, limit, window=WINDOW_SECONDS):
        self.db, self.name, self.limit, self.window = db, name, limit, window

    def allow(self, key, now):
        digest = hashlib.sha256((self.name + ":" + key).encode()).hexdigest()
        with self.db.transaction() as conn:
            row = conn.execute(
                "INSERT INTO rate_windows(rate_key, started_at, attempts) VALUES (?, ?, 1) "
                "ON CONFLICT(rate_key) DO UPDATE SET "
                "started_at = CASE WHEN rate_windows.started_at <= ? THEN excluded.started_at ELSE rate_windows.started_at END, "
                "attempts = CASE WHEN rate_windows.started_at <= ? THEN 1 ELSE rate_windows.attempts + 1 END "
                "RETURNING attempts", (digest, now, now - self.window, now - self.window)).fetchone()
            return row[0] <= self.limit


def parse_trusted_proxies(raw: str | None) -> tuple[Network, ...]:
    """Parse ``JUSTCHESS_TRUSTED_PROXIES``: IPs or CIDRs, comma-separated; invalid entries are logged and skipped."""
    networks: list[Network] = []
    for entry in (raw or "").split(","):
        text = entry.strip()
        if not text:
            continue
        try:
            networks.append(ipaddress.ip_network(text, strict=False))
        except ValueError:
            logger.warning("Ignoring %r in %s: not an IP address or CIDR network", text, TRUSTED_PROXIES_ENV)
    return tuple(networks)


def trusted_proxies_from(env: Mapping[str, str]) -> tuple[Network, ...]:
    """The trusted proxies named in the environment (empty by default)."""
    return parse_trusted_proxies(env.get(TRUSTED_PROXIES_ENV))


def _ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(text.strip())
    except ValueError:
        return None


def is_trusted(address: str, trusted: Iterable[Network]) -> bool:
    """True when ``address`` is an IP inside one of the trusted networks."""
    ip = _ip(address)
    return ip is not None and any(ip in network for network in trusted)


class _Client(Protocol):
    host: str


class _Request(Protocol):
    @property
    def client(self) -> _Client | None: ...

    @property
    def headers(self) -> Mapping[str, str]: ...


def client_address(request: _Request, trusted: Iterable[Network] = ()) -> str:
    """The client address to rate-limit: the reported peer, or from a trusted proxy the rightmost untrusted hop."""
    trusted = tuple(trusted)
    peer = request.client.host if request.client and request.client.host else UNKNOWN_ADDRESS
    if not trusted or not is_trusted(peer, trusted):
        return peer
    forwarded = request.headers.get("x-forwarded-for") or ""
    for hop in reversed([part.strip() for part in forwarded.split(",") if part.strip()]):
        if _ip(hop) is None:
            break  # a malformed hop: stop at the last address we can vouch for
        if not is_trusted(hop, trusted):
            return hop
    return peer
