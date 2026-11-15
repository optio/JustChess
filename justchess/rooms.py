"""Rooms: codes, seats, tokens, presence, score and rematch requests.

Implements BR1.1-BR1.7 and BR3.1-BR3.3. Every function that writes takes an
open connection inside the caller's transaction, so the API layer can combine
Rooms and Games changes in one ``BEGIN IMMEDIATE`` transaction. Times are server
epoch seconds supplied by the caller (an injectable clock).

Tokens are only ever stored as SHA-256 hashes and compared in constant time.
Never log a token or pass one into an error message.

P2 U2 (BR1.2): a room carries a ``mode``. ``create_room`` inserts it as
``waiting`` and a join that takes seat B sets ``online`` in the same
transaction. ``computer_level`` is set only for computer rooms (U4), and the
computer's seat has no token hash, so no presented token can ever match it.

P2 U3 (pass-along and join requests, BR1.1, BR1.4, BR2.1-BR2.4):

- ``set_mode`` moves a room between ``waiting`` and ``pass_along`` for seat A
  only, while seat B does not exist and the room is not a computer room.
  Entering pass-along starts a game still in status waiting, uncounted;
  leaving it declines any pending join request in the same transaction.
- A join request stores only the SHA-256 of the visitor's request token. Every
  read of a pending request past ``expires_at`` marks it ``lapsed`` first
  (``lapse_if_expired``), and the read result says so, so the caller can
  broadcast after its commit. Functions that read requests never raise after
  writing: refusals come back as outcome values, so a lapse is never rolled
  back with a refusal.
- Accepting creates seat B with ``token_hash`` = the request's token hash, so
  the joiner's request token becomes its seat token and no plain token is ever
  stored. ``RequestAddressBook`` keeps, in memory, the client address behind
  each request and the addresses the creator declined in the last 10 minutes.

P2 U4 (computer rooms, BR3.1-BR3.3, BR3.6, ADR-002, ADR-005):

- ``create_computer_room(conn, now, level, white_slot)`` inserts a room in mode
  ``computer`` with its level, seat A with a fresh token and seat B as the
  computer (``is_computer = 1``, no token hash). The caller starts game 1
  (``games.create_computer_game``) in the same transaction.
- ``join_room`` refuses every token but seat A's in a computer room with 409
  "This room plays the computer"; seat A's own token still rejoins.
- ``seat_presence`` reports ``computer`` for the computer's seat.
- The room score of a computer room is the player (A) against the computer (B)
  at that level; ``record_result`` needs no change for it.

Computer stand-in (2026-11-15 follow-up): a friend room still waiting for its
second player can let the computer play seat B until a friend arrives.

- ``set_mode(..., "computer", level=...)`` (seat A, room waiting, no human seat
  B) turns the room into mode ``computer`` at that level, inserts the computer's
  seat B and marks the room in the additive ``room_stand_ins`` runtime table, so
  the core schema and its CHECKs are unchanged. A waiting game starts playing,
  uncounted; a game already under way keeps its position.
- ``set_mode(..., "waiting")`` on a stand-in room removes the computer's seat,
  clears the level and keeps the position, so a friend can still join it.
- ``join_room`` on a stand-in room hands the computer's seat B to the joiner:
  seat B gets the joiner's token hash, the room turns ``online``, the stand-in
  mark goes and the game version is bumped, so an engine reply still in flight
  is discarded. The caller counts the current game (``games.mark_counted``).
- Plain computer rooms (made from the lobby) still refuse every other token.

Switching sides (2026-11-15 follow-up, ``switch_side``): seat A may take the
other colour of the current game. Before a friend has joined (mode waiting or
pass-along) only while no move has been made; against the computer (stand-in
or lobby room) at any time while the game is playing, taking over the
computer's pieces in the current position. A computer game switched after its
first move stops counting toward the score. The version is bumped, so an
engine reply still in flight is discarded.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import string
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from justchess import DomainError, games  # games imports nothing from rooms

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 6
CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")
MAX_CODE_TRIES = 10
TOKEN_BYTES = 32  # 256 bits, above the 128-bit floor of BR1.4
ABANDON_AFTER = 24 * 3600.0  # fallback; the app passes gameplay.yaml's rooms.claim_win_away_hours
CONTINUE_TTL = 10 * 60.0
LAST_SEEN_THROTTLE = 60.0
SLOTS = ("A", "B")
MODE_WAITING, MODE_PASS_ALONG, MODE_ONLINE, MODE_COMPUTER = "waiting", "pass_along", "online", "computer"

INVALID_CODE = "Room code must be 6 letters or digits"
ROOM_NOT_FOUND = "Room not found"
ROOM_FULL = "This game already has two players"
NOT_YOUR_SEAT = "This isn't your seat"
CONTINUE_INVALID = "This continue link is no longer valid"
CREATE_FAILED = "Could not create a room, try again"
FINISH_FIRST = "Finish this game first"

# P2 U3: pass-along and join requests.
# Fallbacks; the app passes gameplay.yaml's join_requests values.
REQUEST_TTL = 10 * 60.0
DECLINE_MEMORY = 10 * 60.0
MAX_REMEMBERED_ADDRESSES = 10_000
SWITCHABLE_MODES = (MODE_WAITING, MODE_PASS_ALONG, MODE_COMPUTER)
WAIT_FIRST = "Switch back to waiting for a friend first"
STAND_IN_DEFAULT_LEVEL = "casual"
PENDING, ACCEPTED, DECLINED, LAPSED = "pending", "accepted", "declined", "lapsed"
CREATOR_ONLY = "Only the creator can do this"
ALREADY_JOINED = "A friend has already joined"
COMPUTER_ROOM = "This room plays the computer"
NO_PENDING = "No pending request"
BUSY = "Someone else is already asking to join. Try again in a few minutes."
DECLINED_RECENTLY = "The creator declined. You can ask again later."

# P2 U4: computer rooms.
COMPUTER_LEVELS = ("beginner", "casual", "club", "strong", "maximum")
UNKNOWN_LEVEL = "Unknown computer level"
UNKNOWN_SLOT = "Unknown colour"


@dataclass(frozen=True)
class Room:
    """A room row: code, activity times, per-slot score, any pending rematch request and the mode."""

    code: str
    created_at: float
    last_activity_at: float
    wins_a: int
    wins_b: int
    draws: int
    rematch_requested_by: str | None
    rematch_requested_at: float | None
    mode: str = MODE_WAITING
    computer_level: str | None = None


@dataclass(frozen=True)
class Seat:
    """A seat row: slot A or B, token hashes only (none for the computer's seat), and lastSeenAt."""

    seat_id: int
    room_code: str
    slot: str
    token_hash: str | None
    continue_token_hash: str | None
    continue_expires_at: float | None
    last_seen_at: float
    is_computer: bool = False


@dataclass(frozen=True)
class JoinResult:
    """The seat a join resolved to and the plain token to return to that client."""

    seat: Seat
    token: str
    created: bool  # True when this join created seat B


@dataclass(frozen=True)
class Transfer:
    """A redeemed continue link: the moved seat, its new plain token and the old token's hash."""

    seat: Seat
    token: str
    old_token_hash: str


def other_slot(slot: str) -> str:
    """Return the opposite seat slot."""
    return "B" if slot == "A" else "A"


# --- codes and tokens -------------------------------------------------------

def normalize_code(raw: str) -> str:
    """Uppercase and validate a room code (BR1.2); raise 400 when malformed."""
    code = (raw or "").strip().upper()
    if not CODE_PATTERN.match(code):
        raise DomainError(400, INVALID_CODE)
    return code


def generate_code() -> str:
    """Draw a 6-character code from a cryptographic random source (BR1.1)."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def issue_token() -> str:
    """Return a fresh URL-safe token with 256 bits of randomness."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in place of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str | None, stored_hash: str | None) -> bool:
    """Compare a presented token with a stored hash in constant time."""
    if not token or not stored_hash:
        return False
    return hmac.compare_digest(hash_token(token), stored_hash)


# --- reads ------------------------------------------------------------------

def _room_from_row(row: sqlite3.Row) -> Room:
    return Room(row["code"], row["created_at"], row["last_activity_at"], row["wins_a"],
                row["wins_b"], row["draws"], row["rematch_requested_by"], row["rematch_requested_at"],
                row["mode"], row["computer_level"])


def _seat_from_row(row: sqlite3.Row) -> Seat:
    return Seat(row["seat_id"], row["room_code"], row["slot"], row["token_hash"],
                row["continue_token_hash"], row["continue_expires_at"], row["last_seen_at"],
                bool(row["is_computer"]))


def get_room(conn: sqlite3.Connection, code: str) -> Room:
    """Return the room or raise 404 "Room not found"."""
    row = conn.execute("SELECT * FROM rooms WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise DomainError(404, ROOM_NOT_FOUND)
    return _room_from_row(row)


def room_exists(conn: sqlite3.Connection, code: str) -> bool:
    """Return True when a room with this code exists."""
    return conn.execute("SELECT 1 FROM rooms WHERE code = ?", (code,)).fetchone() is not None


def get_seats(conn: sqlite3.Connection, code: str) -> dict[str, Seat]:
    """Return the room's seats keyed by slot (zero to two entries)."""
    rows = conn.execute("SELECT * FROM seats WHERE room_code = ? ORDER BY slot", (code,)).fetchall()
    return {row["slot"]: _seat_from_row(row) for row in rows}


def find_seat(conn: sqlite3.Connection, code: str, token: str | None) -> Seat | None:
    """Return the room's seat whose token matches, comparing every seat in constant time."""
    found = None
    for seat in get_seats(conn, code).values():
        if token_matches(token, seat.token_hash):
            found = seat
    if found is None and token:
        from justchess import players
        linked = players.seat_id(conn, code, token)
        if linked is not None:
            found = next((seat for seat in get_seats(conn, code).values() if seat.seat_id == linked), None)
    return found


def authorize_seat(conn: sqlite3.Connection, code: str, token: str | None) -> Seat:
    """Return the seat for this token or raise 403 (BR1.6)."""
    seat = find_seat(conn, code, token)
    if seat is None:
        raise DomainError(403, NOT_YOUR_SEAT)
    return seat


# --- create, join, continue -------------------------------------------------

def _insert_seat_hash(conn: sqlite3.Connection, code: str, slot: str, token_hash: str, now: float) -> Seat:
    cur = conn.execute(
        "INSERT INTO seats (room_code, slot, token_hash, last_seen_at) VALUES (?, ?, ?, ?) RETURNING seat_id",
        (code, slot, token_hash, now),
    )
    return Seat(cur.fetchone()[0], code, slot, token_hash, None, None, now)


def _insert_seat(conn: sqlite3.Connection, code: str, slot: str, now: float) -> tuple[Seat, str]:
    token = issue_token()
    return _insert_seat_hash(conn, code, slot, hash_token(token), now), token


def create_room(conn: sqlite3.Connection, now: float,
                code_factory: Callable[[], str] = generate_code) -> tuple[Room, Seat, str]:
    """Create a room with a unique code and seat A; return the room, seat and plain token."""
    for _ in range(MAX_CODE_TRIES):
        code = code_factory()
        if room_exists(conn, code):
            continue
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at, mode) VALUES (?, ?, ?, ?)",
                     (code, now, now, MODE_WAITING))
        seat, token = _insert_seat(conn, code, "A", now)
        return get_room(conn, code), seat, token
    raise DomainError(503, CREATE_FAILED)


