"""Notifications (U5): alert events, push subscriptions, the one-alert claim and Web Push sends.

Rules (``construction/u5-notifications/functional-design/rules.md``, with the
build decisions of the code-generation plan):

- BR1.1 events: seat B joining alerts seat A (key ``joined``); a move alerts the
  mover's opponent (``move:<game>:<ply>``); a game end alerts the seat that did
  not cause it (``ended:<game>``). A move that ends the game gives only the
  ``ended`` alert. The notification tag is ``<code>:<key>`` on server and client.
  P2 U3 (BR2.5): a join request to a pass-along room alerts seat A
  (``join-request:<requestId>``, "Someone wants to join"), under the same
  one-alert claim.
- BR1.2 claim: ``INSERT OR IGNORE`` into ``alert_records`` before anything is
  sent; a key already claimed is never sent again. A claim left ``claimed`` by a
  crash is never resent, by design, and goes with its room.
- BR1.3 presence: push is skipped (``skipped``) only when the target seat has a
  socket that reports a visible page and was heard from in the last 6 s. The
  caller reads that presence in the request handler and passes it in; this
  module never reads hub state.
- BR1.4 results: any 2xx marks ``sent``; 404/410, and a 400/403 that names a
  VAPID or key mismatch, delete that subscription; zero subscriptions (or push
  disabled) marks ``skipped``; otherwise ``failed``. No retries.
- BR2.1 subscriptions: https on port 443, no user info, no IP literal, not
  localhost, and the host must match the push-service allowlist (plus
  ``JUSTCHESS_PUSH_HOSTS``, comma-separated, ``*.`` wildcards allowed). Keys
  are base64url: p256dh a 65-byte P-256 point, auth 16 bytes. Upsert on
  (room, slot, endpoint), keep the 5 newest per seat.
- BR2.4 cleanup: ``delete_room_data`` is the housekeeping hook; redeeming a
  continue link calls ``delete_seat_subscriptions`` in the same transaction.

Sends go through pywebpush with a ``requests.Session`` that never follows
redirects (``max_redirects = 0`` and ``allow_redirects=False``), TTL 3600 and a
10 s timeout, one subscription after another, in a worker thread. Endpoints and
keys are never logged: log lines carry the room code, seat, event key and the
endpoint's host only.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import logging
import re
import sqlite3
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from justchess import DomainError, games, rooms
from justchess.db import Database
from justchess.vapid import VapidConfig

logger = logging.getLogger("justchess.notifications")

MAX_PER_SEAT = 5
TTL_SECONDS = 3600
SEND_TIMEOUT = 10.0
ENDPOINT_MAX = 1024
P256DH_MAX = 200
AUTH_MAX = 64
P256DH_BYTES = 65
AUTH_BYTES = 16
TITLE_MAX = 60
BODY_MAX = 140

PUSH_HOSTS_ENV = "JUSTCHESS_PUSH_HOSTS"
DEFAULT_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "*.push.services.mozilla.com",
    "*.notify.windows.com",
    "web.push.apple.com",
    "*.push.apple.com",
)
HOST_PATTERN = re.compile(r"^(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)+$")
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
KEY_MISMATCH = re.compile(r"vapid|mismatch|does not correspond|badjwttoken|invalid.{0,20}key|public key", re.IGNORECASE)

INVALID_SUBSCRIPTION = "Invalid push subscription"

CLAIMED, SENT, SKIPPED, FAILED = "claimed", "sent", "skipped", "failed"
DUPLICATE = "duplicate"

TITLE_JOINED = "Your opponent has joined"
TITLE_JOIN_REQUEST = "Someone wants to join"
TITLE_MOVE = "Your move"
TITLE_ENDED = "Game over"
# Same wording as the client's view-model END_TITLES (static/js/view-model.js).
END_TITLES = {
    "checkmate": "Checkmate",
    "stalemate": "Stalemate",
    "insufficient_material": "Draw — not enough pieces to mate",
    "fivefold_repetition": "Draw by fivefold repetition",
    "seventyfive_moves": "Draw by the 75-move rule",
    "threefold_claimed": "Draw claimed (threefold repetition)",
    "fifty_moves_claimed": "Draw claimed (50-move rule)",
    "abandoned": "Opponent left",
}


# --- events (BR1.1) ---------------------------------------------------------

def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass(frozen=True)
class AlertEvent:
    """Something that happened, handed from HttpApi to Notifications after the commit."""

    kind: str  # joined | move | ended | join_request
    room_code: str
    target_slot: str
    event_key: str
    title: str
    body: str

    @property
    def url(self) -> str:
        """The room page the notification opens."""
        return f"/r/{self.room_code}"

    @property
    def tag(self) -> str:
        """The notification tag, ``<code>:<key>``, shared with the page and the service worker."""
        return f"{self.room_code}:{self.event_key}"

    def payload(self) -> str:
        """The JSON the service worker receives."""
        return json.dumps({"title": self.title, "body": self.body, "tag": self.tag, "url": self.url,
                           "code": self.room_code, "key": self.event_key}, ensure_ascii=False)


def _event(kind: str, code: str, target: str, key: str, title: str, body: str) -> AlertEvent:
    return AlertEvent(kind, code, target, key, _clip(title, TITLE_MAX), _clip(body, BODY_MAX))


def end_text(end_reason: str | None) -> str:
    """``Game over — <reason>``, worded as the client's overlay title."""
    return f"Game over — {END_TITLES.get(end_reason or '', 'Game over')}"


