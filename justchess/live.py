"""LiveUpdates: WebSocket connections per room, hello handshake and presence.

Protocol (BR4.4, W8):

- The client opens ``/ws/{code}`` and sends ``{"type": "hello", "token"?, "visible"}``
  as its first message. A matching seat token binds the socket to that seat; no
  token or an invalid one makes it a read-only watcher, never an error.
- The server answers with ``{"type": "state", ...snapshot}`` and sends one again,
  composed per socket, after every change in the room.
- The client sends ``{"type": "ping"}`` every 5 s and ``{"type": "visibility",
  "visible": bool}`` on change. A socket silent for ``receive_timeout`` seconds
  (10 s in production) is closed with code 4408 and its seat becomes away.
- A message over ``max_message_bytes`` (1 KB) closes the socket with code 1009.
  Malformed JSON closes it with 1003 and a first message that is not a hello
  with 1008.
- When a seat moves to another device, sockets bound to the old seat token get
  ``{"type": "seat-moved"}`` and become watchers.
- P2 U4 (BR7.2): ``send_event(code, message)`` sends one event, the same to
  every socket in the room: ``{"type": "computer", "state", "queuePosition"}``
  when the computer's reply request moves up the queue or its search starts,
  and ``{"type": "takeback"}`` just before the state that follows a takeback.
- U5: each socket records ``last_heard`` (the hello, every ping and every
  visibility message). ``is_fresh_visible`` is True only for a seat with a
  socket that reports a visible page and was heard from in the last
  ``FRESH_WINDOW`` (6 s), so a stale "visible" flag never suppresses a push.

The hub knows nothing about the database: the API layer passes callbacks to
identify a token, record lastSeenAt and compose snapshots.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from starlette.websockets import WebSocket, WebSocketDisconnect

from justchess import DomainError

logger = logging.getLogger("justchess.live")

RECEIVE_TIMEOUT = 10.0
MAX_MESSAGE_BYTES = 1024
SEEN_WRITE_INTERVAL = 60.0
FRESH_WINDOW = 6.0  # U5: a visible socket counts only if heard from this recently (pings are every 5 s)

CLOSE_UNSUPPORTED_DATA = 1003
CLOSE_POLICY = 1008
CLOSE_TOO_BIG = 1009
CLOSE_SERVER_ERROR = 1011
CLOSE_TIMEOUT = 4408

Identity = tuple[str, str]  # (slot, token_hash)
SnapshotFor = Callable[[str | None], dict]
SnapshotSource = Callable[[str], SnapshotFor]
Identify = Callable[[str, str | None], Identity | None]
MarkSeen = Callable[[str, str], None]


@dataclass(eq=False)
class Connection:
    """One open socket and the identity it proved in its hello."""

    ws: WebSocket
    slot: str | None
    token_hash: str | None
    visible: bool = True
    last_heard: float = 0.0  # clock time of the last hello, ping or visibility message
    connection_id: str = ""
    credential: str | None = field(default=None, repr=False)


class LiveHub:
    """Registry of sockets per room, with per-socket snapshot broadcasts."""

    def __init__(self, *, snapshot_source: SnapshotSource, identify: Identify, mark_seen: MarkSeen,
                 clock: Callable[[], float], receive_timeout: float = RECEIVE_TIMEOUT,
                 max_message_bytes: int = MAX_MESSAGE_BYTES) -> None:
        self._snapshot_source = snapshot_source
        self._identify = identify
        self._mark_seen = mark_seen
        self._clock = clock
        self.receive_timeout = receive_timeout
        self.max_message_bytes = max_message_bytes
        self._rooms: dict[str, set[Connection]] = {}
        self._seen_written: dict[tuple[str, str], float] = {}
        self.coordination = None

    # --- registry ----------------------------------------------------------

    def connected_slots(self, code: str) -> set[str]:
        """Return the slots with at least one live socket in the room."""
        if self.coordination and self.coordination.db.backend == "postgresql":
            return {row["slot"] for row in self.coordination.presence(code)}
        return {conn.slot for conn in self._rooms.get(code, ()) if conn.slot is not None}

    def is_visible(self, code: str, slot: str) -> bool:
        """Return True when any of the seat's sockets reports a visible page."""
        return any(c.visible for c in self._rooms.get(code, ()) if c.slot == slot)

    def is_fresh_visible(self, code: str, slot: str, now: float, window: float = FRESH_WINDOW) -> bool:
        """U5: True when one of the seat's sockets reports a visible page and was heard within ``window``."""
        if self.coordination and self.coordination.db.backend == "postgresql":
            return any(row["slot"] == slot and row["visible"] and now - row["heard_at"] <= window
                       for row in self.coordination.presence(code))
        return any(c.visible and now - c.last_heard <= window
                   for c in self._rooms.get(code, ()) if c.slot == slot)

    def connections(self, code: str) -> list[Connection]:
        """The room's open sockets (read-only use: tests and diagnostics)."""
        return list(self._rooms.get(code, ()))

    def _register(self, code: str, conn: Connection) -> None:
        self._rooms.setdefault(code, set()).add(conn)

    def _unregister(self, code: str, conn: Connection) -> None:
        members = self._rooms.get(code)
        if members is None:
            return
        members.discard(conn)
        if not members:
            del self._rooms[code]

    # --- sending -----------------------------------------------------------

    async def _send(self, code: str, conn: Connection, payload: dict) -> None:
        try:
            await conn.ws.send_text(json.dumps(payload))
        except (WebSocketDisconnect, RuntimeError, OSError) as exc:
            logger.debug("Dropping a closed socket in room %s: %s", code, type(exc).__name__)
            self._unregister(code, conn)

    def _compose(self, code: str) -> SnapshotFor | None:
        try:
            return self._snapshot_source(code)
        except DomainError as exc:
            logger.info("No snapshot for room %s: %s", code, exc.message)
        except sqlite3.Error:
            logger.exception("Database error while composing a snapshot for room %s", code)
        return None

    async def broadcast(self, code: str) -> None:
        if self.coordination:
            self.coordination.publish(code)
        await self.broadcast_local(code)

    async def broadcast_local(self, code: str) -> None:
        """Send every socket in the room its own snapshot (seat A, seat B or watcher)."""
        members = list(self._rooms.get(code, ()))
        if not members:
            return
        snapshot_for = self._compose(code)
        if snapshot_for is None:
            return
        for conn in members:
            if conn.slot is not None and conn.credential is not None and self._identify(code, conn.credential) is None:
                conn.slot, conn.token_hash = None, None
                if self.coordination:
                    self.coordination.leave(conn.connection_id)
                await self._send(code, conn, {"type": "seat-moved"})
            await self._send(code, conn, {"type": "state", **snapshot_for(conn.slot)})

    async def send_event(self, code: str, message: dict) -> None:
        """P2 U4 BR7.2: send one event (``computer`` or ``takeback``) to every socket in the room."""
        if message.get("type") not in ("computer", "takeback"):
            raise ValueError(f"not a room event: {message.get('type')!r}")
        for conn in list(self._rooms.get(code, ())):
            await self._send(code, conn, message)

    async def notify_seat_moved(self, code: str, slot: str, old_token_hash: str) -> None:
        """Tell sockets bound to the old seat token that the seat moved; they become watchers."""
        for conn in list(self._rooms.get(code, ())):
            if conn.slot == slot and conn.token_hash == old_token_hash:
                conn.slot, conn.token_hash = None, None
                await self._send(code, conn, {"type": "seat-moved"})

    # --- lastSeenAt --------------------------------------------------------

    def _seen(self, code: str, slot: str, force: bool) -> None:
        key = (code, slot)
        now = self._clock()
        last = self._seen_written.get(key)
        if not force and last is not None and now - last < SEEN_WRITE_INTERVAL:
            return
        try:
            self._mark_seen(code, slot)
            self._seen_written[key] = now
        except sqlite3.Error:
            logger.exception("Could not record lastSeenAt for room %s", code)

    # --- serving one socket ------------------------------------------------

    async def _close(self, ws: WebSocket, code: int) -> None:
        try:
            await ws.close(code=code)
        except (RuntimeError, WebSocketDisconnect, OSError):
            logger.debug("Socket already closed before close code %s", code)

    async def _receive(self, ws: WebSocket, room: str) -> dict | None:
        """Return the next JSON object, or None after the socket closed or was closed."""
        try:
            message = await asyncio.wait_for(ws.receive(), self.receive_timeout)
        except TimeoutError:
            logger.info("Socket in room %s silent for %.1f s; closing", room, self.receive_timeout)
            await self._close(ws, CLOSE_TIMEOUT)
            return None
        if message["type"] == "websocket.disconnect":
            return None
        text, data = message.get("text"), message.get("bytes")
        raw = text.encode("utf-8") if text is not None else (data or b"")
        if len(raw) > self.max_message_bytes:
            logger.info("Socket in room %s sent %d bytes; closing", room, len(raw))
            await self._close(ws, CLOSE_TOO_BIG)
            return None
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            parsed = None
        if not isinstance(parsed, dict):
            await self._close(ws, CLOSE_UNSUPPORTED_DATA)
            return None
        return parsed

    async def _handshake(self, ws: WebSocket, code: str) -> Connection | None:
        hello = await self._receive(ws, code)
        if hello is None:
            return None
        if hello.get("type") != "hello":
            await self._close(ws, CLOSE_POLICY)
            return None
        token = hello.get("token") if isinstance(hello.get("token"), str) else None
        identity = self._identify(code, token)
        slot, token_hash = identity if identity else (None, None)
        return Connection(ws, slot, token_hash, visible=hello.get("visible", True) is not False,
                          last_heard=self._clock(), credential=token)

    async def serve(self, ws: WebSocket, code: str) -> None:
        if self.coordination:
            async with self.coordination.listening(code, self.broadcast_local):
                await self._serve(ws, code)
        else:
            await self._serve(ws, code)

    async def _serve(self, ws: WebSocket, code: str) -> None:
        """Run one socket from accept to close. The caller has checked origin and room."""
        await ws.accept()
        conn: Connection | None = None
        try:
            conn = await self._handshake(ws, code)
            if conn is None:
                return
            newly_present = conn.slot is not None and conn.slot not in self.connected_slots(code)
            conn.connection_id = uuid.uuid4().hex
            self._register(code, conn)
            self._presence(code, conn)
            if conn.slot is not None:
                self._seen(code, conn.slot, force=True)
            if newly_present:
                await self.broadcast(code)
            else:
                snapshot_for = self._compose(code)
                if snapshot_for is not None:
                    await self._send(code, conn, {"type": "state", **snapshot_for(conn.slot)})
            await self._listen(ws, code, conn)
        except WebSocketDisconnect:
            pass
        except sqlite3.Error:
            logger.exception("Database error on a socket in room %s", code)
            await self._close(ws, CLOSE_SERVER_ERROR)
        finally:
            if conn is not None:
                await self._leave(code, conn)

    async def _listen(self, ws: WebSocket, code: str, conn: Connection) -> None:
        while True:
            message = await self._receive(ws, code)
            if message is None:
                return
            kind = message.get("type")
            if kind == "ping":
                conn.last_heard = self._clock()
                if conn.slot is not None:
                    self._seen(code, conn.slot, force=False)
            elif kind == "visibility":
                conn.last_heard = self._clock()
                conn.visible = message.get("visible") is not False
            else:
                logger.debug("Ignoring a %r message in room %s", kind, code)
            if kind in ("ping", "visibility"):
                self._presence(code, conn)

    def _presence(self, code, conn):
        if self.coordination:
            self.coordination.touch(code, conn.connection_id, conn.slot, conn.visible, conn.last_heard)

    async def _leave(self, code: str, conn: Connection) -> None:
        self._unregister(code, conn)
        if self.coordination:
            self.coordination.leave(conn.connection_id)
        if conn.slot is not None and conn.slot not in self.connected_slots(code):
            self._seen(code, conn.slot, force=True)
            await self.broadcast(code)