def _unused_code(conn: sqlite3.Connection, code_factory: Callable[[], str]) -> str:
    for _ in range(MAX_CODE_TRIES):
        code = code_factory()
        if not room_exists(conn, code):
            return code
    raise DomainError(503, CREATE_FAILED)


def create_computer_room(conn: sqlite3.Connection, now: float, level: str, white_slot: str,
                         code_factory: Callable[[], str] = generate_code) -> tuple[Room, Seat, str]:
    """P2 U4 BR3.1: a computer room at ``level`` with seat A (token) and the computer's seat B (no token).

    ``white_slot`` is only checked here (the caller starts game 1 with it). The
    computer's seat has no token hash, so no presented token can ever match it.
    """
    if level not in COMPUTER_LEVELS:
        raise DomainError(400, UNKNOWN_LEVEL)
    if white_slot not in SLOTS:
        raise DomainError(400, UNKNOWN_SLOT)
    code = _unused_code(conn, code_factory)
    conn.execute("INSERT INTO rooms (code, created_at, last_activity_at, mode, computer_level) VALUES (?, ?, ?, ?, ?)",
                 (code, now, now, MODE_COMPUTER, level))
    seat, token = _insert_seat(conn, code, "A", now)
    conn.execute("INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) VALUES (?, 'B', NULL, ?, 1)",
                 (code, now))
    return get_room(conn, code), seat, token