def joined_event(code: str) -> AlertEvent:
    """Seat B took its seat: seat A (White in game 1) is told."""
    return _event("joined", code, "A", "joined", TITLE_JOINED, "The game has started. You play White: your move.")


def join_request_event(code: str, request_id: int) -> AlertEvent:
    """P2 U3 BR2.5: a visitor asked to join a pass-along room; seat A (the creator) is told, once per request."""
    return _event("join_request", code, "A", f"join-request:{request_id}", TITLE_JOIN_REQUEST,
                  "Open the game to accept or decline. The request expires in 10 minutes.")


def ended_event(code: str, target_slot: str, game: games.Game) -> AlertEvent:
    """The game ended: the seat that did not cause it is told the reason."""
    return _event("ended", code, target_slot, f"ended:{game.number}", TITLE_ENDED, end_text(game.end_reason))


def event_after_move(code: str, mover_slot: str, game: games.Game, ply: int, san: str) -> AlertEvent:
    """The alert for an accepted move; a move that ends the game gives only the ``ended`` alert."""
    target = rooms.other_slot(mover_slot)
    if game.status == games.FINISHED:
        return ended_event(code, target, game)
    return _event("move", code, target, f"move:{game.number}:{ply}", TITLE_MOVE, f"Your opponent played {san}.")


def event_after_claim(code: str, claimant_slot: str, game: games.Game) -> AlertEvent:
    """A draw or win claim ended the game: the other seat is told."""
    return ended_event(code, rooms.other_slot(claimant_slot), game)


# --- presence (BR1.3) -------------------------------------------------------

@dataclass(frozen=True)
class Presence:
    """The target seat as the request handler saw it: connected, and visible with a fresh socket."""

    connected: bool
    fresh_visible: bool

    @property
    def page_covers_it(self) -> bool:
        """True when an open, visible, recently heard page shows its own banner."""
        return self.connected and self.fresh_visible


# --- subscriptions (BR2.1, BR2.2, BR2.4) ------------------------------------

@dataclass(frozen=True)
class Subscription:
    """One stored push endpoint of one seat."""

    id: int
    room_code: str
    slot: str
    endpoint: str
    p256dh: str
    auth: str
    created_at: float

    def info(self) -> dict:
        """The ``subscription_info`` pywebpush expects."""
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}


