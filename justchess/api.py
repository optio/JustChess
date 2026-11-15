"""HttpApi: routes, orchestration and the application factory.

Every state change runs under the room's ``asyncio.Lock`` inside one
``BEGIN IMMEDIATE`` transaction, then broadcasts the per-viewer snapshot. A
request that loses a race gets 409 with the latest snapshot, never a 500. The
app is designed to run as one process (one Uvicorn worker), because the room
locks and live sockets are in memory.

The seat token travels in request bodies for actions and in the ``X-Seat-Token``
header for state reads; it is never read from a query string and never logged.
Database errors are logged with the room code only.

``create_app()`` takes the database path, clock, Stockfish folder, socket
receive timeout, origin, cleanup hooks and lessons folder as parameters so tests
can inject them; production reads ``JUSTCHESS_DB``, ``JUSTCHESS_ORIGIN`` and
``JUSTCHESS_LESSONS_DIR``.

Lessons (U6): the lessons folder is resolved once in ``create_app`` (default
``lessons/`` next to ``app.py``) and read through ``justchess.lessons``. The
page shell is also served at ``/learn`` and ``/learn/{id}``.

Blunder warnings (U4): ``POST /api/rooms/{code}/check-move`` takes the same body
as a move (``{token, uci, version}``), runs U1's checks under the room lock with
a read-only connection, then replays the copied moves and runs
``justchess.analysis`` in a worker thread outside the lock. It never writes and
never changes the version. The origin and body size middleware apply as usual.

Notifications (U5):

- ``GET /api/push/key`` answers ``{publicKey}`` when VAPID keys are loaded,
  else 404 ``{enabled: false}``.
- ``POST /api/rooms/{code}/push/subscribe`` (``{token, endpoint, keys}``) stores
  the seat's own subscription after ``notifications.validate_subscription``;
  ``POST .../push/unsubscribe`` (``{token, endpoint}``) deletes it, and an
  unsubscribe with no endpoint is refused with 400.
- ``GET /sw.js`` serves ``static/sw.js`` with ``Service-Worker-Allowed: /`` and
  ``Cache-Control: no-cache``.
- After the join, move, claim-draw and claim-win transactions commit, the
  handler builds the AlertEvent, reads the target seat's presence and
  freshness from the hub, and schedules ``Notifier.dispatch_safely`` as a
  ``BackgroundTask`` that runs in a worker thread after the response is sent.
  The worker never reads hub state, and a failure there is logged and never
  fails the request.
- Redeeming a continue link deletes the moved seat's subscriptions in the same
  transaction. ``notifications.delete_room_data`` always runs as the first
  housekeeping hook.

``create_app`` also takes ``vapid`` (default: ``vapid.load_vapid()`` at startup)
and ``push_sender`` (default: the pywebpush sender) so tests can inject them.

Your games (P2 U2, W4): ``POST /api/rooms/summaries`` takes
``{seats: [{code, token}]}`` (1-50 entries) and answers ``{rooms: [...]}``
through ``justchess.summaries``. The body is read raw and validated there, so a
malformed body gets the fixed 400 "Invalid summary request" and never a
validation error that echoes the submitted tokens. It is origin-checked like
every POST, its body limit is 8 KB (the one override of the 4 KB limit), it
writes nothing, and neither tokens nor room codes from the body are logged.

Trainer (P2 U5, W3, BR1.2, BR2.4):

- ``GET /api/lessons?kind=opening|trap|defence`` lists one kind; any other
  value is 400 "Unknown lesson kind". Without ``kind`` every lesson is listed.
- The puzzle store (``justchess.puzzles``, folder ``puzzles_dir``, else
  ``JUSTCHESS_PUZZLES_DIR``, else ``puzzles/``) is loaded once at start-up.
- ``GET /api/puzzles`` -> ``[{theme, label, count}]`` (empty when the folder is
  missing); ``GET /api/puzzles/{theme}`` -> ``[{id, rating}]`` in rating order;
  ``GET /api/puzzles/{theme}/{id}`` -> the detail without the solution;
  ``POST .../check`` ``{ply, uci}`` and ``POST .../hint`` ``{ply, level}``.
  Unknown theme or id is 404; a bad ply, level or an illegal move is 400.
  They only read, need no seat or token, and the POSTs go through the usual
  origin check and 4 KB body limit.
- ``GET /learn/tactics/{theme}`` serves the page shell.

Pass-along and join requests (P2 U3, BR1.1-BR1.5, BR2.1-BR2.5, BR3.1):

- ``POST /api/rooms/{code}/mode`` ``{token, mode: "pass_along" | "waiting" | "computer", level?}``
  switches the room for seat A (``rooms.set_mode``) and answers seat A's
  snapshot; 403 for another seat, 409 once a friend holds seat B. ``computer``
  lets the computer stand in for the friend (from waiting only; 503 without
  an engine); a later join takes over the computer's seat. Snapshots carry
  ``standIn``.
- ``POST /api/rooms/{code}/join`` runs the seat-token rejoin check first. Only
  then, for a pass-along room: the rate limit for the client address
  (``ratelimit``; 429 ``{error: "too_many"}``), then the visitor's own pending
  request back, 409 ``{error: "busy"}``, 409 ``{error: "declined_recently"}``,
  or a new request: 202 ``{requestPending, requestToken, expiresAt, expiresIn, colour}``.
  Seat A gets a broadcast and the ``join-request:<id>`` alert.
- ``POST .../join-request/answer`` ``{token, accept}``: seat A accepts (the
  request token becomes seat B's token) or declines; 409 "No pending request"
  otherwise, after committing any lapse.
- ``POST .../join-request/status`` ``{requestToken}``: ``{status, expiresAt?}``
  for the joiner's poll; it writes nothing but a lapse.
- In pass-along, moves, draw claims and move checks let seat A play both
  colours and alert nobody; "Play again" starts the next game for seat A alone.
- Seat A's snapshot carries ``joinRequest``; ``GET /api/rooms/{code}`` lapses
  an expired request first (under the room lock) and broadcasts, and every
  change to a request is broadcast.

Tokens, request tokens included, travel in bodies only and are never logged.

Gameplay settings: ``gameplay.yaml`` (``justchess.gameplay``) is loaded once in
``create_app``; ``Services.gameplay`` carries the levels, limits and lifetimes
into the routes, and the page's keys are rendered into the app shell as a JSON
``<script id="gameplay-config">``.

Play the computer (P2 U4, BR1.5, BR3.1-BR3.6, BR4.1-BR4.3, BR5.1-BR5.6, BR6.1, BR6.2, BR7.1, BR7.2):

- Lifecycle: ``Services.engine`` (``engine_factory()`` from ``create_app``,
  default ``engine.Engine()``) reports "starting" until ``_prepare_stockfish``
  has found a binary and the process is open; no binary marks it missing. At
  shutdown the reply tasks are cancelled and the engine is stopped.
  ``GET /api/engine`` keeps ``{available, path_source, version}`` (``available``
  now means the engine process is running) and adds ``reason``.
- ``POST /api/rooms`` with ``{kind: "computer", level, colour}`` (colour
  ``white``, ``black`` or ``random``, resolved by ``colour_chooser``, default
  ``secrets.choice``) creates a computer room: 400 for a bad kind, level or
  colour, 429 past 10 per minute per client address, 503 while the engine is
  unavailable. It answers 201 ``{code, token, slot, colour, computer}``. Without
  a kind (or with ``friend``) it creates a friend room exactly as before.
- After every commit that leaves the computer to move in a playing computer
  game (create, move, rematch, computer-move), ``Services.ask_reply`` enqueues
  the reply synchronously, outside the room lock, and the coordinator holds
  ``ReplyInFlight {gameId, version, requestId}`` until the request ends. The
  completion re-takes the room lock and applies the move as seat B only to the
  unchanged game (same game id and version, playing, seat B to move, legal);
  otherwise it is discarded. A failure (not busy) sets the room's 5 s backoff.
  Either way the flag is cleared (only by its own request) and the room is
  broadcast. Queue progress goes to the room's sockets as ``computer`` events.
- Moves in a computer room answer 503 while the engine is unavailable and
  alert nobody. ``POST …/computer-move`` ``{token}`` (30 per minute) asks for
  the reply when it is due; ``POST …/takeback`` and ``POST …/resign``
  ``{token, version}``; ``POST …/hint`` ``{token, version}`` (20 per minute,
  refused at 16 queued requests, one per room, cancelled when the client goes
  away) answers ``{uci, from, to, san, version}``. Rematch takes an optional
  ``colour``; claim-draw and claim-win answer 409 in computer rooms.
- Every snapshot of a computer room carries ``computer`` (``computer.computer_state``);
  ``computer.message`` is set only in the HTTP answer right after a busy refusal.

Endgame trainer (P2 U6, BR2.5, BR3.1-BR3.3):

- The catalog (``justchess.endgames``, folder ``endgames_dir``, else ``endgames/``)
  is loaded once at start-up. ``GET /api/endgames`` -> ``{installed, available,
  reason, categories}`` (availability from ``Engine.status``);
  ``GET /api/endgames/{id}`` -> the position (404 "No such position"). Both
  work without the engine.
- ``POST /api/endgames/{id}/play`` ``{moves}`` (origin-checked, default 4 KB
  body limit, 30 per minute per address): the moves are replayed from the
  start FEN (400 when malformed, illegal, even length or too long) and judged.
  While the attempt is playing, the defender's reply is asked from Engine at
  skill 20 for 1 s (no depth, never random): 503 when unavailable, busy when
  ``refusal_queue`` requests already wait or the queue is full, and busy when
  the wait passes ``wait_limit_seconds`` (the request is cancelled, as it is
  when the client goes away). The answer is ``{status, reason, reply,
  playerMoves, movesLeft}`` plus the boards the page draws. Nothing is stored.
- Hints and endgame replies wait through the same neutral helper
  ``_await_engine``. ``GET /learn/endgames/{id}`` serves the page shell.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import secrets
import sqlite3
import time
import weakref
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, TypeVar

import chess
from fastapi import BackgroundTasks, Body, FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import stockfish_install
from justchess import DomainError, analysis, computer, endgames, games, housekeeping, lessons, notifications, players, puzzles, ratelimit, rooms, summaries
from justchess.coordination import Coordination, AddressBook
from justchess import outbox, work
from justchess import engine as engine_module
from justchess import gameplay as gameplay_module
from justchess import vapid as vapid_keys
from justchess.db import Database, prepare_configured_database
from justchess.live import CLOSE_POLICY, CLOSE_SERVER_ERROR, RECEIVE_TIMEOUT, LiveHub, SnapshotFor
from justchess.security import MAX_BODY_BYTES, BodyLimitMiddleware, OriginGuardMiddleware

logger = logging.getLogger("justchess")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENGINE_DIR = ROOT / ".engines" / f"stockfish-{stockfish_install.PINNED_VERSION}"
SERVER_ERROR = "Something went wrong, please try again"
TOKEN_MAX = 256

T = TypeVar("T")
PathSetting = Path | str | Callable[[], Path] | None
LESSON_NOT_FOUND = "Lesson not found"
UNKNOWN_KIND = "Unknown lesson kind"
PUZZLE_NOT_FOUND = "Puzzle not found"
THEME_NOT_FOUND = "Puzzle theme not found"
FEN_MAX = 100
PUSH_DISABLED = "Push notifications are not enabled on this server"
SERVICE_WORKER = ROOT / "static" / "sw.js"
TOO_MANY = "Too many requests. Try again shortly."
RETRY_AFTER_SECONDS = str(int(ratelimit.WINDOW_SECONDS))

# P2 U4: play the computer.
NOT_FOR_COMPUTER = "Not available against the computer"
TAKEBACK_ONLY = "Takeback is only for games against the computer"
RESIGN_ONLY = "Resigning is only for games against the computer"
HINT_ONLY = "Hints are only for games against the computer"
COMPUTER_ONLY = "This is only for games against the computer"
ENGINE_DOWN = "The computer is not available right now"
HINT_PENDING = "A hint is already on its way"
HINT_CANCELLED = "The hint was cancelled"
COMPUTERS_TURN = "It's the computer's turn"
UNKNOWN_ROOM_KIND = "Unknown room kind"
UNKNOWN_COLOUR = "Unknown colour"
COLOUR_CHOICES = ("white", "black", "random")
HINT_POLL_SECONDS = 0.25
ENGINE_POLL_SECONDS = HINT_POLL_SECONDS  # how often a waiting request checks the client is still there

# P2 U6: the endgame trainer.
POSITION_NOT_FOUND = "No such position"
ENDGAME_CANCELLED = "The move was cancelled"
ColourChooser = Callable[[Sequence[str]], str]
EngineFactory = Callable[[], engine_module.Engine]

# A seat action returns the acting slot, whether it changed anything, and the U5 alert (or None).
ActionResult = tuple[str, bool, "notifications.AlertEvent | None"]
SeatAction = Callable[[sqlite3.Connection, float], ActionResult]


# --- request models ---------------------------------------------------------

class JoinRequest(BaseModel):
    """Join body: an optional seat token for a rejoin."""

    token: str | None = Field(default=None, max_length=TOKEN_MAX)


class SeatRequest(BaseModel):
    """Body of a seat action: the seat token."""

    token: str = Field(min_length=1, max_length=TOKEN_MAX)


class MoveRequest(SeatRequest):
    """Move body: seat token, move in UCI (promotion letter included) and the board version seen."""

    uci: str = Field(min_length=1, max_length=8)
    version: int = Field(ge=0)


class CreateRoomRequest(BaseModel):
    """P2 U4 create body (optional): ``kind`` friend (default) or computer, with ``level`` and ``colour`` for computer."""

    kind: str | None = Field(default=None, max_length=16)
    level: str | None = Field(default=None, max_length=16)
    colour: str | None = Field(default=None, max_length=8)


class VersionedSeatRequest(SeatRequest):
    """P2 U4 takeback, resign and hint body: the seat token and the board version seen."""

    version: int = Field(ge=0)


class RematchRequest(SeatRequest):
    """Rematch body: the seat token and, in a computer room (P2 U4), an optional colour."""

    colour: str | None = Field(default=None, max_length=8)


class ModeRequest(SeatRequest):
    """P2 U3 mode body: seat A's token and the mode to switch to (checked by ``rooms.set_mode``)."""

    mode: str = Field(min_length=1, max_length=16)
    level: str | None = Field(default=None, max_length=16)  # the computer stand-in's level (mode "computer")