def is_stand_in(conn: sqlite3.Connection, code: str) -> bool:
    """True while the computer stands in for the friend this room is waiting for."""
    return conn.execute("SELECT 1 FROM room_stand_ins WHERE room_code = ?", (code,)).fetchone() is not None


def _take_over_computer_seat(conn: sqlite3.Connection, code: str, now: float) -> JoinResult:
    """Give the stand-in computer's seat B to the joiner; the room turns online."""
    token = issue_token()
    conn.execute("UPDATE seats SET is_computer = 0, token_hash = ?, last_seen_at = ? "
                 "WHERE room_code = ? AND slot = 'B' AND is_computer = 1", (hash_token(token), now, code))
    conn.execute("UPDATE rooms SET mode = ?, computer_level = NULL WHERE code = ?", (MODE_ONLINE, code))
    conn.execute("DELETE FROM room_stand_ins WHERE room_code = ?", (code,))
    games.bump_version(conn, games.current_game(conn, code))  # discards an engine reply still in flight
    return JoinResult(get_seats(conn, code)["B"], token, created=True)


def join_room(conn: sqlite3.Connection, code: str, token: str | None, now: float) -> JoinResult:
    """Rejoin by token, take seat B, or refuse a third player (BR1.3).

    Taking seat B turns a waiting room online in the same transaction (P2 U2 BR1.2).
    P2 U4 BR3.2: in a computer room only seat A's token rejoins; anything else is 409,
    except a stand-in room, whose computer seat the joiner takes over.
    """
    room = get_room(conn, code)
    existing = find_seat(conn, code, token)
    if existing is not None:
        return JoinResult(existing, token or "", created=False)
    if room.mode == MODE_COMPUTER:
        if is_stand_in(conn, code):
            return _take_over_computer_seat(conn, code, now)
        raise DomainError(409, COMPUTER_ROOM)
    if "B" in get_seats(conn, code):
        raise DomainError(409, ROOM_FULL)
    seat, new_token = _insert_seat(conn, code, "B", now)
    conn.execute("UPDATE rooms SET mode = ? WHERE code = ? AND mode = ?", (MODE_ONLINE, code, MODE_WAITING))
    return JoinResult(seat, new_token, created=True)


