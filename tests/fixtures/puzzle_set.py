"""A small puzzle folder for tests (P2 U5): two hand-built puzzles per theme.

These positions were built for the tests and checked with python-chess; they
are not Lichess puzzles and are never shipped. The mate puzzles really are
mates; the fork, pin, skewer and discovered-attack entries only need to be
legal for the loader (the loader does not judge the tactic), so they share two
knight-fork positions under different ids.

* ``mateIn1`` ``Rk001``: 1...a6 then Rd8# (Re8# also mates: the "alternative
  mate" case). It has the lowest rating, so it is the first mate-in-1.
* ``mateIn1`` ``Fo001``: Fool's mate, played as Black (2.g4 Qh4#).
* ``mateIn2`` ``Bk001``: 1...a6 2.Qd8+ Rxd8 3.Rxd8# (correct, reply, solved).
* ``mateIn2`` ``Bk002``: the same idea for Black.
"""

from __future__ import annotations

import json
from pathlib import Path

FORK_FEN = "r3k3/pp3ppp/8/3N4/8/8/PP3PPP/6K1 b - - 0 1"
FORK_TWO = ["h7h6", "d5c7", "e8d7", "c7a8"]
FORK_ONE = ["g7g6", "d5c7"]


def _pair(theme: str, prefix: str) -> list[dict]:
    return [
        {"id": f"{prefix}001", "theme": theme, "fen": FORK_FEN, "moves": FORK_ONE, "rating": 1100},
        {"id": f"{prefix}002", "theme": theme, "fen": FORK_FEN, "moves": FORK_TWO, "rating": 1300},
    ]


PUZZLES: dict[str, list[dict]] = {
    "fork": _pair("fork", "Fk"),
    "pin": _pair("pin", "Pn"),
    "skewer": _pair("skewer", "Sk"),
    "discoveredAttack": _pair("discoveredAttack", "Da"),
    "mateIn1": [
        {"id": "Fo001", "theme": "mateIn1", "fen": "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2",
         "moves": ["g2g4", "d8h4"], "rating": 900},
        {"id": "Rk001", "theme": "mateIn1", "fen": "6k1/p4ppp/8/8/8/8/5PPP/3RR1K1 b - - 0 1",
         "moves": ["a7a6", "d1d8"], "rating": 600},
    ],
    "mateIn2": [
        {"id": "Bk001", "theme": "mateIn2", "fen": "2r3k1/p4ppp/8/8/8/8/P2Q1PPP/3R2K1 b - - 0 1",
         "moves": ["a7a6", "d2d8", "c8d8", "d1d8"], "rating": 1200},
        {"id": "Bk002", "theme": "mateIn2", "fen": "3r2k1/p2q1ppp/8/8/8/8/P4PPP/2R3K1 w - - 0 1",
         "moves": ["a2a3", "d7d1", "c1d1", "d8d1"], "rating": 1250},
    ],
}


def write_puzzle_dir(folder: Path, puzzles: dict[str, list[dict]] | None = None) -> Path:
    """Write one PuzzleSet file per theme into ``folder`` (created) and return it."""
    folder.mkdir(parents=True, exist_ok=True)
    for theme, items in (puzzles or PUZZLES).items():
        body = {"theme": theme, "source": "Lichess puzzle database (CC0)", "puzzles": items}
        (folder / f"{theme}.json").write_text(json.dumps(body), encoding="utf-8")
    (folder / "LICENSE.md").write_text("Test fixture puzzles.\n", encoding="utf-8")
    return folder