class AnswerRequest(SeatRequest):
    """P2 U3 answer body: seat A's token and whether to accept the pending join request."""

    accept: bool


class RequestStatusRequest(BaseModel):
    """P2 U3 status body: the joiner's request token (never in a URL)."""

    requestToken: str = Field(min_length=1, max_length=TOKEN_MAX)


class ContinueRequest(BaseModel):
    """Continue body: the continue token taken from the link fragment."""

    continueToken: str = Field(min_length=1, max_length=TOKEN_MAX)


class PositionMoveRequest(BaseModel):
    """Free-play body (BR2.3): a position and a move in UCI. Both are checked before use."""

    fen: str = Field(min_length=1, max_length=FEN_MAX)
    uci: str = Field(min_length=1, max_length=8)


class PuzzleCheckRequest(BaseModel):
    """P2 U5 check body: the index of the expected player move and the move in UCI.

    Loosely typed so ``justchess.puzzles`` answers every bad value with 400.
    """

    ply: object = None
    uci: object = None


class PuzzleHintRequest(BaseModel):
    """P2 U5 hint body: the ply and the level (piece, move or solution)."""

    ply: object = None
    level: object = None


class EndgamePlayRequest(BaseModel):
    """P2 U6 play body: the attempt's UCI moves from the start position.

    Loosely typed so ``endgames.replay`` answers every bad value with 400.
    """

    moves: object = None


class SubscribeRequest(SeatRequest):
    """U5 subscribe body: the seat token and the browser's PushSubscription.toJSON() fields.

    Endpoint and keys are loosely typed here and checked by Notifications, so
    every bad subscription gets the same 400 "Invalid push subscription".
    """

    endpoint: object = None
    keys: object = None


class UnsubscribeRequest(SeatRequest):
    """U5 unsubscribe body: the seat token and the endpoint to remove (required)."""

    endpoint: object = None


# --- services ---------------------------------------------------------------