def allowed_hosts(env: Mapping[str, str]) -> tuple[str, ...]:
    """The default push-service hosts plus valid entries of ``JUSTCHESS_PUSH_HOSTS``."""
    extra = []
    for entry in (env.get(PUSH_HOSTS_ENV) or "").split(","):
        host = entry.strip().lower()
        if not host:
            continue
        if HOST_PATTERN.fullmatch(host):
            extra.append(host)
        else:
            logger.warning("Ignoring %r in %s: not a host name or *.domain pattern", host, PUSH_HOSTS_ENV)
    return DEFAULT_PUSH_HOSTS + tuple(extra)


STRICT_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]")


def host_allowed(host: str, patterns: Iterable[str]) -> bool:
    """Exact host match, or a ``*.domain`` pattern matching a subdomain."""
    for pattern in patterns:
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix) and len(host) > len(suffix):
                return True
        elif host == pattern:
            return True
    return False


def endpoint_host(endpoint: str) -> str:
    """The host of an endpoint, the only part of it ever logged."""
    try:
        return urlsplit(endpoint).hostname or "(no host)"
    except ValueError:
        return "(invalid)"


def _invalid() -> DomainError:
    return DomainError(400, INVALID_SUBSCRIPTION)


def validate_endpoint(endpoint: object, hosts: Iterable[str]) -> str:
    """Return the endpoint when it is a public https push-service URL, else raise 400."""
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= ENDPOINT_MAX:
        raise _invalid()
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in endpoint):
        raise _invalid()
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        raise _invalid() from None
    if parts.scheme != "https" or "@" in parts.netloc or port not in (None, 443):
        raise _invalid()
    # Only plain ASCII host names: letters, digits and hyphens in dot-separated labels.
    # This refuses backslashes, percent-escapes and any other character that a
    # different URL parser (such as the one requests uses) could read as a host
    # boundary, so the host checked here is the host that would be contacted.
    host = parts.hostname or ""
    netloc_host = parts.netloc.lower().rsplit(":443", 1)[0] if parts.netloc.lower().endswith(":443") else parts.netloc.lower()
    if not STRICT_HOST.fullmatch(host) or netloc_host != host:
        raise _invalid()
    try:
        ipaddress.ip_address(host)
        raise _invalid()
    except ValueError:
        pass
    if "." not in host or host == "localhost" or host.endswith((".localhost", ".local")):
        raise _invalid()
    if not host_allowed(host, hosts):
        raise _invalid()
    return endpoint


def _decode_key(value: object, limit: int) -> bytes:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not BASE64URL.fullmatch(value):
        raise _invalid()
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise _invalid() from None


def validate_keys(p256dh: object, auth: object) -> tuple[str, str]:
    """Return the keys when p256dh is a 65-byte P-256 point and auth 16 bytes (base64url), else 400."""
    point = _decode_key(p256dh, P256DH_MAX)
    secret = _decode_key(auth, AUTH_MAX)
    if len(point) != P256DH_BYTES or len(secret) != AUTH_BYTES:
        raise _invalid()
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except ValueError:
        raise _invalid() from None
    return str(p256dh), str(auth)


def validate_subscription(endpoint: object, keys: object, hosts: Iterable[str]) -> tuple[str, str, str]:
    """Validate a browser subscription; return (endpoint, p256dh, auth) or raise 400."""
    if not isinstance(keys, Mapping):
        raise _invalid()
    p256dh, auth = validate_keys(keys.get("p256dh"), keys.get("auth"))
    return validate_endpoint(endpoint, hosts), p256dh, auth


def save_subscription(conn: sqlite3.Connection, code: str, slot: str, endpoint: str, p256dh: str, auth: str,
                      now: float) -> None:
    """Upsert on (room, slot, endpoint), then keep only the seat's 5 newest endpoints."""
    conn.execute(
        "INSERT INTO push_subscriptions (room_code, slot, endpoint, p256dh, auth, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (room_code, slot, endpoint) "
        "DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, created_at = excluded.created_at",
        (code, slot, endpoint, p256dh, auth, now),
    )
    conn.execute(
        "DELETE FROM push_subscriptions WHERE room_code = ? AND slot = ? AND id NOT IN ("
        "SELECT id FROM push_subscriptions WHERE room_code = ? AND slot = ? "
        "ORDER BY created_at DESC, id DESC LIMIT ?)",
        (code, slot, code, slot, MAX_PER_SEAT),
    )


