"""Endgames: the hand-written endgame catalog and the attempt judge (P2 U6, BR1.1, BR1.2, BR2.1-BR2.6).

Catalog (BR1.1, BR1.2). The folder (``endgames/`` at the project root; tests
pass their own folder to ``create_app``) holds one YAML file per category:
``queen-mate.yaml``, ``rook-mate.yaml``, ``king-pawn.yaml`` and
``opposition.yaml``. Only those four names are opened; any other file is
ignored, and a position id from a request is only compared, never used to
build a path. One file looks like::

    positions:
      - id: queen-first-steps          # a-z, 0-9 and "-", 3 to 40 characters, unique across files
        title: First steps             # 1 to 60 characters
        fen: 8/8/8/4k3/8/8/8/3QK3 w - - 0 1
        goal: mate                     # mate | promote | draw
        hint: Bring your king up ...   # 1 to 200 characters, plain text, our own words

The category comes from the file name and the order from the file order.
Each position must be a legal position (``Board.is_valid``) that is not over,
with the player (the side to move) able to reach the goal: ``mate`` needs a
queen or a rook, ``promote`` needs a pawn, and the goal must suit the category
(mate for queen-mate and rook-mate; promote or draw for king-pawn and
opposition). A failing position is skipped with one warning naming its id, a
file that cannot be read is skipped whole, and a missing folder (or a folder
with no valid position) gives an empty catalog marked not installed. Fewer
than three valid positions in a category is logged. Loading never raises.

Judge (BR2.1-BR2.4, BR2.6). ``judge(board, goal, player_colour, player_moves,
limits)`` reads a board replayed from the start FEN and returns a ``Verdict``
(``playing``, ``passed`` or ``failed`` with a reason). ``needs_defender``
says when the engine must be asked for the defender's reply: only while the
attempt is playing, the defender is to move and has a legal move, so a
finished board never reaches the engine. ``replay`` validates a client move
list (UCI shape, legal in order, ends with a player move, at most
``max_plies``) and raises ``EndgameError`` with the 400 message.
"""

from __future__ import annotations

import logging
import os
import re
import stat
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import yaml

logger = logging.getLogger("justchess.endgames")

CATEGORIES = ("queen-mate", "rook-mate", "king-pawn", "opposition")
CATEGORY_LABELS = {"queen-mate": "Queen mate", "rook-mate": "Rook mate", "king-pawn": "King and pawn",
                   "opposition": "Opposition"}
GOALS = ("mate", "promote", "draw")
CATEGORY_GOALS = {"queen-mate": ("mate",), "rook-mate": ("mate",), "king-pawn": ("promote", "draw"),
                  "opposition": ("promote", "draw")}
POSITION_ID = re.compile(r"^[a-z0-9-]{3,40}$")
POSITION_FIELDS = frozenset({"id", "title", "fen", "goal", "hint"})
TITLE_MAX = 60
HINT_MAX = 200
FEN_MAX = 100
MIN_PER_CATEGORY = 3
MAX_FILE_BYTES = 256 * 1024
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class EndgameError(ValueError):
    """A position (or a request about one) broke a rule; the message says which."""


# --- positions (BR1.1) ----------------------------------------------------------

@dataclass(frozen=True)
class EndgamePosition:
    """One training position. ``order`` is its place in its category (1-based, from the file order)."""

    id: str
    category: str
    title: str
    fen: str
    goal: str
    hint: str
    order: int

    @property
    def player(self) -> chess.Color:
        """The player's colour: the side to move in the FEN."""
        return chess.Board(self.fen).turn


