"""Room summaries: the read model behind the "Your games" list (P2 U2, BR2.1-BR2.3, W4).

``POST /api/rooms/summaries`` takes ``{"seats": [{"code", "token"}, ...]}`` in
its body (never in a URL) and answers ``{"rooms": [RoomSummary, ...]}`` in
request order:

- ``parse_request(raw)`` validates the body: 1-50 entries, each code 6
  characters A-Z0-9, each token 1-128 characters. Anything else raises
  ``DomainError(400, "Invalid summary request", error="bad_request")``; the
  message is fixed and never echoes a submitted value. Entries are
  deduplicated by the (code, token) pair, so a browser that holds both seats of
  one room gets one summary per seat.
- ``build_summaries(db, pairs, now)`` reads everything in one read
  transaction and writes nothing: last-seen and last-activity are not touched,
  so asking for a summary never keeps an idle room alive (BR2.3). Seat tokens
  are compared with every stored hash of the room in constant time
  (``rooms.token_matches``); the computer's seat has no hash and never matches.

A RoomSummary (entities.md, BR2.2) is ``{code, found: false}`` for an unknown
room or a token that matches no seat in it, so a wrong token does not reveal
that the room exists. Otherwise it is ``found: true`` with ``kind``
(``computer`` or ``friend``), ``computerLevel``, ``opponent`` (``computer``,
``joined`` or ``waiting``), ``colour``, ``status``, ``yourTurn``, ``result``
(``won``, ``lost`` or ``drawn`` from this seat's view, else ``None``),
``endReason`` (added so the list can name how a game ended), ``lastActivityAt``
and ``endedAt`` (server epoch seconds), ``fen`` and ``pendingJoinRequest``
(a pending, unexpired join request exists and this is seat A).

Tokens are never logged and never put into an error message.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field

from justchess import DomainError, games, players, rooms
from justchess.db import Database

PATH = "/api/rooms/summaries"
MAX_BODY_BYTES = 8192  # this route only; every other route keeps security.MAX_BODY_BYTES
MAX_SEATS = 50
TOKEN_MAX = 128
CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")
INVALID_REQUEST = "Invalid summary request"


def _invalid() -> DomainError:
    return DomainError(400, INVALID_REQUEST, error="bad_request")


# --- request ------------------------------------------------------------------

def _valid_entry(entry: object) -> tuple[str, str] | None:
    if not isinstance(entry, dict):
        return None
    code, token = entry.get("code"), entry.get("token")
    if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
        return None
    if not isinstance(token, str) or not 1 <= len(token) <= TOKEN_MAX:
        return None
    return code, token


def parse_request(raw: bytes) -> list[tuple[str, str]]:
    """Validate the request body (BR2.1) and return the distinct (code, token) pairs in order."""
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _invalid() from None
    seats = body.get("seats") if isinstance(body, dict) else None
    if not isinstance(seats, list) or not 1 <= len(seats) <= MAX_SEATS:
        raise _invalid()
    pairs: list[tuple[str, str]] = []
    for entry in seats:
        pair = _valid_entry(entry)
        if pair is None:
            raise _invalid()
        if pair not in pairs:
            pairs.append(pair)
    return pairs


# --- read model ---------------------------------------------------------------

@dataclass(frozen=True)
class _RoomFacts:
    """Everything one room contributes to its seats' summaries, read once."""

    room: rooms.Room
    seats: dict[str, rooms.Seat]
    game: games.Game
    pending_request: bool
    nicknames: dict[str, str] = field(default_factory=dict)  # slot -> the seat's player nickname, when it has one


def _load_room(conn: sqlite3.Connection, code: str, now: float) -> _RoomFacts | None:
    if not rooms.room_exists(conn, code):
        return None
    try:
        game = games.current_game(conn, code)
    except DomainError:  # a room without a game cannot be shown; answer it as not found
        return None
    pending = conn.execute(
        "SELECT 1 FROM join_requests WHERE room_code = ? AND status = 'pending' AND expires_at > ?",
        (code, now),
    ).fetchone() is not None
    names = {slot: name for slot, name in players.names(conn, code).items() if name}
    return _RoomFacts(rooms.get_room(conn, code), rooms.get_seats(conn, code), game, pending, names)


def _seat_for(facts: _RoomFacts, token: str) -> rooms.Seat | None:
    """The room's seat whose hash matches ``token``, comparing every seat in constant time."""
    found = None
    for seat in facts.seats.values():
        if rooms.token_matches(token, seat.token_hash):
            found = seat
    return found


def _side_to_move(fen: str) -> str:
    """``white`` or ``black`` from the game's cached FEN (its second field)."""
    fields = fen.split()
    return "black" if len(fields) > 1 and fields[1] == "b" else "white"


def _result_for(game: games.Game, slot: str) -> str | None:
    if game.status != games.FINISHED or game.result is None:
        return None
    winner = rooms.result_slot(game.result, game.white_slot)
    if winner is None:
        return "drawn"
    return "won" if winner == slot else "lost"


def _opponent(facts: _RoomFacts, slot: str) -> str:
    other = facts.seats.get(rooms.other_slot(slot))
    if other is None:
        return "waiting"
    return "computer" if other.is_computer else "joined"


def summarize(facts: _RoomFacts, seat: rooms.Seat) -> dict[str, object]:
    """Build one found RoomSummary from the seat holder's view (BR2.2)."""
    room, game = facts.room, facts.game
    colour = game.colour_of(seat.slot)
    return {
        "code": room.code,
        "found": True,
        "kind": "computer" if room.mode == rooms.MODE_COMPUTER else "friend",
        "computerLevel": room.computer_level,
        "opponent": _opponent(facts, seat.slot),
        "colour": colour,
        "status": game.status,
        "yourTurn": game.status == games.PLAYING and _side_to_move(game.fen) == colour,
        "result": _result_for(game, seat.slot),
        "endReason": game.end_reason,
        "lastActivityAt": room.last_activity_at,
        "endedAt": game.ended_at,
        "fen": game.fen,
        "pendingJoinRequest": facts.pending_request and seat.slot == "A",
        # The friend's nickname, when they joined and set one (never the computer's seat).
        "opponentNickname": facts.nicknames.get(rooms.other_slot(seat.slot)) if _opponent(facts, seat.slot) == "joined" else None,
        "passAlong": room.mode == rooms.MODE_PASS_ALONG,
    }


def build_summaries(db: Database, pairs: Iterable[tuple[str, str]], now: float) -> list[dict[str, object]]:
    """Answer every (code, token) pair from one read transaction; nothing is written (BR2.3)."""
    answers: list[dict[str, object]] = []
    with db.read() as conn:
        conn.execute("BEGIN")  # deferred: one consistent snapshot of every room, no write lock
        try:
            loaded: dict[str, _RoomFacts | None] = {}
            for code, token in pairs:
                if code not in loaded:
                    loaded[code] = _load_room(conn, code, now)
                facts = loaded[code]
                seat = rooms.find_seat(conn, code, token) if facts is not None else None
                answers.append(summarize(facts, seat) if seat is not None else {"code": code, "found": False})
        finally:
            conn.execute("ROLLBACK")  # read-only: there is never anything to commit
    return answers