class Services:
    """Per-app state: the database, the clock, the room locks, the live hub and the notifier."""

    def __init__(self, db: Database, clock: Callable[[], float], receive_timeout: float,
                 vapid: vapid_keys.VapidConfig | None = None,
                 push_sender: notifications.Sender | None = None,
                 push_hosts: Sequence[str] = notifications.DEFAULT_PUSH_HOSTS,
                 trusted_proxies: Sequence[ratelimit.Network] = (),
                 engine: engine_module.Engine | None = None,
                 colour_chooser: ColourChooser = secrets.choice,
                 gameplay: gameplay_module.Gameplay | None = None,
                 move_chooser: computer.MoveChooser | None = None) -> None:
        self.db = db
        self.clock = clock
        settings = gameplay if gameplay is not None else gameplay_module.DEFAULT_GAMEPLAY
        self.gameplay = settings  # gameplay.yaml, loaded once in create_app
        # P2 U4: the engine, the per-room reply and hint flags, and the engine-route limits (in memory).
        self.engine = engine if engine is not None else _engine_for(settings)
        self.coordinator = computer.ComputerCoordinator(clock, backoff_seconds=settings.retry_backoff)
        self.create_limiter = ratelimit.RateLimiter(limit=settings.create_per_minute)
        self.hint_limiter = ratelimit.RateLimiter(limit=settings.hint_per_minute)
        self.computer_move_limiter = ratelimit.RateLimiter(limit=settings.computer_move_per_minute)
        self.endgame_limiter = ratelimit.RateLimiter(limit=settings.endgames.play_per_minute)  # P2 U6
        self.colour_chooser = colour_chooser
        self.move_chooser = move_chooser if move_chooser is not None else random.SystemRandom()
        # P2 U3: in-memory join-request state (reset by a restart, by design).
        self.join_limiter = ratelimit.RateLimiter(limit=settings.join_requests_per_minute)
        self.player_limiter = ratelimit.RateLimiter(limit=settings.player_per_minute)
        if db.backend == "postgresql":
            for name in ("create", "hint", "computer_move", "endgame", "join", "player"):
                local = getattr(self, name + "_limiter")
                setattr(self, name + "_limiter", ratelimit.SharedRateLimiter(db, name, local.limit))
        self.request_addresses = rooms.RequestAddressBook(memory=settings.decline_memory,
                                                          limit=settings.address_book_cap)
        self.trusted_proxies = tuple(trusted_proxies)
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
        self.hub = LiveHub(snapshot_source=self.snapshot_source, identify=self.identify,
                           mark_seen=self.mark_seen, clock=clock, receive_timeout=receive_timeout)
        self.coordination = Coordination(db, clock)
        self.hub.coordination = self.coordination
        self.vapid = vapid if vapid is not None else vapid_keys.disabled("not configured")
        self.push_hosts = tuple(push_hosts)
        self.notifier = notifications.Notifier(db, self.vapid, sender=push_sender, clock=clock)
        self.outbox = outbox.Outbox(db, self.vapid,
                                  push_sender or notifications.WebPushSender(timeout=3, ttl=300),
                                  clock, self.presence_of)
        self.serverless = os.environ.get("VERCEL") == "1"

    # notifications (U5) ------------------------------------------------------

    def presence_of(self, code: str, slot: str) -> notifications.Presence:
        """Read the seat's presence and freshness now, in the request handler (BR1.3)."""
        return notifications.Presence(connected=slot in self.hub.connected_slots(code),
                                      fresh_visible=self.hub.is_fresh_visible(code, slot, self.clock()))

    def schedule_alert(self, background: BackgroundTasks, event: notifications.AlertEvent | None) -> None:
        """Queue the alert to run after the response is sent; presence is captured here."""
        if event is None:
            return
        with self.db.transaction() as conn:
            outbox.enqueue(conn, event, self.clock())
        background.add_task(self.dispatch_alert, event, self.presence_of(event.room_code, event.target_slot))

    async def dispatch_alert(self, event: notifications.AlertEvent, presence: notifications.Presence) -> None:
        """Background task: claim and send in a worker thread; never raises."""
        try:
            await asyncio.to_thread(self.outbox.dispatch, event)
        except Exception:  # dispatch_safely logs its own failures; this guards the thread hand-off
            logger.exception("Alert %s for room %s could not be scheduled", event.event_key, event.room_code)

    def lock(self, code: str) -> asyncio.Lock:
        """Return the room's lock; it lives as long as someone holds or awaits it."""
        lock = self._locks.get(code)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[code] = lock
        return lock

    # snapshots ---------------------------------------------------------------

    def _snapshot_from(self, conn: sqlite3.Connection, code: str) -> SnapshotFor:
        room = rooms.get_room(conn, code)
        seats = rooms.get_seats(conn, code)
        game = games.current_game(conn, code)
        view = games.GameView(game, games.load_moves(conn, game.game_id))
        now, connected = self.clock(), self.hub.connected_slots(code)
        presence = {slot: rooms.seat_presence(seats.get(slot), slot in connected, now, self.gameplay.abandon_after)
                    for slot in rooms.SLOTS}
        join_request = rooms.join_request_view(rooms.visible_request(conn, code, now), now)
        computer_view = self.computer_view(code, room, game) if room.mode == rooms.MODE_COMPUTER else None
        stand_in = room.mode == rooms.MODE_COMPUTER and rooms.is_stand_in(conn, code)
        room_view = games.RoomView(code, {"A": room.wins_a, "B": room.wins_b, "draws": room.draws},
                                   presence, rooms.rematch_state(room, presence),
                                   mode=room.mode, computer_level=room.computer_level, join_request=join_request,
                                   computer=computer_view, stand_in=stand_in)
        cache: dict[str | None, dict] = {}
        nicknames = players.names(conn, code)

        def snapshot_for(slot: str | None) -> dict:
            if slot not in cache:
                cache[slot] = view.snapshot(room_view, slot)
                for key, seat_view in cache[slot]["seats"].items():
                    seat_view["nickname"] = nicknames.get(key, "")
            return cache[slot]

        return snapshot_for

    def computer_view(self, code: str, room: rooms.Room, game: games.Game, message: str | None = None) -> dict:
        """BR7.1: the snapshot's ``computer`` field; a reply only shows while its game is playing."""
        flight = self.coordinator.reply_for(code, game.game_id) if game.status == games.PLAYING else None
        return computer.computer_state(room.computer_level, self.engine.status(), flight, message)

    def snapshot_source(self, code: str) -> SnapshotFor:
        """Load the room once and return a per-viewer snapshot builder (used by the hub)."""
        with self.db.read() as conn:
            return self._snapshot_from(conn, code)

    def read_snapshot(self, code: str, token: str | None) -> dict:
        """Return the snapshot for whoever holds ``token`` (a watcher when it matches no seat)."""
        with self.db.read() as conn:
            rooms.get_room(conn, code)
            seat = rooms.find_seat(conn, code, token)
            return self._snapshot_from(conn, code)(seat.slot if seat else None)

    def slot_snapshot(self, code: str, slot: str | None) -> dict:
        """Return the snapshot as seen from one slot."""
        return self.snapshot_source(code)(slot)

    async def lapse_on_read(self, code: str) -> None:
        """BR2.4: before a state read, lapse the room's expired pending request under the lock and broadcast."""
        with self.db.read() as conn:
            if not rooms.has_expired_pending(conn, code, self.clock()):
                return
        lapsed = await self.mutate(code, lambda conn, now: rooms.pending_request(conn, code, now).lapsed)
        if lapsed:
            await self.hub.broadcast(code)

    # hub callbacks -----------------------------------------------------------

    def identify(self, code: str, token: str | None) -> tuple[str, str] | None:
        """Resolve a socket's hello token to (slot, token_hash), or None for a watcher."""
        with self.db.read() as conn:
            seat = rooms.find_seat(conn, code, token)
        return (seat.slot, seat.token_hash) if seat else None

    def mark_seen(self, code: str, slot: str) -> None:
        """Record that the seat is present now."""
        with self.db.transaction() as conn:
            rooms.touch_seat(conn, code, slot, self.clock(), force=True)

    # mutations ---------------------------------------------------------------

    def _attach_snapshot(self, code: str, token: str | None, error: DomainError) -> None:
        try:
            error.extra["snapshot"] = self.read_snapshot(code, token)
        except (DomainError, sqlite3.Error):
            logger.exception("Could not attach the latest snapshot for room %s", code)

    async def read_move_check(self, code: str, token: str, version: int) -> tuple[list[str], int]:
        """U4 BR2.1: authorise the seat and run U1's pre-legality checks under the room lock.

        Read-only (no write transaction), and the lock is held only long enough
        to copy the stored moves (UCI) and the version; the caller replays and
        analyses outside it. A 409 carries the latest snapshot, as for a move.
        """
        async with self.lock(code):
            try:
                with self.db.read() as conn:
                    seat = rooms.authorize_seat(conn, code, token)
                    pass_along = rooms.get_room(conn, code).mode == rooms.MODE_PASS_ALONG
                    game = games.current_game(conn, code)
                    moves = [stored.uci for stored in games.load_moves(conn, game.game_id)]
                    games.require_move_turn(game, seat.slot, version, len(moves), pass_along)
                    return moves, game.version
            except DomainError as error:
                if error.status == 409:
                    self._attach_snapshot(code, token, error)
                raise
            except sqlite3.Error:
                logger.exception("Database error in room %s", code)
                raise HTTPException(500, SERVER_ERROR) from None

    async def mutate(self, code: str | None, action: Callable[[sqlite3.Connection, float], T],
                     viewer_token: str | None = None) -> T:
        """Run ``action`` under the room lock in one transaction; map refusals and DB errors."""
        lock = self.lock(code) if code else asyncio.Lock()
        async with lock:
            try:
                with self.db.transaction() as conn:
                    if code:
                        self.db.lock_room(conn, code)
                    result = action(conn, self.clock())
                    if isinstance(result, tuple):
                        for item in result:
                            if isinstance(item, notifications.AlertEvent):
                                outbox.enqueue(conn, item, self.clock())
                    if code:
                        self.db.notify_room(conn, code)
                    return result
            except DomainError as error:
                if error.status == 409 and code:
                    self._attach_snapshot(code, viewer_token, error)
                raise
            except sqlite3.Error:
                logger.exception("Database error in room %s", code or "(new room)")
                raise HTTPException(500, SERVER_ERROR) from None

    # P2 U4: the computer's reply (BR5.1-BR5.6) ------------------------------------

    async def request_reply(self, code: str, respect_backoff: bool = False) -> ReplyAsk:
        """Vercel finishes bounded engine work within the invoking request.

        The lease survives instance interruption; another request can retry after
        expiry. apply_reply revalidates game/version under the SQL room lock.
        """
        if not self.serverless:
            return self.ask_reply(code, respect_backoff)
        with self.db.transaction() as conn:
            self.db.lock_room(conn, code)
            room = rooms.get_room(conn, code)
            game = games.current_game(conn, code)
            if room.mode != rooms.MODE_COMPUTER or game.status != games.PLAYING:
                return ReplyAsk()
            board = games.replay_board(games.load_moves(conn, game.game_id))
            if game.slot_of(board.turn) != "B" or not self.engine.available:
                return ReplyAsk()
            key = f"engine:{code}:{game.game_id}:{game.version}"
            owner = work.claim(conn, key, self.clock(), 60)
        if owner is None:
            return ReplyAsk()
        try:
            level = computer.reply_settings(room.computer_level, self.gameplay.levels)
            try:
                ticket = self.engine.submit(board, level.skill, level.think, depth=level.depth)
            except engine_module.EngineBusy as busy:
                return ReplyAsk(message=busy.reason)
            except engine_module.EngineUnavailable:
                return ReplyAsk()
            flight = computer.ReplyInFlight(game.game_id, game.version, ticket.request_id, "thinking",
                                            random_move_chance=level.random_move_chance)
            self.coordinator.set_reply(code, flight)
            try:
                try:
                    await asyncio.wait_for(self._complete_reply(code, flight, ticket), 30)
                except TimeoutError:
                    self.coordinator.set_backoff(code)
                    return ReplyAsk(message="The computer is busy, try again in a moment")
            finally:
                self.coordinator.clear_reply(code, flight.request_id)
            return ReplyAsk(asked=True)
        finally:
            with self.db.transaction() as conn:
                if self.coordinator.in_backoff(code):
                    conn.execute("UPDATE work_claims SET expires_at = ? WHERE work_key = ? AND owner = ?",
                                 (self.clock() + self.gameplay.retry_backoff, key, owner))
                else:
                    work.release(conn, key, owner)

    def ask_reply(self, code: str, respect_backoff: bool = False) -> ReplyAsk:
        """BR5.1/BR5.4: enqueue the computer's reply when it is due; never raises.

        Called after the commit, with no lock held. Due means: a computer room,
        the game playing, seat B to move, no reply in flight for this game, the
        engine available and (for resume) no backoff in force. The enqueue is
        synchronous; a busy refusal comes back as the message to show.
        """
        try:
            with self.db.read() as conn:
                room = rooms.get_room(conn, code)
                if room.mode != rooms.MODE_COMPUTER:
                    return ReplyAsk()
                game = games.current_game(conn, code)
                board = games.replay_board(games.load_moves(conn, game.game_id))
        except (DomainError, sqlite3.Error):
            logger.exception("Could not read room %s to ask for the computer's reply", code)
            return ReplyAsk()
        if game.status != games.PLAYING or game.slot_of(board.turn) != "B":
            return ReplyAsk()
        if self.coordinator.reply_for(code, game.game_id) is not None or not self.engine.available:
            return ReplyAsk()
        if respect_backoff and self.coordinator.in_backoff(code):
            return ReplyAsk()
        return self._submit_reply(code, room, game, board)

    def _submit_reply(self, code: str, room: rooms.Room, game: games.Game, board: chess.Board) -> ReplyAsk:
        level = computer.reply_settings(room.computer_level, self.gameplay.levels)
        request_ids: list[int] = []

        def on_progress(state: str, position: int | None) -> None:
            if request_ids and self.coordinator.progress(code, request_ids[0], state, position):
                self.coordinator.spawn(self.hub.send_event(
                    code, {"type": "computer", "state": state, "queuePosition": position}))

        try:
            ticket = self.engine.submit(board, level.skill, level.think, on_progress, depth=level.depth)
        except engine_module.EngineBusy as busy:
            logger.info("The computer's reply in room %s was refused: the engine queue is full", code)
            return ReplyAsk(message=busy.reason)
        except engine_module.EngineUnavailable:
            return ReplyAsk()
        request_ids.append(ticket.request_id)
        flight = computer.ReplyInFlight(game.game_id, game.version, ticket.request_id, ticket.state,
                                        ticket.queue_position, random_move_chance=level.random_move_chance)
        self.coordinator.run_reply(code, flight, lambda: self._complete_reply(code, flight, ticket))
        return ReplyAsk(asked=True)

    async def _complete_reply(self, code: str, flight: computer.ReplyInFlight, ticket: engine_module.Ticket) -> None:
        """BR5.2/BR5.6: apply the move to the unchanged game, or discard it; on failure set the backoff."""
        try:
            move = await ticket.result()
        except engine_module.EngineFailure as failure:
            logger.warning("The computer's reply in room %s failed: %s", code, failure.reason)
            if self._is_current_game(code, flight.game_id):  # a stale game's failure must not hold up the new game
                self.coordinator.set_backoff(code)
            self.coordinator.clear_reply(code, flight.request_id)
            await self.hub.broadcast(code)
            return
        applied = False
        async with self.lock(code):
            try:
                with self.db.transaction() as conn:
                    self.db.lock_room(conn, code)
                    applied = self.apply_reply(conn, self.clock(), code, flight, move)
                    if applied:
                        self.db.notify_room(conn, code)
            except (DomainError, sqlite3.Error):
                logger.exception("The computer's reply in room %s could not be applied", code)
        if not applied:
            logger.info("Discarded a stale computer reply in room %s", code)
        self.coordinator.clear_reply(code, flight.request_id)
        await self.hub.broadcast(code)

    def _is_current_game(self, code: str, game_id: int) -> bool:
        """True when ``game_id`` is still the room's current game (False when it cannot be read)."""
        try:
            with self.db.read() as conn:
                return games.current_game(conn, code).game_id == game_id
        except (DomainError, sqlite3.Error):
            logger.exception("Could not read room %s after a failed computer reply", code)
            return False

    def apply_reply(self, conn: sqlite3.Connection, now: float, code: str, flight: computer.ReplyInFlight,
                    move: chess.Move) -> bool:
        """Inside the room lock and one transaction: apply ``move`` as seat B only to the unchanged game.

        The level's random-move chance (``flight.random_move_chance``) may swap the
        engine's move for a random other legal move first (``self.move_chooser``).
        """
        if rooms.get_room(conn, code).mode != rooms.MODE_COMPUTER:
            return False  # a friend took the computer's seat meanwhile
        game = games.current_game(conn, code)
        if game.game_id != flight.game_id or game.version != flight.version or game.status != games.PLAYING:
            return False
        board = games.replay_board(games.load_moves(conn, game.game_id))
        if game.slot_of(board.turn) != "B" or move not in board.legal_moves:
            return False
        move = computer.maybe_randomise(board, move, flight.random_move_chance, self.move_chooser)
        game = games.apply_move(conn, game, "B", move.uci(), game.version, now, computer=True)
        _finish_score(conn, code, game)
        rooms.touch_room(conn, code, now)
        return True

    # P2 U4: hints (BR6.1) --------------------------------------------------------

    async def read_hint_position(self, code: str, token: str, version: int) -> tuple[chess.Board, int, int]:
        """Check a hint request under the room lock (read-only) and return (board, version, game id)."""
        async with self.lock(code):
            try:
                with self.db.read() as conn:
                    seat = rooms.authorize_seat(conn, code, token)
                    if rooms.get_room(conn, code).mode != rooms.MODE_COMPUTER:
                        raise DomainError(409, HINT_ONLY)
                    game = games.current_game(conn, code)
                    games.require_playing(game)
                    if version != game.version:
                        raise DomainError(409, games.STALE_VERSION)
                    board = games.replay_board(games.load_moves(conn, game.game_id))
            except DomainError as error:
                if error.status == 409:
                    self._attach_snapshot(code, token, error)
                raise
            except sqlite3.Error:
                logger.exception("Database error in room %s", code)
                raise HTTPException(500, SERVER_ERROR) from None
        if game.slot_of(board.turn) != seat.slot:
            raise DomainError(409, COMPUTERS_TURN)
        if not self.engine.available:
            raise DomainError(503, self.engine.reason or ENGINE_DOWN)
        return board, game.version, game.game_id