def issue_continue_token(conn: sqlite3.Connection, seat: Seat, now: float) -> str:
    """Issue a continue token for this seat, replacing any earlier one (BR1.5)."""
    token = issue_token()
    conn.execute(
        "UPDATE seats SET continue_token_hash = ?, continue_expires_at = ? WHERE seat_id = ?",
        (hash_token(token), now + CONTINUE_TTL, seat.seat_id),
    )
    return token


def redeem_continue_token(conn: sqlite3.Connection, code: str, continue_token: str | None,
                          now: float) -> Transfer:
    """Move a seat to a new device: fresh seat token, old token and continue token invalid."""
    target = None
    for seat in get_seats(conn, code).values():
        if token_matches(continue_token, seat.continue_token_hash):
            target = seat
    if target is None or target.continue_expires_at is None or now > target.continue_expires_at:
        raise DomainError(403, CONTINUE_INVALID)
    token = issue_token()
    conn.execute(
        "UPDATE seats SET token_hash = ?, continue_token_hash = NULL, continue_expires_at = NULL, "
        "player_id = NULL, last_seen_at = ? WHERE seat_id = ?",
        (hash_token(token), now, target.seat_id),
    )
    moved = get_seats(conn, code)[target.slot]
    return Transfer(moved, token, target.token_hash)


# --- activity and presence --------------------------------------------------

def touch_room(conn: sqlite3.Connection, code: str, now: float) -> None:
    """Record activity on the room (used by the 30-day cleanup)."""
    conn.execute("UPDATE rooms SET last_activity_at = ? WHERE code = ?", (now, code))


def touch_seat(conn: sqlite3.Connection, code: str, slot: str, now: float, force: bool = False) -> bool:
    """Write lastSeenAt at most once a minute per seat unless forced; return True if written."""
    threshold = now if force else now - LAST_SEEN_THROTTLE
    cur = conn.execute(
        "UPDATE seats SET last_seen_at = ? WHERE room_code = ? AND slot = ? AND last_seen_at <= ?",
        (now, code, slot, threshold),
    )
    return cur.rowcount > 0


def is_abandoned(seat: Seat, now: float, abandon_after: float = ABANDON_AFTER) -> bool:
    """A seat is abandoned when its lastSeenAt is older than ``abandon_after`` (24 hours by default, BR1.7)."""
    return now - seat.last_seen_at > abandon_after


def seat_presence(seat: Seat | None, connected: bool, now: float, abandon_after: float = ABANDON_AFTER) -> str:
    """Return ``empty``, ``connected``, ``away``, ``abandoned`` or (P2 U4) ``computer`` for one slot.

    ``abandon_after`` is gameplay.yaml's ``rooms.claim_win_away_hours`` in the app.
    """
    if seat is None:
        return "empty"
    if seat.is_computer:
        return "computer"
    if connected:
        return "connected"
    return "abandoned" if is_abandoned(seat, now, abandon_after) else "away"


# --- score and rematch ------------------------------------------------------

