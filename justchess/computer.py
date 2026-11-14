"""ComputerOpponent: the level table and the per-room reply and hint coordination (P2 U4, BR2.x, BR5.x, ADR-009).

Levels (BR2.1, FR6.2) come from ``gameplay.yaml`` (``justchess.gameplay``): each
has a Stockfish skill, a think time, an optional depth limit and a random-move
chance. The shipped table, all weaker than full strength:

    beginner  skill 0,  depth 1,  0.05 s, random 0.35     casual   skill 2,  depth 3,  0.1 s, random 0.15
    club      skill 6,  depth 6,  0.3 s,  random 0.05     strong   skill 11, depth 10, 0.6 s, random 0
    maximum   skill 16, no depth limit, 1.0 s, random 0

``maybe_randomise(board, move, chance, rng)`` replaces the engine's move, with
probability ``chance``, by a random other legal move. ``rng`` is a
``random.SystemRandom`` by default (``random()`` and ``choice()``), injectable
for tests; a chance of 0 never randomises.

Hints (BR2.2) always search at full strength (skill 20, 0.5 s by default) and are never randomised.

``ComputerCoordinator`` keeps, in memory and per room (lost on restart, by
design, ADR-009):

- ``ReplyInFlight {game_id, version, request_id}`` plus the request's latest
  state (``queued`` with its position, or ``thinking``). A new flag replaces an
  older one (a rematch's new game supersedes the old game's reply), and only
  the completion of the request that set a flag may clear it
  (``clear_reply(code, request_id)``). ``reply_for(code, game_id)`` ignores a
  flag left from an earlier game, so it never blocks the current one (BR5.3).
- ``HintInFlight``: at most one hint per room (BR6.1).
- ``RetryBackoff``: after a failed reply (not busy), the room asks the engine
  again no sooner than 5 s later (BR5.6).
- A strong-reference set of the tasks it starts, so a running reply task is
  never garbage-collected; ``run_reply`` clears the room's flag in a
  ``finally`` (success, failure, exception or cancellation), and only when the
  flag still carries that task's request id (BR5.1).

``computer_state`` builds the snapshot's ``computer`` field (BR7.1):
``{state, queuePosition, reason, level, available, message}`` where state is
``idle``, ``queued``, ``thinking`` or ``unavailable``; ``queuePosition`` is set
only while queued and ``reason`` only while unavailable. ``message`` is null
except in the HTTP answer right after the engine refused a reply as busy, so
the page can say so and retry.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import chess

from justchess.gameplay import DEFAULT_GAMEPLAY, Gameplay, Level

logger = logging.getLogger("justchess.computer")

# Fallbacks for direct calls; the app passes the loaded gameplay settings.
BACKOFF_SECONDS = DEFAULT_GAMEPLAY.retry_backoff
HINT_QUEUE_LIMIT = DEFAULT_GAMEPLAY.hint_queue_limit  # BR6.1: hints are refused once this many requests wait
LEVELS: dict[str, Level] = DEFAULT_GAMEPLAY.levels

__all__ = ["Level", "LEVELS", "ReplyInFlight", "ComputerCoordinator", "computer_state", "hint_settings",
           "maybe_randomise", "reply_settings"]


class MoveChooser(Protocol):
    """What ``maybe_randomise`` needs from a random source (``random.SystemRandom`` fits)."""

    def random(self) -> float: ...

    def choice(self, seq): ...


def reply_settings(level: str, levels: dict[str, Level] | None = None) -> Level:
    """BR2.1: the level's settings (skill, think, depth, random-move chance); KeyError for an unknown level."""
    return (levels if levels is not None else LEVELS)[level]


def hint_settings(settings: Gameplay | None = None) -> tuple[int, float]:
    """BR2.2: ``(skill, think seconds)`` for hints: full strength, never randomised."""
    settings = settings or DEFAULT_GAMEPLAY
    return settings.hint_skill, settings.hint_think


def maybe_randomise(board: chess.Board, move: chess.Move, chance: float, rng: MoveChooser | None = None) -> chess.Move:
    """With probability ``chance``, a random legal move other than ``move``; else ``move`` (chance 0: never)."""
    if chance <= 0:
        return move
    rng = rng or random.SystemRandom()
    if rng.random() >= chance:
        return move
    others = sorted((candidate for candidate in board.legal_moves if candidate != move), key=chess.Move.uci)
    return rng.choice(others) if others else move


