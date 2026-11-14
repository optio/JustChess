"""Puzzles: the curated Lichess tactics set loaded from puzzles/*.json (P2 U5, BR2.1, BR2.4).

The folder holds one ``<theme>.json`` per theme (``fork``, ``pin``, ``skewer``,
``discoveredAttack``, ``mateIn1``, ``mateIn2``) in the PuzzleSet shape
``{theme, source, puzzles: [...]}``, plus ``LICENSE.md`` with the CC0 credit.
The folder is ``JUSTCHESS_PUZZLES_DIR`` when set, else ``puzzles/`` at the
project root. Files are written once by ``scripts/curate_puzzles.py``.

One puzzle is ``{id, theme, fen, moves, rating}`` exactly as Lichess gives it:
``fen`` is the position BEFORE the opponent's set-up move ``moves[0]``; the
player then plays ``moves[1]``, the opponent ``moves[2]``, and so on, so the
list always ends with a player move.

``validate_puzzle`` is the one validator, shared with the curation script so
only puzzles that pass it are ever sampled (BR2.1):

* the theme matches its file, the id is a Lichess id, the rating is in range;
* the FEN is a legal position and every move is legal in order;
* ``mateIn1`` and ``mateIn2`` end in checkmate;
* the player-move count is 1 for ``mateIn1``, 2 for ``mateIn2``, 1..4 otherwise.

Loading never raises for bad data: a failing puzzle is skipped with one
warning naming its id, a file that cannot be read or parsed is skipped as a
whole, and a missing folder gives an empty, "not installed" catalog. The
catalog is built once (at app start) and kept in memory, sorted by rating.
Files are only listed, never opened by a name taken from a request.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess

logger = logging.getLogger("justchess.puzzles")

THEMES = ("fork", "pin", "skewer", "discoveredAttack", "mateIn1", "mateIn2")
THEME_LABELS = {
    "fork": "Forks",
    "pin": "Pins",
    "skewer": "Skewers",
    "discoveredAttack": "Discovered attacks",
    "mateIn1": "Mate in 1",
    "mateIn2": "Mate in 2",
}
MATE_PLAYER_MOVES = {"mateIn1": 1, "mateIn2": 2}
MAX_PLAYER_MOVES = 4
PUZZLE_ID = re.compile(r"^[0-9A-Za-z]{5}$")
UCI_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
FEN_MAX = 100
RATING_MIN, RATING_MAX = 400, 3000
MAX_FILE_BYTES = 2 * 1024 * 1024
PUZZLE_FIELDS = frozenset({"id", "theme", "fen", "moves", "rating"})
SOURCE = "Lichess puzzle database (CC0)"
ENV_PUZZLES_DIR = "JUSTCHESS_PUZZLES_DIR"


class PuzzleError(ValueError):
    """A puzzle (or a request about one) broke a rule; the message says which."""


# --- validation (BR2.1) ---------------------------------------------------------

def is_theme(value: Any) -> bool:
    """True for one of the six shipped themes."""
    return isinstance(value, str) and value in THEMES


def _board(fen: Any) -> chess.Board:
    if not isinstance(fen, str) or not fen.strip() or len(fen) > FEN_MAX:
        raise PuzzleError("fen must be a FEN")
    try:
        board = chess.Board(fen.strip())
    except ValueError:
        raise PuzzleError("fen is not a valid FEN") from None
    if not board.is_valid():
        raise PuzzleError("fen is not a legal position")
    return board


def _replay(board: chess.Board, moves: Any) -> chess.Board:
    """Play every move in order on a copy of ``board``; raise PuzzleError for a bad or illegal one."""
    if not isinstance(moves, list) or len(moves) < 2:
        raise PuzzleError("moves must be a list of at least 2 UCI moves")
    board = board.copy(stack=False)
    for index, uci in enumerate(moves):
        if not isinstance(uci, str) or not UCI_PATTERN.fullmatch(uci):
            raise PuzzleError(f"move {index + 1} is not a UCI move")
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise PuzzleError(f"move {index + 1} ({uci}) is illegal")
        board.push(move)
    return board


def _check_player_moves(theme: str, moves: list) -> None:
    if len(moves) % 2:
        raise PuzzleError("the move list must end with a player move")
    count = len(moves) // 2
    expected = MATE_PLAYER_MOVES.get(theme)
    if expected is not None and count != expected:
        raise PuzzleError(f"{theme} needs {expected} player move(s), found {count}")
    if expected is None and not 1 <= count <= MAX_PLAYER_MOVES:
        raise PuzzleError(f"{theme} needs 1 to {MAX_PLAYER_MOVES} player moves, found {count}")


def validate_puzzle(data: Any, theme: str) -> dict[str, Any]:
    """Check one puzzle for the file of ``theme`` and return it normalised; raise PuzzleError."""
    if not isinstance(data, dict):
        raise PuzzleError("a puzzle must be a mapping of fields")
    unknown = sorted(str(key) for key in data if key not in PUZZLE_FIELDS)
    if unknown:
        raise PuzzleError(f"unknown field '{unknown[0]}'")
    puzzle_id = data.get("id")
    if not isinstance(puzzle_id, str) or not PUZZLE_ID.fullmatch(puzzle_id):
        raise PuzzleError("id must be a Lichess puzzle id (5 letters or digits)")
    if data.get("theme") != theme:
        raise PuzzleError(f"theme {data.get('theme')!r} does not match its file ({theme})")
    rating = data.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, int) or not RATING_MIN <= rating <= RATING_MAX:
        raise PuzzleError(f"rating must be a whole number from {RATING_MIN} to {RATING_MAX}")
    board = _board(data.get("fen"))
    moves = data.get("moves")
    final = _replay(board, moves)
    _check_player_moves(theme, moves)
    if theme in MATE_PLAYER_MOVES and not final.is_checkmate():
        raise PuzzleError(f"{theme} must end in checkmate")
    return {"id": puzzle_id, "theme": theme, "fen": board.fen(), "moves": list(moves), "rating": rating}


# --- catalog --------------------------------------------------------------------

@dataclass(frozen=True)
class PuzzleCatalog:
    """The loaded set: valid puzzles per theme (rating order), the skipped count, and whether the folder exists."""

    themes: dict[str, tuple[dict[str, Any], ...]] = field(default_factory=dict)
    skipped: int = 0
    installed: bool = False

    def theme_list(self) -> list[dict[str, Any]]:
        """W3 ``GET /api/puzzles``: ``[{theme, label, count}]`` in the fixed theme order; empty when not installed."""
        if not self.installed:
            return []
        return [{"theme": theme, "label": THEME_LABELS[theme], "count": len(self.themes.get(theme, ()))}
                for theme in THEMES]

    def puzzles(self, theme: str) -> tuple[dict[str, Any], ...] | None:
        """The puzzles of a theme in rating order, or None for an unknown theme."""
        if not is_theme(theme):
            return None
        return self.themes.get(theme, ())

    def get(self, theme: str, puzzle_id: str) -> dict[str, Any] | None:
        """One puzzle, or None. The id is only compared, never used as a path."""
        found = self.puzzles(theme)
        if not found or not isinstance(puzzle_id, str) or not PUZZLE_ID.fullmatch(puzzle_id):
            return None
        return next((puzzle for puzzle in found if puzzle["id"] == puzzle_id), None)


def default_puzzles_dir(root: Path) -> Path:
    """``JUSTCHESS_PUZZLES_DIR`` when set, else ``<root>/puzzles``."""
    configured = os.environ.get(ENV_PUZZLES_DIR, "").strip()
    return Path(configured) if configured else root / "puzzles"


def _read_json_file(path: Path) -> Any:
    """Read one regular theme file of at most MAX_FILE_BYTES; raise PuzzleError otherwise."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise PuzzleError(f"could not open the file ({error.strerror or type(error).__name__})") from None
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise PuzzleError("not a regular file")
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise PuzzleError("file too large")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PuzzleError(f"invalid JSON ({type(error).__name__})") from None


