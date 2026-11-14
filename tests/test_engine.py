"""P2 U4 Engine against the fake UCI engine (BR1.1-BR1.5): queue order, the cap, crashes, overruns, shutdown.

Every test runs its own event loop with ``asyncio.run`` and starts
``tests/fakes/fake_uci.py`` processes; think times are 0.05 s and the overrun
grace is shortened, so no test waits seconds.
"""

from __future__ import annotations

import asyncio

import chess
import chess.engine
import pytest

from justchess import engine as engine_module
from justchess.engine import Engine, EngineBusy, EngineFailure, EngineUnavailable
from tests.fakes.engines import fake_opener

THINK = 0.05


def board_after(*ucis: str) -> chess.Board:
    board = chess.Board()
    for uci in ucis:
        board.push_uci(uci)
    return board


async def started(opener, **options) -> Engine:
    engine = Engine(opener, **options)
    await engine.start("fake")
    assert engine.available, engine.reason
    return engine


def test_requests_are_served_in_order_with_their_positions() -> None:
    async def scenario():
        engine = await started(fake_opener(["--delay", "0.15"]))
        done, events = [], {1: [], 2: [], 3: []}
        tickets = []
        for number, board in enumerate((board_after("e2e4"), board_after("d2d4"), board_after("c2c4")), start=1):
            ticket = engine.submit(board, 5, THINK, lambda state, pos, n=number: events[n].append((state, pos)))
            tickets.append(ticket)
        assert [(t.state, t.queue_position) for t in tickets] == [("thinking", None), ("queued", 1), ("queued", 2)]
        assert engine.queued_count() == 3  # the worker has not picked the first one up yet

        async def wait(number, ticket):
            move = await ticket.result()
            done.append(number)
            return move

        moves = await asyncio.gather(*(wait(n, t) for n, t in enumerate(tickets, start=1)))
        await engine.stop()
        return done, events, moves

    done, events, moves = asyncio.run(scenario())
    assert done == [1, 2, 3]
    assert events[1] == [("thinking", None)]
    assert events[2] == [("thinking", None)]
    assert events[3] == [("queued", 1), ("thinking", None)]
    assert [move.uci() for move in moves] == ["a7a5", "a7a5", "a7a5"]  # the fake's first legal move in UCI order


def test_only_one_search_runs_at_a_time(tmp_path) -> None:
    log = tmp_path / "uci.log"

    async def scenario():
        engine = await started(fake_opener(["--delay", "0.05", "--log", str(log)]))
        tickets = [engine.submit(board_after(), 0, THINK) for _ in range(4)]
        running = []

        async def sample():
            while not all(t._request.future.done() for t in tickets):
                running.append(engine.busy)
                await asyncio.sleep(0.01)

        await asyncio.gather(sample(), *(t.result() for t in tickets))
        await engine.stop()
        return running

    running = asyncio.run(scenario())
    assert True in running
    commands = [line.split()[0] for line in log.read_text().splitlines() if line.split()[:1] in (["go"], ["bestmove"])]
    assert commands == ["go", "bestmove"] * 4, "every search ends before the next one starts"


def test_a_level_depth_limit_reaches_the_engine(tmp_path) -> None:
    log = tmp_path / "uci.log"

    async def scenario():
        engine = await started(fake_opener(["--log", str(log)]))
        await engine.submit(board_after(), 0, THINK, depth=3).result()
        await engine.submit(board_after(), 20, THINK).result()
        await engine.stop()

    asyncio.run(scenario())
    goes = [line.split() for line in log.read_text().splitlines() if line.startswith("go ")]
    assert len(goes) == 2
    assert "depth" in goes[0] and goes[0][goes[0].index("depth") + 1] == "3"
    assert "movetime" in goes[0], "the think time still applies"
    assert "depth" not in goes[1], "no depth limit unless the level has one"
    assert engine_module.search_limit(0.5) == chess.engine.Limit(time=0.5)


def test_the_queue_cap_refuses_with_busy() -> None:
    async def scenario():
        engine = await started(fake_opener(["--delay", "5"]))
        running = engine.submit(board_after(), 0, THINK)
        await asyncio.sleep(0.05)  # the first request is now the running search
        waiting = [engine.submit(board_after(), 0, THINK) for _ in range(engine_module.MAX_QUEUE)]
        with pytest.raises(EngineBusy) as busy:
            engine.submit(board_after(), 0, THINK)
        queued = engine.queued_count()
        await engine.stop()
        results = await asyncio.gather(running.result(), *(t.result() for t in waiting), return_exceptions=True)
        return busy.value, queued, waiting, results

    busy, queued, waiting, results = asyncio.run(scenario())
    assert busy.reason == "The computer is busy, try again in a moment"
    assert queued == 32 and waiting[-1].queue_position == 32
    assert all(isinstance(result, EngineFailure) for result in results)