@dataclass
class ReplyInFlight:
    """The room's reply request: the game and version it was asked for, its request id and its latest state."""

    game_id: int
    version: int
    request_id: int
    state: str = "queued"
    queue_position: int | None = None
    random_move_chance: float = 0.0


def computer_state(level: str | None, engine_status: dict[str, object], flight: ReplyInFlight | None,
                   message: str | None = None) -> dict[str, object]:
    """BR7.1: the snapshot's ``computer`` field for a computer room."""
    available = bool(engine_status.get("available"))
    state, position, reason = "idle", None, None
    if flight is not None:
        state = flight.state
        position = flight.queue_position if flight.state == "queued" else None
    elif not available:
        state, reason = "unavailable", engine_status.get("reason")
    return {"state": state, "queuePosition": position, "reason": reason, "level": level,
            "available": available, "message": message}


class ComputerCoordinator:
    """Per-room reply and hint flags, the retry backoff, and the reply tasks (in memory only)."""

    def __init__(self, clock: Callable[[], float], backoff_seconds: float = BACKOFF_SECONDS) -> None:
        self.clock = clock
        self.backoff_seconds = backoff_seconds
        self._replies: dict[str, ReplyInFlight] = {}
        self._hints: set[str] = set()
        self._backoff: dict[str, float] = {}
        self.tasks: set[asyncio.Task] = set()

    # --- reply flag ---------------------------------------------------------

    def reply_for(self, code: str, game_id: int) -> ReplyInFlight | None:
        """The room's flag when it belongs to this game (an older game's flag never blocks, BR5.3)."""
        flight = self._replies.get(code)
        return flight if flight is not None and flight.game_id == game_id else None

    def any_reply(self, code: str) -> ReplyInFlight | None:
        """The room's flag, whatever game it belongs to."""
        return self._replies.get(code)

    def set_reply(self, code: str, flight: ReplyInFlight) -> None:
        """Set the room's flag, replacing any earlier one (BR5.1)."""
        self._replies[code] = flight

    def clear_reply(self, code: str, request_id: int) -> bool:
        """Clear the flag only when it still carries ``request_id``; return True when it did."""
        flight = self._replies.get(code)
        if flight is None or flight.request_id != request_id:
            return False
        del self._replies[code]
        return True

    def progress(self, code: str, request_id: int, state: str, position: int | None) -> bool:
        """Record a request's new state on the room's flag; False when the flag is another request's."""
        flight = self._replies.get(code)
        if flight is None or flight.request_id != request_id:
            return False
        flight.state, flight.queue_position = state, position
        return True

    # --- hint flag ----------------------------------------------------------

    def begin_hint(self, code: str) -> bool:
        """Take the room's one hint slot; False when a hint is already on its way."""
        if code in self._hints:
            return False
        self._hints.add(code)
        return True

    def end_hint(self, code: str) -> None:
        self._hints.discard(code)

    def hint_pending(self, code: str) -> bool:
        return code in self._hints

    # --- retry backoff ------------------------------------------------------

    def set_backoff(self, code: str) -> None:
        """BR5.6: no new reply request for this room for the next 5 s."""
        self._backoff[code] = self.clock() + self.backoff_seconds

    def in_backoff(self, code: str) -> bool:
        until = self._backoff.get(code)
        if until is None:
            return False
        if self.clock() >= until:
            del self._backoff[code]
            return False
        return True

    # --- tasks --------------------------------------------------------------

    def spawn(self, coro: Awaitable[None], name: str | None = None) -> asyncio.Task:
        """Start a task held in a strong reference until it ends."""
        task = asyncio.ensure_future(coro)
        if name:
            task.set_name(name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def run_reply(self, code: str, flight: ReplyInFlight, work: Callable[[], Awaitable[None]]) -> asyncio.Task:
        """Set the flag and run ``work`` in a task that clears it in ``finally`` (only its own request id)."""
        self.set_reply(code, flight)

        async def runner() -> None:
            try:
                await work()
            except asyncio.CancelledError:
                logger.info("The reply task for room %s was cancelled", code)
                raise
            except Exception:  # the task is the boundary: log, the finally still clears the flag
                logger.exception("The reply task for room %s failed", code)
            finally:
                self.clear_reply(code, flight.request_id)

        return self.spawn(runner(), name=f"reply-{code}-{flight.request_id}")

    async def drain(self) -> None:
        """Wait for every running task (tests and shutdown)."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def cancel_all(self) -> None:
        """Cancel every running task and wait for them (app shutdown)."""
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
