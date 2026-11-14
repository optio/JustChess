"""P2 U4 ComputerOpponent (BR2.1, BR2.2, BR5.1, BR5.3, BR5.6, BR7.1): levels, hint settings and the coordinator."""

from __future__ import annotations

import asyncio

import chess
import pytest

from justchess import computer
from justchess.computer import ComputerCoordinator, ReplyInFlight
from tests.fakes.engines import AlwaysRandom, NeverRandom


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_level_table_and_full_strength_hints() -> None:
    # The weakened table shipped in gameplay.yaml: (name, skill, think, depth, random-move chance).
    assert {key: (row.name, row.skill, row.think, row.depth, row.random_move_chance)
            for key, row in computer.LEVELS.items()} == {
        "beginner": ("Beginner", 0, 0.05, 1, 0.35), "casual": ("Casual", 2, 0.1, 3, 0.15),
        "club": ("Club", 6, 0.3, 6, 0.05), "strong": ("Strong", 11, 0.6, 10, 0.0),
        "maximum": ("Maximum", 16, 1.0, None, 0.0),
    }
    club = computer.reply_settings("club")
    assert (club.skill, club.think, club.depth) == (6, 0.3, 6)
    assert computer.hint_settings() == (20, 0.5)
    with pytest.raises(KeyError):
        computer.reply_settings("grandmaster")


def test_a_forced_random_roll_plays_a_legal_move_that_is_not_the_engines() -> None:
    board = chess.Board()
    board.push_uci("e2e4")
    engine_move = chess.Move.from_uci("a7a5")
    rng = AlwaysRandom()
    chosen = computer.maybe_randomise(board, engine_move, 0.35, rng)
    assert chosen in board.legal_moves and chosen != engine_move
    assert engine_move not in rng.choices[0] and len(rng.choices[0]) == board.legal_moves.count() - 1
    only = chess.Board("7k/8/8/8/8/8/6q1/7K w - - 0 1")  # the white king's one legal move: nothing else to pick
    forced = next(iter(only.legal_moves))
    assert computer.maybe_randomise(only, forced, 1.0, AlwaysRandom()) == forced


def test_a_zero_chance_never_randomises() -> None:
    board = chess.Board()
    engine_move = chess.Move.from_uci("e2e4")
    rng = AlwaysRandom()  # the roll is 0.0, the lowest possible: still no random move at chance 0
    assert all(computer.maybe_randomise(board, engine_move, 0, rng) == engine_move for _ in range(50))
    assert rng.choices == []
    assert computer.maybe_randomise(board, engine_move, 0.5, NeverRandom()) == engine_move


def test_the_flag_is_cleared_only_by_its_own_request() -> None:
    coordinator = ComputerCoordinator(Clock())
    coordinator.set_reply("ROOM01", ReplyInFlight(game_id=1, version=3, request_id=7))
    coordinator.set_reply("ROOM01", ReplyInFlight(game_id=2, version=0, request_id=8))  # a rematch replaces it
    assert coordinator.clear_reply("ROOM01", 7) is False
    assert coordinator.progress("ROOM01", 7, "thinking", None) is False
    assert coordinator.any_reply("ROOM01").request_id == 8
    assert coordinator.progress("ROOM01", 8, "queued", 2) is True
    assert (coordinator.any_reply("ROOM01").state, coordinator.any_reply("ROOM01").queue_position) == ("queued", 2)
    assert coordinator.clear_reply("ROOM01", 8) is True and coordinator.any_reply("ROOM01") is None


def test_run_reply_clears_the_flag_after_an_exception_and_after_cancellation() -> None:
    async def scenario():
        coordinator = ComputerCoordinator(Clock())

        async def broken():
            raise RuntimeError("engine said nonsense")

        failed = coordinator.run_reply("ROOM01", ReplyInFlight(1, 0, 1), broken)
        await asyncio.gather(failed, return_exceptions=True)
        after_failure = coordinator.any_reply("ROOM01")

        started = asyncio.Event()

        async def slow():
            started.set()
            await asyncio.sleep(10)

        cancelled = coordinator.run_reply("ROOM02", ReplyInFlight(1, 0, 2), slow)
        await started.wait()
        held = (coordinator.any_reply("ROOM02") is not None, len(coordinator.tasks))
        cancelled.cancel()
        await asyncio.gather(cancelled, return_exceptions=True)
        return after_failure, held, coordinator.any_reply("ROOM02"), len(coordinator.tasks)

    after_failure, held, after_cancel, tasks_left = asyncio.run(scenario())
    assert after_failure is None
    assert held == (True, 1), "the running task is held in the strong-reference set"
    assert after_cancel is None and tasks_left == 0


def test_a_finishing_old_reply_leaves_the_new_flag_alone() -> None:
    async def scenario():
        coordinator = ComputerCoordinator(Clock())
        release = asyncio.Event()

        async def old_search():
            await release.wait()

        old = coordinator.run_reply("ROOM01", ReplyInFlight(game_id=1, version=5, request_id=1), old_search)
        await asyncio.sleep(0)
        coordinator.set_reply("ROOM01", ReplyInFlight(game_id=2, version=0, request_id=2))
        release.set()
        await old
        return coordinator.any_reply("ROOM01")

    remaining = asyncio.run(scenario())
    assert remaining is not None and remaining.request_id == 2


def test_retry_backoff_blocks_for_five_seconds() -> None:
    clock = Clock()
    coordinator = ComputerCoordinator(clock)
    assert coordinator.in_backoff("ROOM01") is False
    coordinator.set_backoff("ROOM01")
    clock.now += 4.9
    assert coordinator.in_backoff("ROOM01") is True and coordinator.in_backoff("ROOM02") is False
    clock.now += 0.1
    assert coordinator.in_backoff("ROOM01") is False


def test_a_flag_from_an_earlier_game_does_not_block_the_current_game() -> None:
    coordinator = ComputerCoordinator(Clock())
    coordinator.set_reply("ROOM01", ReplyInFlight(game_id=1, version=4, request_id=3, state="thinking"))
    assert coordinator.reply_for("ROOM01", 1) is not None
    assert coordinator.reply_for("ROOM01", 2) is None
    assert coordinator.begin_hint("ROOM01") is True and coordinator.begin_hint("ROOM01") is False
    coordinator.end_hint("ROOM01")
    assert coordinator.hint_pending("ROOM01") is False


def test_computer_state_for_the_snapshot() -> None:
    up = {"available": True, "reason": None}
    down = {"available": False, "reason": "The computer stopped working"}
    queued = ReplyInFlight(1, 2, 3, state="queued", queue_position=2)
    thinking = ReplyInFlight(1, 2, 3, state="thinking")
    assert computer.computer_state("club", up, None) == {
        "state": "idle", "queuePosition": None, "reason": None, "level": "club", "available": True, "message": None}
    assert computer.computer_state("club", up, queued)["queuePosition"] == 2
    assert computer.computer_state("club", up, thinking)["state"] == "thinking"
    unavailable = computer.computer_state("club", down, None)
    assert (unavailable["state"], unavailable["reason"], unavailable["available"]) == (
        "unavailable", "The computer stopped working", False)
    assert computer.computer_state("club", up, None, message="busy")["message"] == "busy"