def _load_theme(path: Path, theme: str) -> tuple[list[dict[str, Any]], int]:
    """Valid puzzles of one file and the number skipped; raise PuzzleError when the whole file is unusable."""
    data = _read_json_file(path)
    if not isinstance(data, dict) or data.get("theme") != theme or not isinstance(data.get("puzzles"), list):
        raise PuzzleError("the file must hold {theme, source, puzzles} for its own theme")
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped = 0
    for index, item in enumerate(data["puzzles"]):
        label = item.get("id") if isinstance(item, dict) else None
        try:
            puzzle = validate_puzzle(item, theme)
            if puzzle["id"] in seen:
                raise PuzzleError("duplicate id in this file")
        except PuzzleError as error:
            skipped += 1
            logger.warning("Skipped puzzle %s in %s: %s", label if isinstance(label, str) else f"#{index + 1}",
                           path.name, error)
            continue
        seen.add(puzzle["id"])
        valid.append(puzzle)
    valid.sort(key=lambda puzzle: (puzzle["rating"], puzzle["id"]))
    return valid, skipped


def load_puzzles(directory: Path) -> PuzzleCatalog:
    """Load every theme file in ``directory``. Never raises for a bad file or folder."""
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning("The puzzles folder %s does not exist; puzzles are not installed", directory)
        return PuzzleCatalog({}, 0, False)
    themes: dict[str, tuple[dict[str, Any], ...]] = {}
    skipped = 0
    for theme in THEMES:
        path = directory / f"{theme}.json"
        if not path.exists():
            logger.warning("No puzzle file for %s in %s", theme, directory)
            continue
        try:
            valid, bad = _load_theme(path, theme)
        except (PuzzleError, OSError) as error:
            logger.warning("Skipped puzzle file %s: %s", path.name, error)
            continue
        themes[theme] = tuple(valid)
        skipped += bad
    total = sum(len(found) for found in themes.values())
    logger.info("Loaded %d puzzle(s) in %d theme(s) from %s, skipped %d", total, len(themes), directory, skipped)
    return PuzzleCatalog(themes, skipped, True)