def result_slot(result: str, white_slot: str) -> str | None:
    """Map a game result to the winning slot, or None for a draw."""
    if result == "1-0":
        return white_slot
    if result == "0-1":
        return other_slot(white_slot)
    return None


def record_result(conn: sqlite3.Connection, code: str, result: str, white_slot: str,
                  counted: bool = True) -> None:
    """Add a finished game's result to the room score by slot (BR3.1).

    P2 U3 BR1.4: an uncounted (pass-along practice) game leaves the score alone.
    """
    if not counted:
        return
    winner = result_slot(result, white_slot)
    column = {"A": "wins_a", "B": "wins_b", None: "draws"}[winner]
    conn.execute(f"UPDATE rooms SET {column} = {column} + 1 WHERE code = ?", (code,))


def request_rematch(conn: sqlite3.Connection, room: Room, slot: str, game_finished: bool,
                    now: float) -> str:
    """Apply BR3.2. Return ``recorded``, ``unchanged`` (repeat request) or ``start``."""
    if not game_finished:
        raise DomainError(409, FINISH_FIRST)
    if room.rematch_requested_by == slot:
        return "unchanged"
    if room.rematch_requested_by == other_slot(slot):
        clear_rematch(conn, room.code)
        return "start"
    conn.execute(
        "UPDATE rooms SET rematch_requested_by = ?, rematch_requested_at = ? WHERE code = ?",
        (slot, now, room.code),
    )
    return "recorded"


def clear_rematch(conn: sqlite3.Connection, code: str) -> None:
    """Clear any pending rematch request."""
    conn.execute(
        "UPDATE rooms SET rematch_requested_by = NULL, rematch_requested_at = NULL WHERE code = ?",
        (code,),
    )


def rematch_state(room: Room, presence: dict[str, str]) -> dict[str, str | None]:
    """Compute the rematch state (BR3.3): lapsed is derived, never stored."""
    by = room.rematch_requested_by
    if by is None:
        return {"state": "none", "requestedBy": None}
    state = "lapsed" if presence.get(other_slot(by)) == "abandoned" else "pending"
    return {"state": state, "requestedBy": by}


# --- P2 U3: pass-along mode (BR1.1) ----------------------------------------

@dataclass(frozen=True)
class JoinRequestRow:
    """A join_requests row: only the requester's token hash is stored."""

    request_id: int
    room_code: str
    requester_token_hash: str
    status: str
    created_at: float
    expires_at: float
    answered_at: float | None


@dataclass(frozen=True)
class RequestRead:
    """The room's pending request after lapse-on-read, and whether this read lapsed one."""

    request: JoinRequestRow | None
    lapsed: bool = False


def _request_from_row(row: sqlite3.Row) -> JoinRequestRow:
    return JoinRequestRow(row["request_id"], row["room_code"], row["requester_token_hash"], row["status"],
                          row["created_at"], row["expires_at"], row["answered_at"])


def _set_request_status(conn: sqlite3.Connection, request_id: int, status: str, now: float) -> None:
    conn.execute("UPDATE join_requests SET status = ?, answered_at = ? WHERE request_id = ? AND status = ?",
                 (status, now, request_id, PENDING))


def lapse_if_expired(conn: sqlite3.Connection, request: JoinRequestRow, now: float) -> bool:
    """Mark a pending request past its expiry lapsed (BR2.4); return True when it did."""
    if request.status != PENDING or now < request.expires_at:
        return False
    _set_request_status(conn, request.request_id, LAPSED, now)
    return True


def pending_request(conn: sqlite3.Connection, code: str, now: float) -> RequestRead:
    """Return the room's pending, unexpired request; an expired one is lapsed on the way (BR2.4)."""
    row = conn.execute("SELECT * FROM join_requests WHERE room_code = ? AND status = ?", (code, PENDING)).fetchone()
    if row is None:
        return RequestRead(None)
    request = _request_from_row(row)
    if lapse_if_expired(conn, request, now):
        return RequestRead(None, lapsed=True)
    return RequestRead(request)


def visible_request(conn: sqlite3.Connection, code: str, now: float) -> JoinRequestRow | None:
    """Read-only view of the pending, unexpired request (for snapshots built on a read connection)."""
    row = conn.execute("SELECT * FROM join_requests WHERE room_code = ? AND status = ? AND expires_at > ?",
                       (code, PENDING, now)).fetchone()
    return _request_from_row(row) if row else None


def has_expired_pending(conn: sqlite3.Connection, code: str, now: float) -> bool:
    """True when the room has a pending request past its expiry (a read can lapse it)."""
    return conn.execute("SELECT 1 FROM join_requests WHERE room_code = ? AND status = ? AND expires_at <= ?",
                        (code, PENDING, now)).fetchone() is not None