def list_subscriptions(conn: sqlite3.Connection, code: str, slot: str) -> list[Subscription]:
    """The seat's subscriptions, newest first."""
    rows = conn.execute(
        "SELECT * FROM push_subscriptions WHERE room_code = ? AND slot = ? ORDER BY created_at DESC, id DESC",
        (code, slot),
    ).fetchall()
    return [Subscription(r["id"], r["room_code"], r["slot"], r["endpoint"], r["p256dh"], r["auth"], r["created_at"])
            for r in rows]


def delete_subscription(conn: sqlite3.Connection, code: str, slot: str, endpoint: str) -> int:
    """Delete the seat's subscription for one endpoint; return how many rows went (0 or 1)."""
    cur = conn.execute("DELETE FROM push_subscriptions WHERE room_code = ? AND slot = ? AND endpoint = ?",
                       (code, slot, endpoint))
    return cur.rowcount


def delete_seat_subscriptions(conn: sqlite3.Connection, code: str, slot: str) -> int:
    """Delete every subscription of a seat (the seat moved to another device)."""
    return conn.execute("DELETE FROM push_subscriptions WHERE room_code = ? AND slot = ?", (code, slot)).rowcount


def delete_room_data(conn: sqlite3.Connection, code: str) -> None:
    """Housekeeping hook (BR2.4): remove the room's subscriptions and alert records."""
    conn.execute("DELETE FROM push_subscriptions WHERE room_code = ?", (code,))
    conn.execute("DELETE FROM alert_records WHERE room_code = ?", (code,))


# --- claims (BR1.2) ---------------------------------------------------------