def _text(data: dict, key: str, limit: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EndgameError(f"{key} must be text")
    value = value.strip()
    if len(value) > limit:
        raise EndgameError(f"{key} must be at most {limit} characters")
    if CONTROL_CHARACTERS.search(value):
        raise EndgameError(f"{key} must be one line of plain text")
    return value


def _board(fen: Any) -> chess.Board:
    if not isinstance(fen, str) or not fen.strip() or len(fen) > FEN_MAX:
        raise EndgameError("fen must be a FEN")
    try:
        board = chess.Board(fen.strip())
    except ValueError:
        raise EndgameError("fen is not a valid FEN") from None
    if not board.is_valid():
        raise EndgameError("fen is not a legal position")
    if board.is_game_over(claim_draw=True):
        raise EndgameError("the position is already over")
    return board


def _check_material(board: chess.Board, goal: str) -> None:
    player = board.turn
    if goal == "mate" and not (board.pieces(chess.QUEEN, player) or board.pieces(chess.ROOK, player)):
        raise EndgameError("a mate goal needs a queen or a rook for the side to move")
    if goal == "promote" and not board.pieces(chess.PAWN, player):
        raise EndgameError("a promote goal needs a pawn for the side to move")


def validate_position(data: Any, category: str, order: int) -> EndgamePosition:
    """Check one position of the file of ``category`` and return it; raise EndgameError."""
    if not isinstance(data, dict):
        raise EndgameError("a position must be a mapping of fields")
    unknown = sorted(str(key) for key in data if key not in POSITION_FIELDS)
    if unknown:
        raise EndgameError(f"unknown field '{unknown[0]}'")
    position_id = data.get("id")
    if not isinstance(position_id, str) or not POSITION_ID.fullmatch(position_id):
        raise EndgameError("id must be 3 to 40 lower-case letters, digits or hyphens")
    goal = data.get("goal")
    if goal not in GOALS:
        raise EndgameError(f"goal must be one of {', '.join(GOALS)}")
    if goal not in CATEGORY_GOALS[category]:
        raise EndgameError(f"goal {goal} does not suit the {category} category")
    title = _text(data, "title", TITLE_MAX)
    hint = _text(data, "hint", HINT_MAX)
    board = _board(data.get("fen"))
    _check_material(board, goal)
    return EndgamePosition(position_id, category, title, board.fen(), goal, hint, order)


# --- catalog --------------------------------------------------------------------

@dataclass(frozen=True)
class EndgameCatalog:
    """All valid positions (category order, then file order), the skipped count and whether it is installed."""

    positions: tuple[EndgamePosition, ...] = ()
    installed: bool = False
    skipped: int = 0
    _by_id: dict[str, EndgamePosition] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._by_id.update({position.id: position for position in self.positions})

    def get(self, position_id: Any) -> EndgamePosition | None:
        """One position, or None. The id is only compared, never used as a path."""
        if not isinstance(position_id, str) or not POSITION_ID.fullmatch(position_id):
            return None
        return self._by_id.get(position_id)

    def in_category(self, category: str) -> list[EndgamePosition]:
        return [position for position in self.positions if position.category == category]

    def place_of(self, position: EndgamePosition) -> tuple[int, int]:
        """(index, count): the position's 1-based place in its category and the category's size."""
        siblings = self.in_category(position.category)
        return siblings.index(position) + 1, len(siblings)

    def next_of(self, position: EndgamePosition) -> str:
        """The id of the next position in catalog order, wrapping round to the first."""
        index = self.positions.index(position)
        return self.positions[(index + 1) % len(self.positions)].id

    def categories(self) -> list[dict[str, Any]]:
        """BR3.1: ``[{id, label, positions: [{id, title, goal, order}]}]`` in the fixed category order."""
        if not self.installed:
            return []
        return [{"id": category, "label": CATEGORY_LABELS[category],
                 "positions": [{"id": p.id, "title": p.title, "goal": p.goal, "order": p.order}
                               for p in self.in_category(category)]}
                for category in CATEGORIES]


def default_endgames_dir(root: Path) -> Path:
    """``<root>/endgames`` (there is no environment setting for this folder)."""
    return Path(root) / "endgames"


def _read_yaml_file(path: Path) -> Any:
    """Read one regular category file of at most MAX_FILE_BYTES as YAML; raise EndgameError otherwise."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise EndgameError(f"could not open the file ({error.strerror or type(error).__name__})") from None
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise EndgameError("not a regular file")
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise EndgameError("file too large")
    try:
        return yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise EndgameError(f"invalid YAML ({type(error).__name__})") from None


def _load_category(path: Path, category: str, seen: set[str]) -> tuple[list[EndgamePosition], int]:
    """Valid positions of one file and the number skipped; raise EndgameError when the whole file is unusable."""
    data = _read_yaml_file(path)
    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        raise EndgameError("the file must hold a 'positions' list")
    valid: list[EndgamePosition] = []
    skipped = 0
    for index, item in enumerate(data["positions"]):
        label = item.get("id") if isinstance(item, dict) else None
        try:
            position = validate_position(item, category, len(valid) + 1)
            if position.id in seen:
                raise EndgameError("duplicate id")
        except EndgameError as error:
            skipped += 1
            logger.warning("Skipped endgame position %s in %s: %s",
                           label if isinstance(label, str) else f"#{index + 1}", path.name, error)
            continue
        seen.add(position.id)
        valid.append(position)
    return valid, skipped


def load_catalog(folder: Path) -> EndgameCatalog:
    """Load the four category files of ``folder``. Never raises for a bad file or folder."""
    folder = Path(folder)
    if not folder.is_dir():
        logger.warning("The endgames folder %s does not exist; endgame positions are not installed", folder)
        return EndgameCatalog((), False, 0)
    positions: list[EndgamePosition] = []
    seen: set[str] = set()
    skipped = 0
    for category in CATEGORIES:
        path = folder / f"{category}.yaml"
        if not path.exists():
            logger.warning("No endgame file for %s in %s", category, folder)
            continue
        try:
            valid, bad = _load_category(path, category, seen)
        except (EndgameError, OSError) as error:
            logger.warning("Skipped endgame file %s: %s", path.name, error)
            continue
        positions.extend(valid)
        skipped += bad
    for category, count in summarise(positions).items():
        if count < MIN_PER_CATEGORY:
            logger.warning("Only %d valid endgame position(s) for %s (at least %d expected)",
                           count, category, MIN_PER_CATEGORY)
    logger.info("Loaded %d endgame position(s) from %s, skipped %d", len(positions), folder, skipped)
    return EndgameCatalog(tuple(positions), bool(positions), skipped)


class EndgameStore:
    """Holds the catalog, loaded once on first use (the app loads it at start-up)."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._catalog: EndgameCatalog | None = None

    def catalog(self) -> EndgameCatalog:
        """The loaded catalog; the folder is read only the first time."""
        current = self._catalog
        if current is not None:
            return current
        with self._lock:
            if self._catalog is None:
                self._catalog = load_catalog(self.directory)
            return self._catalog


def summarise(positions: Iterable[EndgamePosition]) -> dict[str, int]:
    """How many positions each category holds (used by the content checks and the start-up log)."""
    counts = {category: 0 for category in CATEGORIES}
    for position in positions:
        counts[position.category] += 1
    return counts


# --- the attempt: replay and judge (BR2.1-BR2.4, BR2.6, BR3.2) --------------------

PLAYING, PASSED, FAILED = "playing", "passed", "failed"
UCI_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
INVALID_MOVES = "Invalid moves"
MUST_END_WITH_PLAYER = "The moves must end with your move"
TOO_LONG = "This attempt is too long; start again"
DEFAULT_HOLD_MOVES = 30  # fallbacks for direct calls; the app passes gameplay.yaml's endgames values
DEFAULT_MAX_PLIES = 300


@dataclass(frozen=True)
class JudgeLimits:
    """What the judge needs from the settings (gameplay.EndgameSettings has the same two fields)."""

    hold_moves: int = DEFAULT_HOLD_MOVES
    max_plies: int = DEFAULT_MAX_PLIES


@dataclass(frozen=True)
class Verdict:
    """The answer to one judging: status, reason (or None while playing), player moves and, for draw, moves left."""

    status: str
    reason: str | None
    player_moves: int
    moves_left: int | None = None


def illegal_move(index: int) -> str:
    """400 text naming the move by its 1-based place in the list."""
    return f"Illegal move (move {index + 1})"


def replay(position: EndgamePosition, moves: Any, max_plies: int = DEFAULT_MAX_PLIES) -> chess.Board:
    """BR3.2/BR2.4: the board after ``moves`` from the start FEN; raise EndgameError with the 400 text.

    ``moves`` must be a list of 1 to ``max_plies`` UCI strings, legal in order,
    ending with a player move (odd length). Only this replayed board, never
    client text, reaches the engine.
    """
    if not isinstance(moves, list) or not moves:
        raise EndgameError(INVALID_MOVES)
    if len(moves) > max_plies:
        raise EndgameError(TOO_LONG)
    if len(moves) % 2 == 0:
        raise EndgameError(MUST_END_WITH_PLAYER)
    board = chess.Board(position.fen)
    for index, uci in enumerate(moves):
        if not isinstance(uci, str) or not UCI_PATTERN.fullmatch(uci):
            raise EndgameError(illegal_move(index))
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise EndgameError(illegal_move(index))
        board.push(move)
    return board


def player_moves_in(moves: list) -> int:
    """The player's moves in a list that starts with a player move (even indexes)."""
    return (len(moves) + 1) // 2


def draw_reason(board: chess.Board) -> str | None:
    """A draw by the rules, by its specific kind, or None (BR2.1: is_repetition(3), is_fifty_moves())."""
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "insufficient_material"
    if board.is_repetition(3):
        return "threefold_repetition"
    if board.is_fifty_moves():
        return "fifty_moves"
    return None


def _mated(board: chess.Board, player: chess.Color) -> str | None:
    """'defender' or 'player' when the side to move is checkmated, else None."""
    if not board.is_checkmate():
        return None
    return "player" if board.turn == player else "defender"


def _judge_mate(board: chess.Board, player: chess.Color) -> tuple[str, str | None]:
    """BR2.1."""
    mated = _mated(board, player)
    if mated == "defender":
        return PASSED, "checkmate"
    if mated == "player":
        return FAILED, "player_mated"
    draw = draw_reason(board)
    return (FAILED, draw) if draw else (PLAYING, None)


def _judge_promote(board: chess.Board, player: chess.Color) -> tuple[str, str | None]:
    """BR2.2: a promotion counts only as the player's own last move."""
    last = board.peek() if board.move_stack else None
    if last is not None and board.turn != player and last.promotion:
        return PASSED, "promoted"
    mated = _mated(board, player)
    if mated == "defender":
        return PASSED, "checkmate"
    if mated == "player":
        return FAILED, "player_mated"
    if not board.pieces(chess.PAWN, player):
        return FAILED, "pawns_lost"
    draw = draw_reason(board)
    return (FAILED, draw) if draw else (PLAYING, None)


def _judge_draw(board: chess.Board, player: chess.Color, player_moves: int, hold_moves: int) -> tuple[str, str | None]:
    """BR2.3: held once the defender has answered the hold_moves-th player move without mating."""
    mated = _mated(board, player)
    if mated == "defender":
        return PASSED, "checkmate"
    if mated == "player":
        return FAILED, "player_mated"
    draw = draw_reason(board)
    if draw:
        return PASSED, draw
    if player_moves >= hold_moves and board.turn == player:
        return PASSED, "held_moves"
    return PLAYING, None


_TERMINATION_REASONS = {
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.SEVENTYFIVE_MOVES: "fifty_moves",
    chess.Termination.FIVEFOLD_REPETITION: "threefold_repetition",
    chess.Termination.FIFTY_MOVES: "fifty_moves",
    chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
}


def _finished_reason(board: chess.Board, player: chess.Color) -> str | None:
    """BR2.6 catch-all: the end of a board that is over (or has no legal move), else None.

    "Over" means a draw already reached, not one that could be claimed on the
    next move: a position the side to move can still steer away from is played on.
    """
    if board.is_checkmate():
        return "player_mated" if board.turn == player else "checkmate"
    outcome = board.outcome(claim_draw=False)
    if outcome is not None:
        return _TERMINATION_REASONS.get(outcome.termination, "stalemate")
    if not any(board.legal_moves):
        return "stalemate"
    return None


def judge(board: chess.Board, goal: str, player_colour: chess.Color, player_moves: int,
          limits: JudgeLimits | Any = JudgeLimits()) -> Verdict:
    """BR2.1-BR2.4, BR2.6: judge the replayed board for ``goal``.

    The goal rules decide first. A board that is still over after them (a
    finished board no goal rule named) fails with its end as the reason, so it
    never goes to the engine; an attempt still playing at ``max_plies`` plies
    fails as ``too_long``. ``moves_left`` is set for the draw goal only.
    """
    if goal == "mate":
        status, reason = _judge_mate(board, player_colour)
    elif goal == "promote":
        status, reason = _judge_promote(board, player_colour)
    elif goal == "draw":
        status, reason = _judge_draw(board, player_colour, player_moves, limits.hold_moves)
    else:
        raise EndgameError(f"unknown goal {goal!r}")
    if status == PLAYING:
        finished = _finished_reason(board, player_colour)
        if finished:
            status, reason = FAILED, finished
        elif len(board.move_stack) >= limits.max_plies:
            status, reason = FAILED, "too_long"
    moves_left = max(0, limits.hold_moves - player_moves) if goal == "draw" else None
    return Verdict(status, reason, player_moves, moves_left)


def needs_defender(board: chess.Board, verdict: Verdict, player_colour: chess.Color) -> bool:
    """BR2.6: ask the engine only while playing, with the defender to move and a legal move for it."""
    return verdict.status == PLAYING and board.turn != player_colour and any(board.legal_moves)