# --- play (BR2.3, BR2.4) --------------------------------------------------------

HINT_LEVELS = ("piece", "move", "solution")
BAD_PLY = "Invalid ply"
BAD_LEVEL = "Invalid hint level"
ILLEGAL_MOVE = "Illegal move"


def _legal(board: chess.Board) -> list[str]:
    return sorted(move.uci() for move in board.legal_moves)


def public_detail(puzzle: dict[str, Any]) -> dict[str, Any]:
    """W3 detail: the start, the set-up move and the position after it; never the solution.

    ``afterSetup``, ``legalMoves`` and ``check`` let the browser draw and move
    without a chess engine (as lessons do); ``side`` is the player's colour.
    """
    board = chess.Board(puzzle["fen"])
    board.push_uci(puzzle["moves"][0])
    return {
        "id": puzzle["id"], "theme": puzzle["theme"], "label": THEME_LABELS[puzzle["theme"]],
        "fen": puzzle["fen"], "setup": puzzle["moves"][0], "playerMoves": len(puzzle["moves"]) // 2,
        "rating": puzzle["rating"], "side": "white" if board.turn == chess.WHITE else "black",
        "afterSetup": board.fen(), "legalMoves": _legal(board), "check": board.is_check(),
    }


def _board_at(puzzle: dict[str, Any], ply: Any) -> chess.Board:
    """The position before the expected player move ``moves[ply]``; raise PuzzleError for a bad ply."""
    moves = puzzle["moves"]
    if isinstance(ply, bool) or not isinstance(ply, int) or ply % 2 != 1 or not 1 <= ply <= len(moves) - 1:
        raise PuzzleError(BAD_PLY)
    board = chess.Board(puzzle["fen"])
    for uci in moves[:ply]:
        board.push_uci(uci)
    return board


def check_move(puzzle: dict[str, Any], ply: Any, uci: Any) -> dict[str, Any]:
    """BR2.4: judge the player's move at ``ply``. Any checkmate counts as solved; a wrong answer leaks nothing."""
    board = _board_at(puzzle, ply)
    if not isinstance(uci, str) or not UCI_PATTERN.fullmatch(uci):
        raise PuzzleError(ILLEGAL_MOVE)
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise PuzzleError(ILLEGAL_MOVE)
    expected = uci == puzzle["moves"][ply]
    board.push(move)
    after = {"fen": board.fen(), "check": board.is_check()}
    if board.is_checkmate():
        return {"result": "solved", **after}
    if not expected:
        return {"result": "wrong"}
    if ply + 1 >= len(puzzle["moves"]):
        return {"result": "solved", **after}
    reply = puzzle["moves"][ply + 1]
    board.push_uci(reply)
    return {"result": "correct", **after, "reply": reply, "replyFen": board.fen(),
            "legalMoves": _legal(board), "replyCheck": board.is_check()}


def hint(puzzle: dict[str, Any], ply: Any, level: Any) -> dict[str, Any]:
    """BR2.4 hint route: ``piece`` -> {from}, ``move`` -> {uci}, ``solution`` -> {line, fens}."""
    board = _board_at(puzzle, ply)
    if level not in HINT_LEVELS:
        raise PuzzleError(BAD_LEVEL)
    expected = puzzle["moves"][ply]
    if level == "piece":
        return {"from": expected[:2]}
    if level == "move":
        return {"uci": expected}
    line = list(puzzle["moves"][ply:])
    fens = []
    for uci in line:
        board.push_uci(uci)
        fens.append(board.fen())
    return {"line": line, "fens": fens}


class PuzzleStore:
    """Holds the catalog, loaded once on first use (the app loads it at start-up)."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._catalog: PuzzleCatalog | None = None

    def catalog(self) -> PuzzleCatalog:
        """The loaded catalog; the folder is read only the first time."""
        current = self._catalog
        if current is not None:
            return current
        with self._lock:
            if self._catalog is None:
                self._catalog = load_puzzles(self.directory)
            return self._catalog