def claim(conn: sqlite3.Connection, event: AlertEvent, now: float) -> bool:
    """Claim the event's key for its seat; False when it was claimed before."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO alert_records (room_code, slot, event_key, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event.room_code, event.target_slot, event.event_key, CLAIMED, now, now),
    )
    return cur.rowcount == 1


def mark(conn: sqlite3.Connection, event: AlertEvent, status: str, now: float) -> None:
    """Record the outcome of a claim."""
    conn.execute(
        "UPDATE alert_records SET status = ?, updated_at = ? WHERE room_code = ? AND slot = ? AND event_key = ?",
        (status, now, event.room_code, event.target_slot, event.event_key),
    )


def alert_status(conn: sqlite3.Connection, code: str, slot: str, key: str) -> str | None:
    """The stored status of one claim, or None."""
    row = conn.execute("SELECT status FROM alert_records WHERE room_code = ? AND slot = ? AND event_key = ?",
                       (code, slot, key)).fetchone()
    return row["status"] if row else None


# --- sending (BR1.4) --------------------------------------------------------

@dataclass(frozen=True)
class PushResult:
    """What the push service answered: an HTTP status (0 when no answer arrived) and its body text."""

    status: int
    text: str = ""


class Sender(Protocol):
    """Sends one encrypted push; never raises for transport or HTTP failures."""

    def __call__(self, subscription_info: dict, payload: str, vapid: VapidConfig) -> PushResult: ...


class NoRedirectSession(requests.Session):
    """A requests session that never follows a redirect (the push endpoint is user-supplied)."""

    def __init__(self) -> None:
        super().__init__()
        self.max_redirects = 0

    def request(self, method, url, *args, **kwargs):  # noqa: D102 - same contract as requests.Session
        kwargs["allow_redirects"] = False
        return super().request(method, url, *args, **kwargs)


class WebPushSender:
    """The production sender: pywebpush over a fresh no-redirect session per send."""

    def __init__(self, session_factory: Callable[[], requests.Session] = NoRedirectSession,
                 timeout: float = SEND_TIMEOUT, ttl: int = TTL_SECONDS) -> None:
        self.session_factory = session_factory
        self.timeout = timeout
        self.ttl = ttl

    def __call__(self, subscription_info: dict, payload: str, vapid: VapidConfig) -> PushResult:
        session = self.session_factory()
        try:
            response = webpush(subscription_info, data=payload, vapid_private_key=vapid.signer(),
                               vapid_claims={"sub": vapid.subject}, ttl=self.ttl, timeout=self.timeout,
                               headers={"Urgency": "high"}, requests_session=session)
            return PushResult(response.status_code)
        except WebPushException as exc:
            response = exc.response
            if response is not None:
                return PushResult(int(response.status_code), (response.text or "")[:500])
            return PushResult(0, "WebPushException")
        except requests.RequestException as exc:
            return PushResult(0, type(exc).__name__)
        except (ValueError, TypeError) as exc:  # keys that cannot be used for encryption
            return PushResult(0, type(exc).__name__)
        finally:
            session.close()


def is_gone(result: PushResult) -> bool:
    """True when the subscription must be deleted: 404/410, or a VAPID or key mismatch."""
    if result.status in (404, 410):
        return True
    return result.status in (400, 403) and bool(KEY_MISMATCH.search(result.text))


class Notifier:
    """Claims each alert once and sends Web Push to the target seat's endpoints."""

    def __init__(self, db: Database, vapid: VapidConfig, *, sender: Sender | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.db = db
        self.vapid = vapid
        self.sender: Sender = sender if sender is not None else WebPushSender()
        self.clock = clock

    def dispatch(self, event: AlertEvent, presence: Presence) -> str:
        """Run W2 for one event; return ``duplicate``, ``skipped``, ``sent`` or ``failed``."""
        with self.db.transaction() as conn:
            if not claim(conn, event, self.clock()):
                logger.debug("Alert %s for room %s seat %s was claimed before", event.event_key,
                             event.room_code, event.target_slot)
                return DUPLICATE
        if presence.page_covers_it:
            return self._finish(event, SKIPPED, "a visible page shows it")
        if not self.vapid.enabled:
            return self._finish(event, SKIPPED, "push is disabled")
        with self.db.read() as conn:
            subscriptions = list_subscriptions(conn, event.room_code, event.target_slot)
        if not subscriptions:
            return self._finish(event, SKIPPED, "no_subscription")
        sent, gone = self._send_all(event, subscriptions)
        return self._finish(event, SENT if sent else FAILED, f"{sent} accepted, {len(gone)} removed", gone)

    def dispatch_safely(self, event: AlertEvent, presence: Presence) -> str | None:
        """``dispatch`` that logs any failure (room code only) instead of raising."""
        try:
            return self.dispatch(event, presence)
        except Exception:
            logger.exception("Alert %s for room %s could not be dispatched", event.event_key, event.room_code)
            return None

    def _send_all(self, event: AlertEvent, subscriptions: list[Subscription]) -> tuple[int, list[int]]:
        payload, sent, gone = event.payload(), 0, []
        for subscription in subscriptions:
            host = endpoint_host(subscription.endpoint)
            result = self.sender(subscription.info(), payload, self.vapid)
            if 200 <= result.status < 300:
                sent += 1
            elif is_gone(result):
                gone.append(subscription.id)
                logger.info("Push endpoint at %s for room %s seat %s is gone (%s); removing it",
                            host, event.room_code, event.target_slot, result.status)
            else:
                logger.warning("Push to %s for room %s seat %s failed (status %s)",
                               host, event.room_code, event.target_slot, result.status or "no answer")
        return sent, gone

    def _finish(self, event: AlertEvent, status: str, why: str, gone: Iterable[int] = ()) -> str:
        with self.db.transaction() as conn:
            for subscription_id in gone:
                conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (subscription_id,))
            mark(conn, event, status, self.clock())
        logger.info("Alert %s for room %s seat %s: %s (%s)", event.event_key, event.room_code,
                    event.target_slot, status, why)
        return status
