"""Openers that start ``fake_uci.py`` for the U4 tests, one flag list per process launch.

    opener = fake_opener(["--crash-on-go", "1"], [])   # first launch crashes on its first go, the restart is healthy
    engine = Engine(opener)

The last flag list is reused for any further launch. ``launches`` counts the
processes started. The path the Engine passes is ignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

import chess.engine

FAKE_UCI = Path(__file__).with_name("fake_uci.py")


class FakeOpener:
    def __init__(self, *launches: list[str]) -> None:
        self.flags = [list(flags) for flags in launches] or [[]]
        self.launches = 0

    async def __call__(self, _path: str):
        flags = self.flags[min(self.launches, len(self.flags) - 1)]
        self.launches += 1
        return await chess.engine.popen_uci([sys.executable, str(FAKE_UCI), *flags])


def fake_opener(*launches: list[str]) -> FakeOpener:
    return FakeOpener(*launches)


class NeverRandom:
    """A move chooser whose roll never falls under a level's random-move chance (the engine's move always stands)."""

    def random(self) -> float:
        return 1.0

    def choice(self, seq):
        raise AssertionError("NeverRandom never chooses a random move")


class AlwaysRandom:
    """A move chooser whose roll is always 0.0 (under any chance above 0) and that picks the last candidate."""

    def __init__(self) -> None:
        self.choices: list[list] = []

    def random(self) -> float:
        return 0.0

    def choice(self, seq):
        self.choices.append(list(seq))
        return seq[-1]
