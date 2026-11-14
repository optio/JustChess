"""P2 U4 with the real Stockfish (NFR1, BR2.1, BR2.2). Skipped with the reason when no binary is found.

The binary is found the way the app finds it (``STOCKFISH_PATH``, the PATH,
then the app's own install in ``.engines/``); nothing is downloaded and the
binary is never changed. ``test_maximum_reply_within_three_seconds`` is also
the NFR1 timing check when it runs on the Raspberry Pi.
"""

from __future__ import annotations

import asyncio
import os
import shutil

import chess
import pytest

from justchess import computer
from justchess.api import DEFAULT_ENGINE_DIR
from justchess.engine import Engine
import stockfish_install


def stockfish_path():
    found = stockfish_install.resolve_existing(os.environ, shutil.which, DEFAULT_ENGINE_DIR)
    if found is None:
        pytest.skip("no Stockfish binary found (STOCKFISH_PATH, PATH or .engines/), so the real-engine tests cannot run")
    return found[0]


def test_maximum_reply_within_three_seconds() -> None:
    path = stockfish_path()

    async def scenario():
        engine = Engine()
        await engine.start(path)
        assert engine.available, engine.reason
        board = chess.Board()
        for uci in ("e2e4", "e7e5", "g1f3"):
            board.push_uci(uci)
        loop = asyncio.get_running_loop()
        began = loop.time()
        level = computer.reply_settings("maximum")
        move = await engine.submit(board, level.skill, level.think, depth=level.depth).result()
        elapsed = loop.time() - began
        await engine.stop()
        return board, move, elapsed

    board, move, elapsed = asyncio.run(scenario())
    assert move in board.legal_moves
    assert elapsed < 3.0, f"the Maximum reply took {elapsed:.2f} s (NFR1: within 3 s)"


def test_a_hint_returns_a_legal_move() -> None:
    path = stockfish_path()

    async def scenario():
        engine = Engine()
        await engine.start(path)
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 4")
        move = await engine.submit(board, *computer.hint_settings()).result()
        await engine.stop()
        return board, move

    board, move = asyncio.run(scenario())
    assert move in board.legal_moves
    assert move == chess.Move.from_uci("h5f7"), "full strength finds the mate in one"