@dataclass(frozen=True)
class ModeChange:
    """What ``set_mode`` did: the new mode, whether anything changed and whether it declined a request."""

    mode: str
    changed: bool
    declined_request: bool = False


def set_mode(conn: sqlite3.Connection, code: str, seat: Seat, mode: str, now: float,
             level: str | None = None) -> ModeChange:
    """Switch the room between waiting, pass-along and the computer stand-in (BR1.1).

    Seat A only (403), never once a friend holds seat B (409) or in a computer
    room made from the lobby (409). Entering pass-along starts a game still
    waiting, uncounted; leaving keeps the position and declines any pending join
    request in the same transaction. The stand-in is entered from waiting only
    and left back to waiting (see the module docstring).
    """
    if mode not in SWITCHABLE_MODES:
        raise DomainError(400, "Unknown mode")
    if seat.slot != "A":
        raise DomainError(403, CREATOR_ONLY)
    room = get_room(conn, code)
    stand_in = room.mode == MODE_COMPUTER and is_stand_in(conn, code)
    if room.mode == MODE_COMPUTER and not stand_in:
        raise DomainError(409, COMPUTER_ROOM)
    if room.mode == MODE_ONLINE or (not stand_in and "B" in get_seats(conn, code)):
        raise DomainError(409, ALREADY_JOINED)
    if room.mode == mode:
        return ModeChange(mode, changed=False)
    if mode == MODE_COMPUTER:
        return _start_stand_in(conn, code, room, level or STAND_IN_DEFAULT_LEVEL, now)
    if stand_in:
        if mode != MODE_WAITING:
            raise DomainError(409, WAIT_FIRST)
        conn.execute("DELETE FROM seats WHERE room_code = ? AND slot = 'B' AND is_computer = 1", (code,))
        conn.execute("UPDATE rooms SET mode = ?, computer_level = NULL WHERE code = ?", (MODE_WAITING, code))
        conn.execute("DELETE FROM room_stand_ins WHERE room_code = ?", (code,))
        _back_to_waiting(conn, code)
        return ModeChange(MODE_WAITING, changed=True)
    conn.execute("UPDATE rooms SET mode = ? WHERE code = ?", (mode, code))
    if mode == MODE_PASS_ALONG:
        games.start_pass_along(conn, games.current_game(conn, code), now)
        return ModeChange(mode, changed=True)
    _back_to_waiting(conn, code)
    pending = pending_request(conn, code, now).request
    if pending is not None:
        _set_request_status(conn, pending.request_id, DECLINED, now)
    return ModeChange(mode, changed=True, declined_request=pending is not None)


def _back_to_waiting(conn: sqlite3.Connection, code: str) -> None:
    """Back to waiting for a friend: a game with no moves waits again (status waiting, counted).

    A game with moves keeps its position; moves stay refused until a friend
    takes seat B (``games.require_opponent``), who continues from there.
    """
    game = games.current_game(conn, code)
    if game.status == games.PLAYING and not games.load_moves(conn, game.game_id):
        conn.execute("UPDATE games SET status = ?, started_at = NULL, counted = 1, version = version + 1 "
                     "WHERE game_id = ?", (games.WAITING, game.game_id))
    else:
        games.bump_version(conn, game)


def _start_stand_in(conn: sqlite3.Connection, code: str, room: Room, level: str, now: float) -> ModeChange:
    """The computer takes seat B of a waiting friend room until a friend joins."""
    if level not in COMPUTER_LEVELS:
        raise DomainError(400, UNKNOWN_LEVEL)
    if room.mode != MODE_WAITING:
        raise DomainError(409, WAIT_FIRST)
    conn.execute("UPDATE rooms SET mode = ?, computer_level = ? WHERE code = ?", (MODE_COMPUTER, level, code))
    conn.execute("INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) VALUES (?, 'B', NULL, ?, 1)",
                 (code, now))
    conn.execute("INSERT INTO room_stand_ins (room_code, started_at) VALUES (?, ?)", (code, now))
    game = games.current_game(conn, code)
    if not games.start_pass_along(conn, game, now):  # a waiting game starts, uncounted; else keep the position
        games.bump_version(conn, game)
    return ModeChange(MODE_COMPUTER, changed=True)


CANNOT_SWITCH = "You can't switch sides now"
UNKNOWN_COLOUR = "Unknown colour"