def test_a_crash_fails_the_running_request_restarts_and_the_queue_continues() -> None:
    async def scenario():
        opener = fake_opener(["--crash-on-go", "1"], [])
        engine = await started(opener)
        first = engine.submit(board_after(), 0, THINK)
        second = engine.submit(board_after("e2e4"), 0, THINK)
        results = await asyncio.gather(first.result(), second.result(), return_exceptions=True)
        state = (engine.available, engine.restarts_used, opener.launches)
        await engine.stop()
        return results, state

    (failed, move), state = asyncio.run(scenario())
    assert isinstance(failed, EngineFailure) and failed.reason == "The computer stopped working"
    assert move == chess.Move.from_uci("a7a5")
    assert state == (True, 1, 2)


def test_a_second_crash_makes_the_engine_unavailable_and_fails_the_queue() -> None:
    async def scenario():
        engine = await started(fake_opener(["--crash-on-go", "1"]))
        tickets = [engine.submit(board_after(), 0, THINK) for _ in range(3)]
        results = await asyncio.gather(*(t.result() for t in tickets), return_exceptions=True)
        with pytest.raises(EngineUnavailable) as refused:
            engine.submit(board_after(), 0, THINK)
        status = engine.status()
        await engine.stop()
        return results, refused.value, status

    results, refused, status = asyncio.run(scenario())
    assert all(isinstance(r, EngineFailure) and r.reason == "The computer stopped working" for r in results)
    assert refused.reason == "The computer stopped working"
    assert status == {"available": False, "reason": "The computer stopped working"}


def test_the_restart_count_comes_from_the_settings() -> None:
    async def scenario():
        engine = await started(fake_opener(["--crash-on-go", "1"], []), restarts=0)
        ticket = engine.submit(board_after(), 0, THINK)
        failed = await asyncio.gather(ticket.result(), return_exceptions=True)
        status = engine.status()
        await engine.stop()
        return failed[0], status

    failed, status = asyncio.run(scenario())
    assert isinstance(failed, EngineFailure)
    assert status == {"available": False, "reason": "The computer stopped working"}, "no restart allowed"


def test_a_search_past_think_plus_grace_counts_as_a_crash() -> None:
    async def scenario():
        engine = await started(fake_opener(["--hang"], []), grace=0.2)
        loop = asyncio.get_running_loop()
        began = loop.time()
        hung = engine.submit(board_after(), 0, THINK)
        after = engine.submit(board_after(), 0, THINK)
        results = await asyncio.gather(hung.result(), after.result(), return_exceptions=True)
        elapsed = loop.time() - began
        restarts = engine.restarts_used
        await engine.stop()
        return results, elapsed, restarts

    (failed, move), elapsed, restarts = asyncio.run(scenario())
    assert isinstance(failed, EngineFailure)
    assert isinstance(move, chess.Move)
    assert restarts == 1
    assert elapsed < 3.0, "the overrun is cut at think + grace, not left hanging"


def test_an_illegal_engine_move_is_a_failure_not_a_crash() -> None:
    async def scenario():
        engine = await started(fake_opener(["--illegal"]))
        ticket = engine.submit(board_after("e2e4"), 0, THINK)
        with pytest.raises(EngineFailure) as failed:
            await ticket.result()
        state = (engine.available, engine.restarts_used)
        await engine.stop()
        return failed.value, state

    failed, state = asyncio.run(scenario())
    assert failed.reason == "The computer did not find a legal move"
    assert state == (True, 0)


def test_stop_fails_queued_requests_and_ends_the_process() -> None:
    async def scenario():
        engine = await started(fake_opener(["--delay", "3"]))
        transport = engine._transport
        tickets = [engine.submit(board_after(), 0, THINK) for _ in range(2)]
        await asyncio.sleep(0.05)
        loop = asyncio.get_running_loop()
        began = loop.time()
        await engine.stop()
        stop_seconds = loop.time() - began
        results = await asyncio.gather(*(t.result() for t in tickets), return_exceptions=True)
        for _ in range(50):
            if transport.get_returncode() is not None:
                break
            await asyncio.sleep(0.02)
        return results, stop_seconds, transport.get_returncode(), engine.status()

    results, stop_seconds, returncode, status = asyncio.run(scenario())
    assert all(isinstance(r, EngineFailure) and r.reason == "The computer is shutting down" for r in results)
    assert returncode is not None
    assert stop_seconds < 2.5
    assert status["available"] is False


def test_start_up_states_starting_missing_and_failed_open() -> None:
    async def scenario():
        starting = Engine(fake_opener([]))
        before = starting.status()
        missing = Engine(fake_opener([]))
        missing.mark_missing()
        broken = Engine(fake_opener(["--fail-open"]))
        await broken.start("fake")
        return before, missing.status(), broken.status()

    before, missing, broken = asyncio.run(scenario())
    assert before == {"available": False, "reason": "The computer is starting"}
    assert missing == {"available": False, "reason": "No chess engine is installed"}
    assert broken == {"available": False, "reason": "The computer could not be started"}