class ReplyAsk:
    """What ``ask_reply`` did: whether a reply was asked for, and a busy message to show (or None)."""

    __slots__ = ("asked", "message")

    def __init__(self, asked: bool = False, message: str | None = None) -> None:
        self.asked = asked
        self.message = message


def services(request: Request) -> Services:
    """Return the app's services (available once the lifespan has started)."""
    return request.app.state.services


# --- use cases (run inside one transaction) ---------------------------------

def _finish_score(conn: sqlite3.Connection, code: str, game: games.Game) -> None:
    if game.status == games.FINISHED and game.result:
        rooms.record_result(conn, code, game.result, game.white_slot, counted=game.counted)


def _is_pass_along(conn: sqlite3.Connection, code: str) -> bool:
    return rooms.get_room(conn, code).mode == rooms.MODE_PASS_ALONG


def _after_action(conn: sqlite3.Connection, code: str, slot: str, now: float) -> None:
    rooms.touch_room(conn, code, now)
    rooms.touch_seat(conn, code, slot, now)


def _limit(svc: Services, limiter: ratelimit.RateLimiter, request: Request) -> None:
    """BR6.2: one sliding 60 s window per route and client address; 429 (Retry-After 60) past the limit."""
    address = ratelimit.client_address(request, svc.trusted_proxies)
    if not limiter.allow(address, svc.clock()):
        raise DomainError(429, TOO_MANY, error="too_many")


def _snapshot_with(svc: Services, code: str, slot: str | None, message: str | None = None) -> dict:
    """The slot's snapshot; a busy refusal's message goes into its ``computer`` field (this answer only)."""
    snapshot = dict(svc.slot_snapshot(code, slot))
    if message and snapshot.get("computer"):
        snapshot["computer"] = {**snapshot["computer"], "message": message}
    return snapshot


def _require_computer_room(conn: sqlite3.Connection, code: str, message: str) -> rooms.Room:
    room = rooms.get_room(conn, code)
    if room.mode != rooms.MODE_COMPUTER:
        raise DomainError(409, message)
    return room


def _refuse_in_computer_room(conn: sqlite3.Connection, code: str) -> rooms.Room:
    """BR3.6: claims make no sense against the computer."""
    room = rooms.get_room(conn, code)
    if room.mode == rooms.MODE_COMPUTER:
        raise DomainError(409, NOT_FOR_COMPUTER)
    return room


def _valid_colour(colour: str | None, allow_none: bool) -> str | None:
    if colour is None and allow_none:
        return None
    if colour not in COLOUR_CHOICES:
        raise DomainError(400, UNKNOWN_COLOUR)
    return colour


class ClientGone(Exception):
    """The client went away while its engine request waited (the request was cancelled)."""


class EngineWaitTimeout(Exception):
    """The engine request was still unanswered at the caller's wait limit (the request was cancelled)."""


async def _await_engine(request: Request, ticket: engine_module.Ticket, limit: float | None = None) -> chess.Move:
    """Wait for an engine request, shared by hints and endgame replies (P2 U6, BR3.3).

    Every ENGINE_POLL_SECONDS it checks the client is still connected. When the
    client goes away (``ClientGone``) or ``limit`` seconds pass
    (``EngineWaitTimeout``), the request is cancelled: a queued one leaves the
    queue, a running search's result is dropped. ``EngineFailure`` passes
    through. The callers choose their own wording.
    """
    loop = asyncio.get_running_loop()
    deadline = None if limit is None else loop.time() + limit
    result = asyncio.ensure_future(ticket.result())
    try:
        while True:
            timeout = ENGINE_POLL_SECONDS if deadline is None else max(0.0, min(ENGINE_POLL_SECONDS, deadline - loop.time()))
            done, _pending = await asyncio.wait({result}, timeout=timeout)
            if done:
                return result.result()
            if deadline is not None and loop.time() >= deadline:
                raise EngineWaitTimeout()
            if await request.is_disconnected():
                raise ClientGone()
    finally:
        if not result.done():
            result.cancel()  # Ticket.result cancels the engine request
            await asyncio.gather(result, return_exceptions=True)


async def _await_hint(request: Request, ticket: engine_module.Ticket) -> chess.Move:
    """Wait for the hint; when the client goes away, cancel the request (or drop a running search's result)."""
    try:
        return await _await_engine(request, ticket)
    except ClientGone:
        raise DomainError(409, HINT_CANCELLED) from None


def _engine_for(settings: gameplay_module.Gameplay) -> engine_module.Engine:
    """The production Engine with gameplay.yaml's queue cap, overrun grace and restart count."""
    return engine_module.Engine(max_queue=settings.queue_cap, grace=settings.overrun_grace, restarts=settings.restarts)


def _judge_move(moves: list[str], uci: str, budget_ms: float = analysis.DEFAULT_BUDGET_MS) -> dict[str, object]:
    """U4: replay the copied moves, check legality (400) and analyse the candidate (runs in a worker thread)."""
    board = chess.Board()
    for stored in moves:
        board.push_uci(stored)
    move = games.parse_legal_move(board, uci)
    warning = analysis.analyse(board, move, budget_ms=budget_ms)
    return {"warning": warning.to_dict() if warning else None, "san": board.san(move)}


# --- app factory ------------------------------------------------------------

def _resolve_path(setting: PathSetting, default: Callable[[], Path]) -> Path:
    if setting is None:
        return default()
    if callable(setting):
        return Path(setting())
    return Path(setting)


async def _prepare_stockfish(app: FastAPI, engine_dir: Path) -> None:
    try:
        app.state.stockfish = await asyncio.to_thread(stockfish_install.ensure_stockfish, engine_dir, os.environ)
    except Exception:
        logger.exception("Stockfish preparation failed; running without an engine")


async def _prepare_engine(app: FastAPI, engine_dir: Path, engine: engine_module.Engine) -> None:
    """P2 U4 BR1.5: find Stockfish (existing ``ensure_stockfish``), then open the one engine process."""
    await _prepare_stockfish(app, engine_dir)
    found = getattr(app.state, "stockfish", None)
    if found is None or not found.available:
        engine.mark_missing()
        logger.info("Play the computer is unavailable: no chess engine is installed")
        return
    await engine.start(found.path)


async def _load_lessons(store: lessons.LessonStore) -> None:
    """W1: scan the lessons folder at startup (problems are logged by the loader)."""
    try:
        await asyncio.to_thread(store.catalog)
    except Exception:
        logger.exception("Loading the lessons failed at startup; they will be retried on the next request")


async def _load_puzzles(store: puzzles.PuzzleStore) -> None:
    """W3: load the puzzle set once at startup (skipped puzzles are logged by the loader)."""
    try:
        await asyncio.to_thread(store.catalog)
    except Exception:
        logger.exception("Loading the puzzles failed at startup; they will be retried on the next request")


async def _load_endgames(store: endgames.EndgameStore) -> None:
    """P2 U6 BR1.1: load the endgame positions once at startup (skipped positions are logged by the loader)."""
    try:
        await asyncio.to_thread(store.catalog)
    except Exception:
        logger.exception("Loading the endgame positions failed at startup; they will be retried on the next request")