def can_switch_side(conn: sqlite3.Connection, code: str, room: Room, game: games.Game) -> bool:
    """True when seat A may take the other colour in the current game (see the module docstring)."""
    if game.status == games.FINISHED:
        return False
    if room.mode == MODE_COMPUTER:
        return game.status == games.PLAYING
    if room.mode not in (MODE_WAITING, MODE_PASS_ALONG) or "B" in get_seats(conn, code):
        return False
    return not games.load_moves(conn, game.game_id)


def switch_side(conn: sqlite3.Connection, code: str, seat: Seat, colour: str) -> bool:
    """Seat A takes ``colour`` in the current game; return True when anything changed."""
    if colour not in games.COLOURS:
        raise DomainError(400, UNKNOWN_COLOUR)
    if seat.slot != "A":
        raise DomainError(403, CREATOR_ONLY)
    room, game = get_room(conn, code), games.current_game(conn, code)
    if game.colour_of("A") == colour:
        return False
    if not can_switch_side(conn, code, room, game):
        raise DomainError(409, CANNOT_SWITCH)
    flipped = "B" if game.white_slot == "A" else "A"
    played = bool(games.load_moves(conn, game.game_id))
    # A computer game switched after its first move no longer counts toward the score.
    counted = 0 if (room.mode == MODE_COMPUTER and played) else int(game.counted)
    conn.execute("UPDATE games SET white_slot = ?, counted = ?, version = version + 1 WHERE game_id = ?",
                 (flipped, counted, game.game_id))
    return True


# --- P2 U3: join requests (BR2.1-BR2.4) -----------------------------------

class RequestAddressBook:
    """In memory: the client address behind each request, and addresses declined per room.

    ``declined_recently`` is true for 10 minutes after the creator declined a
    request from that address in that room (BR2.1). At most 10,000 entries are
    kept in each table, oldest dropped first; a restart forgets everything
    (accepted, like the rate windows).
    """

    def __init__(self, memory: float = DECLINE_MEMORY, limit: int = MAX_REMEMBERED_ADDRESSES) -> None:
        self.memory = memory
        self.limit = limit
        self._by_request: OrderedDict[int, str] = OrderedDict()
        self._declined: OrderedDict[tuple[str, str], float] = OrderedDict()

    @staticmethod
    def _bounded(table: OrderedDict, limit: int) -> None:
        while len(table) > limit:
            table.popitem(last=False)

    def note_request(self, request_id: int, address: str) -> None:
        """Remember which client address made this request."""
        self._by_request[request_id] = address
        self._bounded(self._by_request, self.limit)

    def note_declined(self, request_id: int, code: str, now: float) -> None:
        """The creator declined this request: block its address in the room for a while."""
        address = self._by_request.pop(request_id, None)
        if address is None:
            return
        self._declined.pop((code, address), None)
        self._declined[(code, address)] = now
        self._bounded(self._declined, self.limit)

    def declined_recently(self, code: str, address: str, now: float) -> bool:
        """True when this address had a request declined in this room within the memory window."""
        declined_at = self._declined.get((code, address))
        if declined_at is None:
            return False
        if now - declined_at >= self.memory:
            del self._declined[(code, address)]
            return False
        return True


@dataclass(frozen=True)
class JoinRequestOutcome:
    """The pass-along branch of a join: ``created``, ``existing``, ``busy`` or ``declined_recently``."""

    kind: str
    request: JoinRequestRow | None = None
    token: str | None = None
    lapsed: bool = False


def find_request(conn: sqlite3.Connection, code: str, token: str | None, now: float) -> RequestRead:
    """Return the room's request whose token matches (any status), lapsing it on read when expired."""
    if not token:
        return RequestRead(None)
    row = conn.execute("SELECT * FROM join_requests WHERE room_code = ? AND requester_token_hash = ?",
                       (code, hash_token(token))).fetchone()
    if row is None:
        return RequestRead(None)
    request = _request_from_row(row)
    if lapse_if_expired(conn, request, now):
        return RequestRead(_request_from_row(conn.execute(
            "SELECT * FROM join_requests WHERE request_id = ?", (request.request_id,)).fetchone()), lapsed=True)
    return RequestRead(request)


