"""Engine: one Stockfish process behind a FIFO queue (P2 U4, BR1.1-BR1.6, NFR1, ADR-001).

One python-chess asyncio UCI process (``chess.engine.popen_uci``) runs with
``Threads = 2`` and ``Hash = 64`` and serves one search at a time, in arrival
order, from a worker task. The web server's event loop never waits on it.

    engine = Engine(opener=chess.engine.popen_uci)
    await engine.start(path)            # or engine.mark_missing() when no binary was found
    ticket = engine.submit(board, skill, think, on_progress)   # synchronous
    move = await ticket.result()        # a legal chess.Move, or EngineFailure
    engine.cancel(ticket)               # a queued request leaves the queue; a running one's result is dropped
    engine.queued_count()               # requests waiting behind the running search
    await engine.stop()

Rules:

- ``submit`` returns a Ticket at once with its request id and initial state:
  ``thinking`` when nothing is ahead of it, else ``queued`` with
  ``queue_position`` = the requests ahead of it (the running search included).
  It raises ``EngineUnavailable`` (with the reason) while the engine is not
  available and ``EngineBusy`` when 32 requests are already waiting (BR1.2).
- ``on_progress(state, position)`` is called when a queued request's position
  changes (``"queued", n``) and when its search starts (``"thinking", None``).
  A callback that raises is logged and ignored.
- The board is copied with its move stack, so the engine receives the start
  position and the moves replayed from storage, never client text (BR1.6). The
  returned move is checked to be legal on that board; an illegal or missing
  move fails the request without counting as a crash.
- A search still running at ``think + grace`` (5 s) seconds, a process that
  exits, or one that stops answering counts as a crash (BR1.4): the running
  request fails, the process is killed, and it is restarted (``restarts``
  times in all, once by default) while the queue carries on. A crash after the
  restarts are used, or a restart that fails, makes the engine unavailable
  ("The computer stopped working") and fails every queued request; restarts
  are never given back while the app runs (BR1.3).
- ``submit(..., depth=n)`` also stops the search at depth ``n`` (P2 U4 tuning:
  weaker levels); the think time still applies.
- ``max_queue``, ``grace`` and ``restarts`` come from ``gameplay.yaml`` in the app.
- The engine reports "The computer is starting" until ``start`` has opened the
  process, then available, or "No chess engine is installed" /
  "The computer could not be started" (BR1.5). ``stop`` fails queued requests,
  asks the process to quit and kills it after 2 s.

Errors are logged without positions; this module never sees a seat token. The
binary path is never put in a reason.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import chess
import chess.engine

logger = logging.getLogger("justchess.engine")

MAX_QUEUE = 32  # these three are fallbacks: the app passes gameplay.yaml's engine values
GRACE_SECONDS = 5.0
RESTARTS = 1
QUIT_SECONDS = 2.0
OPEN_SECONDS = 15.0
THREADS = 2
HASH_MB = 64

STARTING = "The computer is starting"
NOT_INSTALLED = "No chess engine is installed"
COULD_NOT_START = "The computer could not be started"
STOPPED_WORKING = "The computer stopped working"
SHUTTING_DOWN = "The computer is shutting down"
BUSY = "The computer is busy, try again in a moment"
NO_MOVE = "The computer did not find a legal move"

Opener = Callable[[str], Awaitable[tuple[asyncio.SubprocessTransport, chess.engine.UciProtocol]]]
Progress = Callable[[str, int | None], None]


def search_limit(think: float, depth: int | None = None) -> chess.engine.Limit:
    """The search limit: the think time, and the depth limit when the level has one (the first reached stops it)."""
    return chess.engine.Limit(time=think, depth=depth) if depth is not None else chess.engine.Limit(time=think)


class EngineBusy(Exception):
    """The queue is full (BR1.2); nothing was queued."""

    def __init__(self) -> None:
        super().__init__(BUSY)
        self.reason = BUSY


class EngineUnavailable(Exception):
    """The engine is not available; ``reason`` is the text shown to the player."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class EngineFailure(Exception):
    """A request failed (crash, overrun, illegal move, shutdown); ``reason`` is shown to the player."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(eq=False)
class _Request:
    request_id: int
    board: chess.Board
    skill: int
    think: float
    on_progress: Progress | None
    future: asyncio.Future
    state: str = "queued"
    position: int | None = None
    depth: int | None = None

    def notify(self, state: str, position: int | None) -> None:
        self.state, self.position = state, position
        if self.on_progress is None or self.future.done():
            return
        try:
            self.on_progress(state, position)
        except Exception:  # a broken listener must never stop the queue
            logger.exception("Engine progress listener failed for request %s", self.request_id)


@dataclass(eq=False)
class Ticket:
    """A submitted request: its id, the state it started in, and the way to its result."""

    request_id: int
    state: str
    queue_position: int | None
    _request: _Request = field(repr=False)
    _engine: Engine = field(repr=False)

    async def result(self) -> chess.Move:
        """The legal move, or ``EngineFailure``; cancelling the waiter cancels the request."""
        try:
            return await self._request.future
        except asyncio.CancelledError:
            self._engine.cancel(self)
            raise


class Engine:
    """One UCI process, one search at a time, a bounded FIFO queue, one restart."""

    def __init__(self, opener: Opener = chess.engine.popen_uci, *, max_queue: int = MAX_QUEUE,
                 grace: float = GRACE_SECONDS, restarts: int = RESTARTS, quit_timeout: float = QUIT_SECONDS,
                 open_timeout: float = OPEN_SECONDS, threads: int = THREADS, hash_mb: int = HASH_MB) -> None:
        self._opener = opener
        self.max_queue = max_queue
        self.max_restarts = restarts
        self.grace = grace
        self.quit_timeout = quit_timeout
        self.open_timeout = open_timeout
        self.threads = threads
        self.hash_mb = hash_mb
        self.available = False
        self.reason: str | None = STARTING
        self.restarts_used = 0
        self._path: str | None = None
        self._transport: asyncio.SubprocessTransport | None = None
        self._protocol: chess.engine.UciProtocol | None = None
        self._queue: deque[_Request] = deque()
        self._current: _Request | None = None
        self._ids = itertools.count(1)
        self._wake = asyncio.Event()
        self._worker: asyncio.Task | None = None
        self._stopped = False

    # --- status -------------------------------------------------------------

    def status(self) -> dict[str, object]:
        """``{available, reason}`` for the snapshot and ``GET /api/engine``."""
        return {"available": self.available, "reason": None if self.available else self.reason}

    def queued_count(self) -> int:
        """Requests waiting behind the running search (the hint threshold reads this, BR6.1)."""
        return len(self._queue)

    @property
    def busy(self) -> bool:
        """True while a search runs."""
        return self._current is not None

    # --- lifecycle ----------------------------------------------------------

    def mark_missing(self) -> None:
        """No binary was found: unavailable with "No chess engine is installed" (BR1.5)."""
        self._make_unavailable(NOT_INSTALLED)

    async def start(self, path: Path | str) -> None:
        """Open the process and start the worker; a failure marks the engine unavailable (never raises)."""
        if self._stopped:
            return
        self._path = str(path)
        try:
            await self._open()
        except Exception as exc:  # any open failure leaves the app running without an engine
            logger.error("The chess engine could not be started (%s)", type(exc).__name__)
            self._make_unavailable(COULD_NOT_START)
            return
        self.available, self.reason = True, None
        self._worker = asyncio.create_task(self._run(), name="justchess-engine")
        logger.info("The chess engine is ready (Threads=%d, Hash=%d MB)", self.threads, self.hash_mb)

    async def stop(self) -> None:
        """Fail every request, stop the worker, ask the process to quit and kill it after 2 s."""
        self._stopped = True
        self._make_unavailable(SHUTTING_DOWN)
        if self._current is not None:
            self._fail(self._current, EngineFailure(SHUTTING_DOWN))
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        await self._close_process(gracefully=True)

    async def _open(self) -> None:
        transport, protocol = await asyncio.wait_for(self._opener(self._path), self.open_timeout)
        self._transport, self._protocol = transport, protocol
        await asyncio.wait_for(protocol.configure({"Threads": self.threads, "Hash": self.hash_mb}), self.open_timeout)

    async def _close_process(self, gracefully: bool) -> None:
        transport, protocol = self._transport, self._protocol
        self._transport = self._protocol = None
        if protocol is not None and gracefully:
            try:
                await asyncio.wait_for(protocol.quit(), self.quit_timeout)
            except (TimeoutError, chess.engine.EngineError, OSError, asyncio.CancelledError):
                logger.warning("The chess engine did not quit within %.0f s; killing it", self.quit_timeout)
        if transport is not None:
            try:
                transport.kill()
            except (ProcessLookupError, OSError):
                pass  # it already exited
            transport.close()

    # --- requests -----------------------------------------------------------

    def submit(self, board: chess.Board, skill: int, think: float, on_progress: Progress | None = None,
               depth: int | None = None) -> Ticket:
        """Queue a search synchronously and return its Ticket; raise EngineUnavailable or EngineBusy."""
        if not self.available:
            raise EngineUnavailable(self.reason or STARTING)
        if len(self._queue) >= self.max_queue:
            raise EngineBusy()
        future = asyncio.get_running_loop().create_future()
        request = _Request(next(self._ids), board.copy(stack=True), skill, think, on_progress, future, depth=depth)
        ahead = len(self._queue) + (1 if self._current is not None else 0)
        request.state, request.position = ("thinking", None) if ahead == 0 else ("queued", ahead)
        self._queue.append(request)
        self._wake.set()
        return Ticket(request.request_id, request.state, request.position, request, self)

    def cancel(self, ticket: Ticket) -> None:
        """A queued request leaves the queue; a running one's result is dropped when it comes."""
        request = ticket._request
        if not request.future.done():
            request.future.cancel()
        if request in self._queue:
            self._queue.remove(request)
            self._report_positions()

    def _report_positions(self) -> None:
        for index, request in enumerate(self._queue):
            position = index + 1  # the running search is ahead of every waiting request
            if request.state != "queued" or request.position != position:
                request.notify("queued", position)

    @staticmethod
    def _fail(request: _Request, error: Exception) -> None:
        if not request.future.done():
            request.future.set_exception(error)
            request.future.exception()  # mark retrieved: a dropped (cancelled-waiter) result never warns

    def _make_unavailable(self, reason: str) -> None:
        self.available, self.reason = False, reason
        while self._queue:
            self._fail(self._queue.popleft(), EngineFailure(reason))

    # --- worker -------------------------------------------------------------

    async def _run(self) -> None:
        while True:
            while not self._queue:
                self._wake.clear()
                await self._wake.wait()
            request = self._queue.popleft()
            self._report_positions()
            if request.future.done():
                continue  # cancelled while it waited
            await self._serve(request)

    async def _serve(self, request: _Request) -> None:
        self._current = request
        request.notify("thinking", None)
        try:
            move = await asyncio.wait_for(self._search(request), request.think + self.grace)
        except (TimeoutError, chess.engine.EngineTerminatedError, OSError, ConnectionError) as exc:
            logger.error("The chess engine failed request %s (%s); counting a crash",
                         request.request_id, type(exc).__name__)
            self._fail(request, EngineFailure(STOPPED_WORKING))
            await self._crashed()
        except chess.engine.EngineError as exc:
            logger.error("The chess engine answered request %s with an unusable move (%s)",
                         request.request_id, type(exc).__name__)
            self._fail(request, EngineFailure(NO_MOVE))
        else:
            if move is None or move not in request.board.legal_moves:
                logger.error("The chess engine returned no legal move for request %s", request.request_id)
                self._fail(request, EngineFailure(NO_MOVE))
            elif not request.future.done():
                request.future.set_result(move)
        finally:
            self._current = None

    async def _search(self, request: _Request) -> chess.Move | None:
        if self._protocol is None:
            raise chess.engine.EngineTerminatedError("no engine process")
        result = await self._protocol.play(request.board, search_limit(request.think, request.depth),
                                           options={"Skill Level": request.skill})
        return result.move

    async def _crashed(self) -> None:
        """BR1.3: kill the process; restart it once, else become unavailable for good."""
        await self._close_process(gracefully=False)
        if self._stopped:
            return
        if self.restarts_used >= self.max_restarts:
            logger.error("The chess engine crashed again; it stays unavailable until the app restarts")
            self._make_unavailable(STOPPED_WORKING)
            return
        self.restarts_used += 1
        try:
            await self._open()
        except Exception as exc:  # a failed restart is final
            logger.error("The chess engine could not be restarted (%s)", type(exc).__name__)
            self._make_unavailable(STOPPED_WORKING)
            return
        logger.warning("The chess engine crashed and was restarted (the one restart is now used)")