def create_app(*, db_path: PathSetting = None, clock: Callable[[], float] = time.time,
               engine_dir: PathSetting = None, receive_timeout: float = RECEIVE_TIMEOUT,
               origin: str | None = None, cleanup_hooks: Sequence[housekeeping.CleanupHook] = (),
               lessons_dir: PathSetting = None, vapid: vapid_keys.VapidConfig | None = None,
               push_sender: notifications.Sender | None = None,
               puzzles_dir: PathSetting = None, engine_factory: EngineFactory | None = None,
               colour_chooser: ColourChooser = secrets.choice,
               gameplay: gameplay_module.Gameplay | None = None,
               move_chooser: computer.MoveChooser | None = None,
               endgames_dir: PathSetting = None,
               database_url: str | Callable[[], str | None] | None = None) -> FastAPI:
    """Build the JustChess app. Nothing touches the database until the app starts.

    ``database_url`` explicitly selects PostgreSQL (a callable resolves at startup).
    Otherwise an explicit ``db_path`` selects isolated SQLite; with neither,
    DATABASE_URL takes precedence over JUSTCHESS_DB from the environment.

    ``lessons_dir`` is resolved here, once: the argument, else ``JUSTCHESS_LESSONS_DIR``,
    else ``lessons/`` at the project root. ``vapid`` defaults to the keys from the
    environment, loaded (and logged once) when the app starts. P2 U4:
    ``engine_factory`` builds the Engine at start-up (tests pass one with a fake
    UCI opener) and ``colour_chooser`` resolves a random colour.

    Gameplay settings: ``gameplay`` (tests), else ``gameplay.yaml`` (or
    ``JUSTCHESS_GAMEPLAY_FILE``) loaded here, once; a bad file raises
    ``GameplayError`` naming the key, so the app does not start with it.
    ``move_chooser`` is the random source of the levels' random moves
    (default ``random.SystemRandom()``). The page's keys are put in the app shell.
    P2 U6: ``endgames_dir`` is the endgame folder (default ``endgames/`` at the project root).
    """
    settings = gameplay if gameplay is not None else gameplay_module.load_gameplay()
    lesson_store = lessons.LessonStore(_resolve_path(lessons_dir, lambda: lessons.default_lessons_dir(ROOT)), clock)
    puzzle_store = puzzles.PuzzleStore(_resolve_path(puzzles_dir, lambda: puzzles.default_puzzles_dir(ROOT)))
    endgame_store = endgames.EndgameStore(_resolve_path(endgames_dir, lambda: endgames.default_endgames_dir(ROOT)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        url = database_url() if callable(database_url) else database_url
        path = _resolve_path(db_path, lambda: None) if db_path is not None else None
        db = prepare_configured_database(path, database_url=url)
        keys = vapid if vapid is not None else vapid_keys.load_vapid(os.environ, ROOT)
        chess_engine = engine_factory() if engine_factory is not None else _engine_for(settings)
        svc = Services(db, clock, receive_timeout, vapid=keys, push_sender=push_sender,
                       push_hosts=notifications.allowed_hosts(os.environ),
                       trusted_proxies=ratelimit.trusted_proxies_from(os.environ),
                       engine=chess_engine, colour_chooser=colour_chooser, gameplay=settings,
                       move_chooser=move_chooser)
        app.state.services = svc
        app.state.stockfish = None
        await _load_lessons(lesson_store)
        await _load_puzzles(puzzle_store)
        await _load_endgames(endgame_store)
        engine_folder = _resolve_path(engine_dir, lambda: DEFAULT_ENGINE_DIR)
        if svc.serverless:
            # A cold start must finish preparation before accepting engine requests.
            # Vercel may suspend between requests; no autonomous housekeeping loop.
            await _prepare_engine(app, engine_folder, chess_engine)
            tasks = []
        else:
            tasks = [asyncio.create_task(_prepare_engine(app, engine_folder, chess_engine)),
                     asyncio.create_task(housekeeping.run_forever(
                         db, clock, (notifications.delete_room_data, *cleanup_hooks),
                         retention=settings.idle_room_retention))]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await svc.coordinator.cancel_all()  # BR1.5: reply tasks first, then the engine process
            await chess_engine.stop()
            db.close()  # idle PostgreSQL connections

    app = FastAPI(title="JustChess", lifespan=lifespan)

    @app.get("/api/cron/maintenance")
    async def maintenance(request: Request):
        secret = os.environ.get("CRON_SECRET", "")
        supplied = request.headers.get("authorization", "")
        if not secret or not secrets.compare_digest(supplied, "Bearer " + secret):
            raise HTTPException(401, "Unauthorized")
        svc = services(request)
        drained = await asyncio.to_thread(svc.outbox.drain)
        await asyncio.to_thread(housekeeping.run_lapse, svc.db, svc.clock())
        # Bounded cleanup instead of traversing an unbounded room backlog in cron.
        deleted = await asyncio.to_thread(housekeeping.run_cleanup, svc.db, svc.clock(),
                                         (notifications.delete_room_data, *cleanup_hooks),
                                         settings.idle_room_retention, 20)
        with svc.db.transaction() as conn:
            conn.execute("DELETE FROM live_presence WHERE heard_at < ?", (svc.clock() - 60,))
            conn.execute("DELETE FROM work_claims WHERE expires_at < ?", (svc.clock() - 3600,))
            conn.execute("DELETE FROM rate_windows WHERE started_at < ?", (svc.clock() - 3600,))
            conn.execute("DELETE FROM room_declines WHERE declined_at < ?", (svc.clock() - settings.decline_memory,))
        return {"processed": drained, "deleted": deleted}
    app.state.gameplay = settings
    app.state.lessons = lesson_store
    app.state.puzzles = puzzle_store
    app.state.endgames = endgame_store
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES,
                       overrides={summaries.PATH: summaries.MAX_BODY_BYTES})
    app.add_middleware(OriginGuardMiddleware, configured_origin=origin or os.environ.get("JUSTCHESS_ORIGIN"))
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=str(ROOT / "templates"))

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, error: DomainError) -> JSONResponse:
        """Answer a business refusal with its status, message and any attached snapshot."""
        headers = {"Retry-After": RETRY_AFTER_SECONDS} if error.status == 429 else None
        return JSONResponse({"detail": error.message, **error.extra}, status_code=error.status, headers=headers)

    _add_page_routes(app, templates, settings)
    _add_lesson_routes(app, lesson_store)
    _add_puzzle_routes(app, puzzle_store)
    _add_endgame_routes(app, endgame_store, settings)
    _add_room_routes(app)
    _add_player_routes(app)
    _add_join_request_routes(app)
    _add_game_routes(app)
    _add_push_routes(app)
    _add_socket_route(app)
    return app


def _add_page_routes(app: FastAPI, templates: Jinja2Templates, settings: gameplay_module.Gameplay) -> None:
    client_gameplay = settings.client_json()

    def page(request: Request):
        """The app shell, with gameplay.yaml's page settings (static/js/gameplay.js reads them)."""
        return templates.TemplateResponse(request, "index.html", {"gameplay": client_gameplay})

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        """Serve the page."""
        return page(request)

    @app.get("/r/{code}", response_class=HTMLResponse)
    def invite(request: Request, code: str):
        """Serve the page for an invite link; the page then joins the room."""
        return page(request)

    @app.get("/learn", response_class=HTMLResponse)
    def learn(request: Request):
        """Serve the page for the opening trainer (U6); the page lists the lessons."""
        return page(request)

    @app.get("/learn/{lesson_id}", response_class=HTMLResponse)
    def learn_lesson(request: Request, lesson_id: str):
        """Serve the page for one lesson; the page checks the id and loads it."""
        return page(request)

    @app.get("/learn/tactics/{theme}", response_class=HTMLResponse)
    def learn_tactics(request: Request, theme: str):
        """P2 U5 W3: serve the page for the puzzle screen; the page checks the theme."""
        return page(request)

    @app.get("/learn/endgames/{position_id}", response_class=HTMLResponse)
    def learn_endgame(request: Request, position_id: str):
        """P2 U6 W2: serve the page for the endgame screen; the page checks the position id."""
        return page(request)

    @app.get("/api/engine")
    def engine(request: Request):
        """Report whether the engine is available (P2 U4: its process is running), without exposing its path.

        ``path_source`` and ``version`` describe the binary that was found (or
        None); ``reason`` says why the computer is unavailable, else None.
        """
        result = getattr(request.app.state, "stockfish", None)
        svc = getattr(request.app.state, "services", None)
        status = svc.engine.status() if svc is not None else {"available": False, "reason": engine_module.STARTING}
        found = result is not None and result.available
        return {"available": bool(status["available"]), "path_source": result.source if found else None,
                "version": result.version if found else None, "reason": status["reason"]}

    @app.get("/api/health")
    async def health(request: Request):
        """Monitoring signal (Observability Setup): 200 when the database answers and the engine is available.

        Read-only: one ``SELECT 1``, no writes, no secrets, no error details;
        503 with the failing part named (``database`` or ``engine``) otherwise.
        """
        svc = getattr(request.app.state, "services", None)
        database_ok = False
        if svc is not None:
            def ping() -> bool:
                with svc.db.read() as conn:
                    return conn.execute("SELECT 1").fetchone()[0] == 1
            try:
                database_ok = await asyncio.to_thread(ping)
            except Exception:  # sanitized: never echo driver errors or connection details
                logger.warning("Health check: the database did not answer")
        engine_ok = bool(svc is not None and svc.engine.status()["available"])
        body = {"status": "ok" if database_ok and engine_ok else "degraded",
                "database": "ok" if database_ok else "down", "engine": "available" if engine_ok else "unavailable"}
        return JSONResponse(body, status_code=200 if database_ok and engine_ok else 503,
                            headers={"Cache-Control": "no-store"})


def _add_lesson_routes(app: FastAPI, store: lessons.LessonStore) -> None:
    def current_catalog() -> lessons.LessonCatalog:
        try:
            return store.catalog()
        except Exception:
            logger.exception("Could not load the lessons from %s", store.directory)
            raise HTTPException(500, SERVER_ERROR) from None

    @app.get("/api/lessons")
    def list_lessons(kind: str | None = None):
        """BR2.1: the valid lessons (id, name, kind, aliases, eco, side, moves), sorted by name.

        P2 U5 BR1.2: ``?kind=`` lists one kind; an unknown kind is 400.
        """
        if kind is not None and not lessons.is_kind(kind):
            raise HTTPException(400, UNKNOWN_KIND)
        return current_catalog().summaries(kind)

    @app.get("/api/lessons/{lesson_id}")
    def lesson_detail(lesson_id: str):
        """BR2.2: one lesson with its objectives and steps; a malformed or unknown id is 404."""
        if not lessons.LESSON_ID.fullmatch(lesson_id):
            raise HTTPException(404, LESSON_NOT_FOUND)
        lesson = current_catalog().get(lesson_id)
        if lesson is None:
            raise HTTPException(404, LESSON_NOT_FOUND)
        return lesson

    @app.post("/api/position/move")
    def position_move(body: PositionMoveRequest):
        """BR2.3: stateless free-play move. 400 "Illegal move" or "Invalid position" on bad input."""
        try:
            return lessons.position_move(body.fen, body.uci)
        except lessons.PositionError as error:
            raise HTTPException(400, str(error)) from None


def _add_puzzle_routes(app: FastAPI, store: puzzles.PuzzleStore) -> None:
    def current_catalog() -> puzzles.PuzzleCatalog:
        try:
            return store.catalog()
        except Exception:
            logger.exception("Could not load the puzzles from %s", store.directory)
            raise HTTPException(500, SERVER_ERROR) from None

    def theme_puzzles(theme: str) -> tuple[dict, ...]:
        found = current_catalog().puzzles(theme)
        if found is None:
            raise HTTPException(404, THEME_NOT_FOUND)
        return found

    def puzzle_of(theme: str, puzzle_id: str) -> dict:
        theme_puzzles(theme)
        puzzle = current_catalog().get(theme, puzzle_id)
        if puzzle is None:
            raise HTTPException(404, PUZZLE_NOT_FOUND)
        return puzzle

    @app.get("/api/puzzles")
    def list_themes():
        """W3: ``[{theme, label, count}]``; empty when puzzles are not installed."""
        return current_catalog().theme_list()

    @app.get("/api/puzzles/{theme}")
    def list_puzzles(theme: str):
        """W3: the theme's puzzles as ``[{id, rating}]``, easier first; 404 for an unknown theme."""
        return [{"id": puzzle["id"], "rating": puzzle["rating"]} for puzzle in theme_puzzles(theme)]

    @app.get("/api/puzzles/{theme}/{puzzle_id}")
    def puzzle_detail(theme: str, puzzle_id: str):
        """W3: one puzzle without its solution."""
        return puzzles.public_detail(puzzle_of(theme, puzzle_id))

    @app.post("/api/puzzles/{theme}/{puzzle_id}/check")
    def puzzle_check(theme: str, puzzle_id: str, body: PuzzleCheckRequest):
        """BR2.4: correct (with the reply), solved, or wrong (with no solution in the answer)."""
        try:
            return puzzles.check_move(puzzle_of(theme, puzzle_id), body.ply, body.uci)
        except puzzles.PuzzleError as error:
            raise HTTPException(400, str(error)) from None

    @app.post("/api/puzzles/{theme}/{puzzle_id}/hint")
    def puzzle_hint(theme: str, puzzle_id: str, body: PuzzleHintRequest):
        """BR2.4: the piece to move, the move, or the remaining line."""
        try:
            return puzzles.hint(puzzle_of(theme, puzzle_id), body.ply, body.level)
        except puzzles.PuzzleError as error:
            raise HTTPException(400, str(error)) from None


def _engine_status(request: Request) -> dict[str, object]:
    """The engine's ``{available, reason}``, also before the lifespan has built the services."""
    svc = getattr(request.app.state, "services", None)
    return svc.engine.status() if svc is not None else {"available": False, "reason": engine_module.STARTING}