def create_join_request(conn: sqlite3.Connection, code: str, token: str | None, now: float,
                        declined_recently: bool = False, ttl: float = REQUEST_TTL) -> JoinRequestOutcome:
    """BR2.1 after the seat-token rejoin check: return the visitor's own pending request, refuse, or create one.

    Order: the visitor's own pending request (same expiry), a pending request of
    someone else (busy), a recent decline of this address (declined_recently),
    else a new request with a fresh token whose hash alone is stored.
    """
    own = find_request(conn, code, token, now)
    if own.request is not None and own.request.status == PENDING:
        return JoinRequestOutcome("existing", own.request, token, own.lapsed)
    current = pending_request(conn, code, now)
    lapsed = own.lapsed or current.lapsed
    if current.request is not None:
        return JoinRequestOutcome("busy", lapsed=lapsed)
    if declined_recently:
        return JoinRequestOutcome("declined_recently", lapsed=lapsed)
    new_token = issue_token()
    cur = conn.execute(
        "INSERT INTO join_requests (room_code, requester_token_hash, status, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?) RETURNING request_id",
        (code, hash_token(new_token), PENDING, now, now + ttl),
    )
    request = JoinRequestRow(cur.fetchone()[0], code, hash_token(new_token), PENDING, now, now + ttl, None)
    return JoinRequestOutcome("created", request, new_token, lapsed)


@dataclass(frozen=True)
class Answer:
    """What ``answer_request`` did: ``accepted``, ``declined`` or ``none`` (nothing to answer)."""

    kind: str
    request: JoinRequestRow | None = None
    seat: Seat | None = None
    lapsed: bool = False


def answer_request(conn: sqlite3.Connection, code: str, seat: Seat, accept: bool, now: float,
                   addresses: RequestAddressBook | None = None) -> Answer:
    """BR2.2: seat A accepts or declines the pending request.

    Seat A only (403, raised before anything is written). ``none`` when there is
    no pending, unexpired request, the room left pass-along or seat B exists; the
    caller answers 409 "No pending request" after committing any lapse. Accept
    creates seat B from the request's token hash, turns the room online, counts
    the current game when it is not finished and marks the request accepted.
    """
    if seat.slot != "A":
        raise DomainError(403, CREATOR_ONLY)
    room = get_room(conn, code)
    current = pending_request(conn, code, now)
    request = current.request
    if request is None or room.mode != MODE_PASS_ALONG or "B" in get_seats(conn, code):
        return Answer("none", lapsed=current.lapsed)
    if not accept:
        _set_request_status(conn, request.request_id, DECLINED, now)
        if addresses is not None:
            addresses.note_declined(request.request_id, code, now)
        return Answer("declined", request)
    seat_b = _insert_seat_hash(conn, code, "B", request.requester_token_hash, now)
    conn.execute("UPDATE rooms SET mode = ? WHERE code = ?", (MODE_ONLINE, code))
    games.mark_counted(conn, games.current_game(conn, code))
    _set_request_status(conn, request.request_id, ACCEPTED, now)
    return Answer("accepted", request, seat_b)


def request_status(conn: sqlite3.Connection, code: str, token: str | None, now: float) -> tuple[dict, bool]:
    """BR2.3: ``{status, expiresAt}`` for the request holding ``token``, else ``{status: "unknown"}``.

    Writes nothing except the lapse of BR2.4; the second value says whether it lapsed.
    """
    get_room(conn, code)
    read = find_request(conn, code, token, now)
    if read.request is None:
        return {"status": "unknown"}, False
    return {"status": read.request.status, "expiresAt": read.request.expires_at}, read.lapsed


def lapse_expired(conn: sqlite3.Connection, now: float) -> int:
    """Housekeeping (BR2.4): mark every pending request past its expiry lapsed; return how many."""
    cur = conn.execute("UPDATE join_requests SET status = ?, answered_at = ? WHERE status = ? AND expires_at <= ?",
                       (LAPSED, now, PENDING, now))
    return cur.rowcount


def join_request_view(request: JoinRequestRow | None, now: float) -> dict[str, float] | None:
    """The snapshot's ``joinRequest`` for seat A: ``{expiresAt, expiresIn}`` or None."""
    if request is None:
        return None
    return {"expiresAt": request.expires_at, "expiresIn": max(0.0, request.expires_at - now)}


# --- cleanup ----------------------------------------------------------------

def list_idle_rooms(conn: sqlite3.Connection, cutoff: float) -> list[str]:
    """Return codes of rooms with no activity since ``cutoff``."""
    rows = conn.execute("SELECT code FROM rooms WHERE last_activity_at < ? ORDER BY code", (cutoff,))
    return [row["code"] for row in rows]


def delete_room(conn: sqlite3.Connection, code: str) -> None:
    """Delete the room and its seats. Games data must be deleted first by Games."""
    conn.execute("DELETE FROM room_stand_ins WHERE room_code = ?", (code,))
    conn.execute("DELETE FROM seats WHERE room_code = ?", (code,))
    conn.execute("DELETE FROM rooms WHERE code = ?", (code,))