def _side(colour: chess.Color) -> str:
    return "white" if colour == chess.WHITE else "black"


def _endgame_detail(catalog: endgames.EndgameCatalog, position: endgames.EndgamePosition, hold_moves: int) -> dict:
    """BR3.1: one position, plus what the page needs to draw it (side, legal moves, check, next position)."""
    board = chess.Board(position.fen)
    index, count = catalog.place_of(position)
    detail = {"id": position.id, "category": position.category,
              "categoryLabel": endgames.CATEGORY_LABELS[position.category], "title": position.title,
              "fen": position.fen, "goal": position.goal, "hint": position.hint, "index": index, "count": count,
              "side": _side(board.turn), "legalMoves": sorted(move.uci() for move in board.legal_moves),
              "check": board.is_check(), "next": catalog.next_of(position)}
    if position.goal == "draw":
        detail["holdMoves"] = hold_moves
    return detail


async def _defender_reply(request: Request, svc: Services, board: chess.Board) -> chess.Move:
    """BR2.5/BR3.3: the defender's move from the shared Engine queue, or a 503 (409 when the client left).

    Refused as busy once ``refusal_queue`` requests wait (so live games keep
    their place) or the queue is full; a wait longer than ``wait_limit`` is
    cancelled and answered busy. The board is the one replayed from the start
    FEN; the returned move is checked to be legal on it.
    """
    settings = svc.gameplay.endgames
    if not svc.engine.available:
        raise DomainError(503, svc.engine.reason or ENGINE_DOWN)
    if svc.engine.queued_count() >= settings.refusal_queue:
        raise DomainError(503, engine_module.BUSY)
    try:
        ticket = svc.engine.submit(board, settings.defender_skill, settings.defender_think)
    except (engine_module.EngineBusy, engine_module.EngineUnavailable) as refused:
        raise DomainError(503, refused.reason) from None
    try:
        move = await _await_engine(request, ticket, limit=settings.wait_limit)
    except engine_module.EngineFailure as failure:
        logger.warning("An endgame defender reply failed: %s", failure.reason)
        raise DomainError(503, failure.reason) from None
    except EngineWaitTimeout:
        logger.info("An endgame defender reply waited more than %g s and was cancelled", settings.wait_limit)
        raise DomainError(503, engine_module.BUSY) from None
    except ClientGone:
        raise DomainError(409, ENDGAME_CANCELLED) from None
    if move not in board.legal_moves:
        logger.error("The engine's endgame reply was not legal; refusing it")
        raise DomainError(503, engine_module.NO_MOVE)
    return move


def _add_endgame_routes(app: FastAPI, store: endgames.EndgameStore, settings: gameplay_module.Gameplay) -> None:
    """P2 U6: list, get and play endgame positions (BR3.1-BR3.3)."""

    def current_catalog() -> endgames.EndgameCatalog:
        try:
            return store.catalog()
        except Exception:
            logger.exception("Could not load the endgame positions from %s", store.directory)
            raise HTTPException(500, SERVER_ERROR) from None

    def position_of(catalog: endgames.EndgameCatalog, position_id: str) -> endgames.EndgamePosition:
        position = catalog.get(position_id)
        if position is None:
            raise DomainError(404, POSITION_NOT_FOUND)
        return position

    @app.get("/api/endgames")
    def list_endgames(request: Request):
        """BR3.1: ``{installed, available, reason, categories}``; works without the engine."""
        catalog = current_catalog()
        status = _engine_status(request)
        return {"installed": catalog.installed, "available": bool(status["available"]), "reason": status["reason"],
                "categories": catalog.categories()}

    @app.get("/api/endgames/{position_id}")
    def endgame_detail(position_id: str):
        """BR3.1: one position; an unknown id is 404 "No such position"."""
        catalog = current_catalog()
        return _endgame_detail(catalog, position_of(catalog, position_id), settings.endgames.hold_moves)

    @app.post("/api/endgames/{position_id}/play")
    async def endgame_play(request: Request, position_id: str,
                           body: Annotated[EndgamePlayRequest | None, Body()] = None):
        """BR3.2: validate the attempt, add the defender's reply while it is playing, and answer the verdict."""
        svc = services(request)
        _limit(svc, svc.endgame_limiter, request)
        catalog = current_catalog()
        position = position_of(catalog, position_id)
        limits = svc.gameplay.endgames
        moves = body.moves if body is not None else None
        try:
            board = endgames.replay(position, moves, limits.max_plies)
        except endgames.EndgameError as error:
            raise DomainError(400, str(error)) from None
        player = chess.Board(position.fen).turn
        count = endgames.player_moves_in(moves)
        verdict = endgames.judge(board, position.goal, player, count, limits)
        after_player = {"playerFen": board.fen(), "playerCheck": board.is_check()}
        reply = None
        if endgames.needs_defender(board, verdict, player):
            move = await _defender_reply(request, svc, board)
            reply = {"uci": move.uci(), "san": board.san(move)}
            board.push(move)
            verdict = endgames.judge(board, position.goal, player, count, limits)
        playing = verdict.status == endgames.PLAYING
        return {"status": verdict.status, "reason": verdict.reason, "reply": reply, "playerMoves": count,
                "movesLeft": verdict.moves_left, **after_player, "fen": board.fen(), "check": board.is_check(),
                "legalMoves": sorted(m.uci() for m in board.legal_moves) if playing else []}


def _add_player_routes(app: FastAPI) -> None:
    @app.post("/api/player/{action}")
    async def player_action(request: Request, action: str):
        svc = services(request)
        _limit(svc, svc.player_limiter, request)
        if action not in {"create", "restore", "profile", "nickname", "regenerate", "seats"}:
            raise DomainError(404, "Player action not found")
        try:
            body = await request.json()
        except (ValueError, TypeError):
            raise DomainError(400, "Invalid player request") from None
        if not isinstance(body, dict):
            raise DomainError(400, "Invalid player request")
        token = request.headers.get("X-Player-Token")

        def change(conn, now):
            if action == "create":
                return players.create(conn, now)
            if action == "restore":
                return players.restore(conn, body.get("recovery"), now)
            player = players.authenticate(conn, token)
            if action == "nickname":
                name = players.nickname(body.get("nickname"))
                conn.execute("UPDATE players SET nickname = ? WHERE player_id = ?", (name, player["player_id"]))
            if action == "regenerate":
                return {"recovery": players.regenerate(conn, token)}
            if action == "seats":
                code = rooms.normalize_code(body.get("code"))
                players.attach(conn, token, code, body.get("token"))
            return players.profile(conn, token)

        answer = await svc.mutate(None, change)
        if action in {"nickname", "seats"}:
            for seat in answer["seats"]:
                await svc.hub.broadcast(seat["code"])
        return JSONResponse(answer, headers={"Cache-Control": "no-store"})


def _add_room_routes(app: FastAPI) -> None:
    @app.post(summaries.PATH)
    async def room_summaries(request: Request):
        """W4, BR2.1-BR2.3: one summary per distinct (code, token) pair, read-only.

        The tokens are in the body only; they are never logged, and a malformed
        body is answered with the fixed 400 message, never with its contents.
        """
        pairs = summaries.parse_request(await request.body())
        svc = services(request)
        try:
            answers = await asyncio.to_thread(summaries.build_summaries, svc.db, pairs, svc.clock())
        except sqlite3.Error:
            logger.exception("Database error while reading %d room summaries", len(pairs))
            raise HTTPException(500, SERVER_ERROR) from None
        return {"rooms": answers}

    @app.post("/api/rooms", status_code=201)
    async def create_room(request: Request, body: Annotated[CreateRoomRequest | None, Body()] = None):
        """W1: create a room with seat A and game 1; the token is returned once.

        P2 U4 BR3.1: ``{kind: "computer", level, colour}`` creates a computer room instead.
        """
        kind = body.kind if body is not None else None
        if kind == "computer":
            return await _create_computer_room(request, body)
        if kind not in (None, "friend"):
            raise DomainError(400, UNKNOWN_ROOM_KIND)

        def action(conn: sqlite3.Connection, now: float) -> tuple[str, str]:
            room, _seat, token = rooms.create_room(conn, now)
            games.create_first_game(conn, room.code, now)
            return room.code, token

        code, token = await services(request).mutate(None, action)
        logger.info("Created room %s", code)
        return JSONResponse({"code": code, "token": token, "slot": "A", "colour": "white"},
                            status_code=201, headers={"Location": f"/r/{code}"})

    @app.post("/api/rooms/{code}/join")
    async def join_room(request: Request, code: str, background: BackgroundTasks,
                        body: Annotated[JoinRequest | None, Body()] = None):
        """W2: rejoin by token, take seat B and start game 1, or refuse a third player.

        U5: taking seat B alerts seat A ("Your opponent has joined").
        P2 U3: the seat-token rejoin check runs first; then a pass-along room
        answers with a join request (202) or a refusal instead of seat B, and a
        direct join counts the current game if it is not finished (BR1.4).
        """
        code = rooms.normalize_code(code)
        token = body.token if body else None
        svc = services(request)
        address = ratelimit.client_address(request, svc.trusted_proxies)

        def action(conn: sqlite3.Connection, now: float):
            room = rooms.get_room(conn, code)
            existing = rooms.find_seat(conn, code, token)
            if existing is None and room.mode == rooms.MODE_PASS_ALONG:
                return _ask_to_join(svc, conn, code, token, address, now)
            joined = rooms.join_room(conn, code, token, now)
            game = games.current_game(conn, code)
            if joined.created:
                games.mark_playing(conn, game, now)
                games.mark_counted(conn, game)
                rooms.touch_room(conn, code, now)
                outbox.enqueue(conn, notifications.joined_event(code), now)
            return joined, game.colour_of(joined.seat.slot)

        result = await svc.mutate(code, action, viewer_token=token)
        if isinstance(result, rooms.JoinRequestOutcome):
            return await _join_request_answer(svc, background, code, result)
        joined, colour = result
        if joined.created:
            await svc.hub.broadcast(code)
            svc.schedule_alert(background, notifications.joined_event(code))
        return {"code": code, "token": joined.token, "slot": joined.seat.slot, "colour": colour}

    @app.get("/api/rooms/{code}")
    async def room_state(request: Request, code: str,
                         x_seat_token: Annotated[str | None, Header(max_length=TOKEN_MAX)] = None):
        """Read the snapshot; the seat comes from the X-Seat-Token header only, else watcher."""
        code = rooms.normalize_code(code)
        svc = services(request)
        try:
            await svc.lapse_on_read(code)  # P2 U3 BR2.4: an expired request lapses before it is read
            return svc.read_snapshot(code, x_seat_token)
        except sqlite3.Error:
            logger.exception("Database error in room %s", code)
            raise HTTPException(500, SERVER_ERROR) from None

    @app.post("/api/rooms/{code}/continue-link")
    async def continue_link(request: Request, code: str, body: SeatRequest):
        """W7: issue a continue token (valid 10 minutes) for moving this seat to another device."""
        code = rooms.normalize_code(code)

        def action(conn: sqlite3.Connection, now: float) -> str:
            seat = rooms.authorize_seat(conn, code, body.token)
            return rooms.issue_continue_token(conn, seat, now)

        continue_token = await services(request).mutate(code, action, viewer_token=body.token)
        return {"continueToken": continue_token, "expiresIn": int(rooms.CONTINUE_TTL)}

    @app.post("/api/rooms/{code}/continue")
    async def redeem_continue(request: Request, code: str, body: ContinueRequest):
        """W7: redeem a continue token; the old device is told seat-moved and becomes a watcher."""
        code = rooms.normalize_code(code)

        def action(conn: sqlite3.Connection, now: float) -> tuple[rooms.Transfer, str]:
            rooms.get_room(conn, code)
            moved = rooms.redeem_continue_token(conn, code, body.continueToken, now)
            # U5: the old device's push endpoints go with the seat; the new device subscribes again.
            notifications.delete_seat_subscriptions(conn, code, moved.seat.slot)
            rooms.touch_room(conn, code, now)
            return moved, games.current_game(conn, code).colour_of(moved.seat.slot)

        svc = services(request)
        moved, colour = await svc.mutate(code, action)
        await svc.hub.notify_seat_moved(code, moved.seat.slot, moved.old_token_hash)
        await svc.hub.broadcast(code)
        return {"code": code, "token": moved.token, "slot": moved.seat.slot, "colour": colour}


async def _create_computer_room(request: Request, body: CreateRoomRequest) -> JSONResponse:
    """BR3.1, BR6.2: validate (400), rate-limit (429), check the engine (503), create, then ask for the reply."""
    if body.level not in computer.LEVELS:
        raise DomainError(400, rooms.UNKNOWN_LEVEL)
    colour = _valid_colour(body.colour, allow_none=False)
    svc = services(request)
    _limit(svc, svc.create_limiter, request)
    if not svc.engine.available:
        raise DomainError(503, svc.engine.reason or ENGINE_DOWN)
    chosen = svc.colour_chooser(games.COLOURS) if colour == "random" else colour
    if chosen not in games.COLOURS:
        raise HTTPException(500, SERVER_ERROR)
    white_slot = "A" if chosen == "white" else "B"
    level = body.level

    def action(conn: sqlite3.Connection, now: float) -> tuple[str, str]:
        room, _seat, token = rooms.create_computer_room(conn, now, level, white_slot)
        games.create_computer_game(conn, room.code, white_slot, now)
        return room.code, token

    code, token = await svc.mutate(None, action)
    logger.info("Created computer room %s at level %s", code, level)
    asked = await svc.request_reply(code)  # BR3.1: the computer moves first when it plays white
    snapshot = _snapshot_with(svc, code, "A", asked.message)
    return JSONResponse({"code": code, "token": token, "slot": "A", "colour": chosen, "computer": snapshot["computer"]},
                        status_code=201, headers={"Location": f"/r/{code}"})


def _ask_to_join(svc: Services, conn: sqlite3.Connection, code: str, token: str | None, address: str,
                 now: float) -> rooms.JoinRequestOutcome:
    """BR2.1/BR3.1 inside the join transaction: rate limit first, then the request outcome (never raises after a write)."""
    if not svc.join_limiter.allow(address, now):
        raise DomainError(429, TOO_MANY, error="too_many")
    book = AddressBook(conn, svc.gameplay.decline_memory) if svc.db.backend == "postgresql" else svc.request_addresses
    declined = book.declined_recently(code, address, now)
    outcome = rooms.create_join_request(conn, code, token, now, declined, ttl=svc.gameplay.join_request_ttl)
    if outcome.kind == "created":
        book.note_request(outcome.request.request_id, address)
        outbox.enqueue(conn, notifications.join_request_event(code, outcome.request.request_id), now)
    return outcome


async def _join_request_answer(svc: Services, background: BackgroundTasks, code: str,
                               outcome: rooms.JoinRequestOutcome) -> JSONResponse:
    """After the join transaction: broadcast, alert seat A, and answer 202 or the refusal (BR2.1, BR2.5)."""
    if outcome.kind == "created" or outcome.lapsed:
        await svc.hub.broadcast(code)
    if outcome.kind == "busy":
        raise DomainError(409, rooms.BUSY, error="busy")
    if outcome.kind == "declined_recently":
        raise DomainError(409, rooms.DECLINED_RECENTLY, error="declined_recently")
    if outcome.kind == "created":
        logger.info("Join request %s created in room %s", outcome.request.request_id, code)
        svc.schedule_alert(background, notifications.join_request_event(code, outcome.request.request_id))
    request = outcome.request
    with svc.db.read() as conn:  # the colour the joiner would take over: seat B's in the current game
        colour = games.current_game(conn, code).colour_of("B")
    return JSONResponse({"requestPending": True, "requestToken": outcome.token, "expiresAt": request.expires_at,
                         "expiresIn": max(0.0, request.expires_at - svc.clock()), "colour": colour}, status_code=202)


def _add_join_request_routes(app: FastAPI) -> None:
    @app.post("/api/rooms/{code}/mode")
    async def set_mode(request: Request, code: str, body: ModeRequest):
        """BR1.1, W1: seat A switches between waiting, pass-along and the computer stand-in; answers seat A's snapshot."""
        code = rooms.normalize_code(code)
        svc = services(request)

        def action(conn: sqlite3.Connection, now: float) -> rooms.ModeChange:
            seat = rooms.authorize_seat(conn, code, body.token)
            change = rooms.set_mode(conn, code, seat, body.mode, now, level=body.level)
            if change.changed and change.mode == rooms.MODE_COMPUTER and not svc.engine.available:
                raise DomainError(503, ENGINE_DOWN)  # rolls the switch back: the computer could never answer
            if change.changed:
                _after_action(conn, code, seat.slot, now)
            return change

        change = await svc.mutate(code, action, viewer_token=body.token)
        if change.changed:
            await svc.hub.broadcast(code)
            logger.info("Room %s switched to %s", code, change.mode)
        return svc.slot_snapshot(code, "A")

    @app.post("/api/rooms/{code}/join-request/answer")
    async def answer_join_request(request: Request, code: str, body: AnswerRequest):
        """BR2.2, W3: seat A accepts or declines the pending request; 409 "No pending request" otherwise."""
        code = rooms.normalize_code(code)
        svc = services(request)

        def action(conn: sqlite3.Connection, now: float) -> rooms.Answer:
            seat = rooms.authorize_seat(conn, code, body.token)
            book = AddressBook(conn, svc.gameplay.decline_memory) if svc.db.backend == "postgresql" else svc.request_addresses
            answer = rooms.answer_request(conn, code, seat, body.accept, now, book)
            if answer.kind != "none":
                _after_action(conn, code, seat.slot, now)
            return answer

        answer = await svc.mutate(code, action, viewer_token=body.token)
        if answer.kind != "none" or answer.lapsed:
            await svc.hub.broadcast(code)
        if answer.kind == "none":
            error = DomainError(409, rooms.NO_PENDING)
            svc._attach_snapshot(code, body.token, error)
            raise error
        logger.info("Join request %s in room %s %s", answer.request.request_id, code, answer.kind)
        return svc.slot_snapshot(code, "A")

    @app.post("/api/rooms/{code}/join-request/status")
    async def join_request_status(request: Request, code: str, body: RequestStatusRequest):
        """BR2.3, W4: the joiner's poll; writes nothing except the lapse of BR2.4."""
        code = rooms.normalize_code(code)
        svc = services(request)
        status, lapsed = await svc.mutate(
            code, lambda conn, now: rooms.request_status(conn, code, body.requestToken, now))
        if lapsed:
            await svc.hub.broadcast(code)
        return status


def _add_game_routes(app: FastAPI) -> None:
    async def run_and_broadcast(request: Request, code: str, token: str, action: SeatAction,
                                background: BackgroundTasks | None = None, reply: bool = False) -> dict:
        """Run a seat action, broadcast when it changed something, schedule its alert, return the snapshot.

        P2 U4: with ``reply``, the computer's reply is asked for after the commit
        and before the broadcast, so every snapshot shows it queued or thinking.
        """
        svc = services(request)
        slot, changed, event = await svc.mutate(code, action, viewer_token=token)
        asked = await svc.request_reply(code) if reply else ReplyAsk()
        if changed or asked.asked:
            await svc.hub.broadcast(code)
        if background is not None:
            svc.schedule_alert(background, event)
        return _snapshot_with(svc, code, slot, asked.message)

    @app.post("/api/rooms/{code}/moves")
    async def make_move(request: Request, code: str, body: MoveRequest, background: BackgroundTasks):
        """W3: apply a move; on a game end the score is updated in the same transaction.

        U5: the opponent is alerted ``move:<game>:<ply>``, or ``ended:<game>`` for a final move.
        P2 U4 (W2): in a computer room the move is refused with 503 while the
        engine is unavailable, the end check adds the automatic draws, nobody is
        alerted, and the computer's reply is asked for after the commit.
        """
        code = rooms.normalize_code(code)
        svc = services(request)

        def action(conn: sqlite3.Connection, now: float) -> ActionResult:
            seat = rooms.authorize_seat(conn, code, body.token)
            mode = rooms.get_room(conn, code).mode
            pass_along, against_computer = mode == rooms.MODE_PASS_ALONG, mode == rooms.MODE_COMPUTER
            if against_computer and not svc.engine.available:
                raise DomainError(503, ENGINE_DOWN)  # BR5.5: the game would wait forever on the computer's turn
            game = games.apply_move(conn, games.current_game(conn, code), seat.slot, body.uci, body.version, now,
                                    pass_along=pass_along, computer=against_computer)
            _finish_score(conn, code, game)
            _after_action(conn, code, seat.slot, now)
            if pass_along or against_computer:  # one player at one device, or the computer: nobody to alert
                return seat.slot, True, None
            last = games.load_moves(conn, game.game_id)[-1]
            return seat.slot, True, notifications.event_after_move(code, seat.slot, game, last.ply, last.san)

        return await run_and_broadcast(request, code, body.token, action, background, reply=True)

    @app.post("/api/rooms/{code}/check-move")
    async def check_move(request: Request, code: str, body: MoveRequest):
        """U4 W1, BR2.1: judge a candidate move for the seat to move; changes nothing.

        Checks run in U1's order: seat (403), playing (409), version (409 with
        the snapshot), turn (403), legality (400). Analysis runs in a worker
        thread outside the room lock, so it never blocks moves or sockets.
        Answers ``{warning, san, version}``.
        """
        code = rooms.normalize_code(code)
        moves, version = await services(request).read_move_check(code, body.token, body.version)
        try:
            judged = await asyncio.to_thread(_judge_move, moves, body.uci, services(request).gameplay.blunder_budget_ms)
        except DomainError:
            raise
        except Exception:
            logger.exception("Blunder analysis failed in room %s", code)
            raise HTTPException(500, SERVER_ERROR) from None
        return {**judged, "version": version}

    @app.post("/api/rooms/{code}/claim-draw")
    async def claim_draw(request: Request, code: str, body: SeatRequest, background: BackgroundTasks):
        """W4: claim a threefold or 50-move draw as the seat to move (U5: alerts the other seat)."""
        code = rooms.normalize_code(code)

        def action(conn: sqlite3.Connection, now: float) -> ActionResult:
            seat = rooms.authorize_seat(conn, code, body.token)
            pass_along = _refuse_in_computer_room(conn, code).mode == rooms.MODE_PASS_ALONG
            game = games.claim_draw(conn, games.current_game(conn, code), seat.slot, now, pass_along=pass_along)
            _finish_score(conn, code, game)
            _after_action(conn, code, seat.slot, now)
            event = None if pass_along else notifications.event_after_claim(code, seat.slot, game)
            return seat.slot, True, event

        return await run_and_broadcast(request, code, body.token, action, background)

    @app.post("/api/rooms/{code}/claim-win")
    async def claim_win(request: Request, code: str, body: SeatRequest, background: BackgroundTasks):
        """W5: claim the win when the opponent has been away for more than 24 hours (U5: alerts them)."""
        code = rooms.normalize_code(code)
        hub = services(request).hub

        def action(conn: sqlite3.Connection, now: float) -> ActionResult:
            seat = rooms.authorize_seat(conn, code, body.token)
            _refuse_in_computer_room(conn, code)
            opponent_slot = rooms.other_slot(seat.slot)
            opponent = rooms.get_seats(conn, code).get(opponent_slot)
            presence = rooms.seat_presence(opponent, opponent_slot in hub.connected_slots(code), now,
                                           services(request).gameplay.abandon_after)
            game = games.claim_win(conn, games.current_game(conn, code), seat.slot, presence == "abandoned", now)
            _finish_score(conn, code, game)
            _after_action(conn, code, seat.slot, now)
            return seat.slot, True, notifications.event_after_claim(code, seat.slot, game)

        return await run_and_broadcast(request, code, body.token, action, background)

    @app.post("/api/rooms/{code}/rematch")
    async def rematch(request: Request, code: str, body: RematchRequest):
        """W6: request a rematch; the second seat's request starts the next game, colours swapped.

        P2 U3 BR1.5: in pass-along, seat A's "Play again" starts the next game at once, uncounted.
        P2 U4 BR3.4: in a computer room seat A starts the next game at once, colours
        swapped unless ``colour`` names one; the new game's reply replaces any
        reply still in flight, and is asked for at once when the computer is white.
        """
        code = rooms.normalize_code(code)

        def action(conn: sqlite3.Connection, now: float) -> ActionResult:
            seat = rooms.authorize_seat(conn, code, body.token)
            room, game = rooms.get_room(conn, code), games.current_game(conn, code)
            if room.mode == rooms.MODE_COMPUTER:
                colour = _valid_colour(body.colour, allow_none=True)
                # A stand-in's games never count toward the friends' room score.
                games.start_computer_rematch(conn, game, now, colour, counted=not rooms.is_stand_in(conn, code))
                _after_action(conn, code, seat.slot, now)
                return seat.slot, True, None
            if room.mode == rooms.MODE_PASS_ALONG and seat.slot == "A":
                games.start_pass_along_rematch(conn, game, now)
                rooms.clear_rematch(conn, code)
                _after_action(conn, code, seat.slot, now)
                return seat.slot, True, None
            outcome = rooms.request_rematch(conn, room, seat.slot, game.status == games.FINISHED, now)
            if outcome == "start":
                games.start_rematch(conn, game, now)
            elif outcome == "recorded":
                games.bump_version(conn, game)
            changed = outcome != "unchanged"
            if changed:
                _after_action(conn, code, seat.slot, now)
            return seat.slot, changed, None  # a rematch alerts nobody (BR1.1)

        return await run_and_broadcast(request, code, body.token, action, reply=True)

    _add_computer_routes(app, run_and_broadcast)


def _add_computer_routes(app: FastAPI, run_and_broadcast: Callable[..., Awaitable[dict]]) -> None:
    """P2 U4: computer-move, takeback, hint and resign (BR5.4, BR4.1, BR6.1, BR4.3)."""

    @app.post("/api/rooms/{code}/computer-move")
    async def computer_move(request: Request, code: str, body: SeatRequest):
        """BR5.4, W4: ask for the computer's reply when it is due; otherwise answer the state unchanged."""
        code = rooms.normalize_code(code)
        svc = services(request)
        _limit(svc, svc.computer_move_limiter, request)
        try:
            with svc.db.read() as conn:
                rooms.authorize_seat(conn, code, body.token)
                _require_computer_room(conn, code, COMPUTER_ONLY)
        except sqlite3.Error:
            logger.exception("Database error in room %s", code)
            raise HTTPException(500, SERVER_ERROR) from None
        asked = await svc.request_reply(code, respect_backoff=True)
        if asked.asked:
            await svc.hub.broadcast(code)
        return _snapshot_with(svc, code, "A", asked.message)

    @app.post("/api/rooms/{code}/takeback")
    async def takeback(request: Request, code: str, body: VersionedSeatRequest):
        """BR4.1, W5: take back the last move pair (or the player's move alone when the computer can't answer)."""
        code = rooms.normalize_code(code)
        svc = services(request)

        def action(conn: sqlite3.Connection, now: float) -> str:
            seat = rooms.authorize_seat(conn, code, body.token)
            _require_computer_room(conn, code, TAKEBACK_ONLY)
            game = games.current_game(conn, code)
            games.require_playing(game)
            if body.version != game.version:
                raise DomainError(409, games.STALE_VERSION)
            if svc.coordinator.reply_for(code, game.game_id) is not None:
                raise DomainError(409, games.WAIT_FOR_COMPUTER)  # BR5.3
            games.takeback(conn, game, now, True, version=body.version, player_slot=seat.slot)
            _after_action(conn, code, seat.slot, now)
            return seat.slot

        slot = await svc.mutate(code, action, viewer_token=body.token)
        await svc.hub.send_event(code, {"type": "takeback"})  # BR7.2: before the new state
        await svc.hub.broadcast(code)
        return svc.slot_snapshot(code, slot)

    @app.post("/api/rooms/{code}/resign")
    async def resign(request: Request, code: str, body: VersionedSeatRequest):
        """BR4.3, W7: resign the computer game; the score is recorded and a reply in flight is later discarded."""
        code = rooms.normalize_code(code)

        def action(conn: sqlite3.Connection, now: float) -> ActionResult:
            seat = rooms.authorize_seat(conn, code, body.token)
            _require_computer_room(conn, code, RESIGN_ONLY)
            game = games.resign(conn, games.current_game(conn, code), seat.slot, now, version=body.version)
            _finish_score(conn, code, game)
            _after_action(conn, code, seat.slot, now)
            return seat.slot, True, None

        return await run_and_broadcast(request, code, body.token, action)

    @app.post("/api/rooms/{code}/hint")
    async def hint(request: Request, code: str, body: VersionedSeatRequest):
        """BR6.1, W6: a full-strength move for the player's own turn; changes nothing in the game."""
        code = rooms.normalize_code(code)
        svc = services(request)
        _limit(svc, svc.hint_limiter, request)
        board, version, game_id = await svc.read_hint_position(code, body.token, body.version)
        if not svc.coordinator.begin_hint(code):
            raise DomainError(409, HINT_PENDING)
        try:
            if svc.engine.queued_count() >= svc.gameplay.hint_queue_limit:
                raise DomainError(503, engine_module.BUSY)
            try:
                ticket = svc.engine.submit(board, *computer.hint_settings(svc.gameplay))
            except (engine_module.EngineBusy, engine_module.EngineUnavailable) as refused:
                raise DomainError(503, refused.reason) from None
            try:
                move = await _await_hint(request, ticket)
            except engine_module.EngineFailure as failure:
                raise DomainError(503, failure.reason) from None
        finally:
            svc.coordinator.end_hint(code)
        _check_hint_still_current(svc, code, body.token, version, game_id)
        return {"uci": move.uci(), "from": chess.square_name(move.from_square),
                "to": chess.square_name(move.to_square), "san": board.san(move), "version": version}


def _check_hint_still_current(svc: Services, code: str, token: str, version: int, game_id: int) -> None:
    """BR6.1: a hint for a position that changed while it was computed answers 409 with the snapshot."""
    try:
        with svc.db.read() as conn:
            game = games.current_game(conn, code)
    except sqlite3.Error:
        logger.exception("Database error in room %s", code)
        raise HTTPException(500, SERVER_ERROR) from None
    if game.game_id != game_id or game.version != version:
        error = DomainError(409, games.STALE_VERSION)
        svc._attach_snapshot(code, token, error)
        raise error


def _add_push_routes(app: FastAPI) -> None:
    @app.get("/sw.js")
    def service_worker():
        """U5: the service worker, served from the root so it can control every page."""
        return FileResponse(SERVICE_WORKER, media_type="text/javascript",
                            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

    @app.get("/api/push/key")
    def push_key(request: Request):
        """BR2.3: the VAPID public key, or 404 ``{enabled: false}`` when push is disabled."""
        keys = services(request).vapid
        if not keys.enabled:
            return JSONResponse({"enabled": False, "detail": PUSH_DISABLED}, status_code=404)
        return {"enabled": True, "publicKey": keys.public_key}

    @app.post("/api/rooms/{code}/push/subscribe")
    async def push_subscribe(request: Request, code: str, body: SubscribeRequest):
        """BR2.1: a seat stores its own push subscription (403 for a foreign token, 400 when invalid)."""
        code = rooms.normalize_code(code)
        svc = services(request)
        if not svc.vapid.enabled:
            raise HTTPException(404, PUSH_DISABLED)
        endpoint, p256dh, auth = notifications.validate_subscription(body.endpoint, body.keys, svc.push_hosts)

        def action(conn: sqlite3.Connection, now: float) -> str:
            seat = rooms.authorize_seat(conn, code, body.token)
            notifications.save_subscription(conn, code, seat.slot, endpoint, p256dh, auth, now)
            return seat.slot

        slot = await svc.mutate(code, action)
        logger.info("Stored a push subscription for room %s seat %s (%s)", code, slot,
                    notifications.endpoint_host(endpoint))
        return {"ok": True}

    @app.post("/api/rooms/{code}/push/unsubscribe")
    async def push_unsubscribe(request: Request, code: str, body: UnsubscribeRequest):
        """BR2.2: a seat deletes its subscription for the given endpoint; the endpoint is required."""
        code = rooms.normalize_code(code)
        endpoint = body.endpoint
        if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= notifications.ENDPOINT_MAX:
            raise HTTPException(400, "An unsubscribe needs the subscription's endpoint")

        def action(conn: sqlite3.Connection, _now: float) -> int:
            seat = rooms.authorize_seat(conn, code, body.token)
            return notifications.delete_subscription(conn, code, seat.slot, endpoint)

        removed = await services(request).mutate(code, action)
        return {"ok": True, "removed": removed}


def _add_socket_route(app: FastAPI) -> None:
    @app.websocket("/ws/{code}")
    async def live(ws: WebSocket, code: str):
        """W8: live connection; origin is checked by middleware, the room must exist."""
        try:
            code = rooms.normalize_code(code)
        except DomainError:
            await ws.close(code=CLOSE_POLICY)
            return
        svc: Services = ws.app.state.services
        try:
            with svc.db.read() as conn:
                exists = rooms.room_exists(conn, code)
        except sqlite3.Error:
            logger.exception("Database error in room %s", code)
            await ws.close(code=CLOSE_SERVER_ERROR)
            return
        if not exists:
            await ws.close(code=CLOSE_POLICY)
            return
        await svc.hub.serve(ws, code)
