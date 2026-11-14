"""Analysis (U4): is a candidate move a blunder? Pure, no I/O, python-chess only.

``analyse(board, move, *, budget_ms=250) -> BlunderWarning | None`` judges one
legal move for the side to move (the "mover") and implements BR1.1-BR1.5 of
the u4-blunder-warnings functional design, with the design review decisions
recorded in its code generation plan:

* **Mate in one (BR1.1).** After the move, the opponent has a legal move that
  checkmates. Only replies that give check are played (``gives_check`` is
  tested first), so only checking moves are pushed. The reported reply is the
  first mating reply in SAN order.
* **Hanging piece (BR1.2).** A mover knight, bishop, rook or queen is hanging
  when the opponent, moving next, wins material on its square by a static
  exchange: legal captures only, worked out by pushing real moves on the board
  (pins, king recaptures and check evasions are respected), least valuable
  attacker first, each side free to stop when going on would lose. For the
  moved piece the gain must exceed an offset: the value it just captured plus,
  for a promoted piece, (promoted value - 1). A defended queen promotion that a
  rook takes back is therefore not "free".
* **Only new problems (BR1.3).** The same sets are worked out on the position
  before the move, with the turn passed (``push(chess.Move.null())``). When the
  mover is in check before the move a null move is not meaningful, so the
  "before" sets are empty and every problem after the move is new. A mate
  threat's identity is "the opponent has at least one mating reply". A piece's
  identity follows it: the moved piece from its origin to its destination, and
  the rook when castling. A promoted piece is always new.
* **No alternative (BR1.4).** When a warning remains, every other legal move is
  swept for the same kind of problem, quiet moves first, then captures and
  checks, stopping at the first move free of it; when none is, the warning is
  dropped. The sweep runs per kind: when the mate warning is dropped, the
  hanging check runs on its own, with its own sweep. An alternative "free of
  mate" only needs to allow no mate.
* **Priority (BR1.5).** Mate first; among hanging pieces the most valuable,
  then the lowest square index (nearest a1).
* **Budget (BR2.2, derived from NFR5).** The sweep has a hard budget on a
  monotonic clock. When it runs out the warning stands, because warning is
  safer, and that is logged at debug level.

``defended`` in a hanging warning means the mover has at least one legal
recapture after the opponent's first capture; it changes the dialog's wording.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import chess

logger = logging.getLogger("justchess.analysis")

MATE_IN_ONE = "mate_in_one"
HANGING_PIECE = "hanging_piece"
DEFAULT_BUDGET_MS = 250  # fallback; the app passes gameplay.yaml's blunder_check.time_budget_ms

# PieceValue (entities.md). The king counts only as an attacker of last resort.
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 1000,
}
JUDGED_PIECES = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


@dataclass(frozen=True)
class BlunderWarning:
    """The Warning entity: what the candidate move allows.

    ``mate_in_one`` carries ``mate``; ``hanging_piece`` carries ``piece``,
    ``square``, ``capturer`` (``{"piece", "square"}``) and ``defended``.
    """

    kind: str
    move: str
    mate: str | None = None
    piece: str | None = None
    square: str | None = None
    capturer: dict[str, str] | None = None
    defended: bool | None = None

    def to_dict(self) -> dict[str, object]:
        """The JSON shape the check-move route answers with (only the fields of its kind)."""
        if self.kind == MATE_IN_ONE:
            return {"kind": self.kind, "move": self.move, "mate": self.mate}
        return {"kind": self.kind, "move": self.move, "piece": self.piece, "square": self.square,
                "capturer": dict(self.capturer or {}), "defended": bool(self.defended)}


@dataclass(frozen=True)
class _Hanging:
    square: int
    piece_type: int
    capturer_type: int
    capturer_square: int
    defended: bool


class _Clock:
    """A monotonic deadline for the no-alternative sweep."""

    def __init__(self, budget_ms: float) -> None:
        self.deadline = time.monotonic() + budget_ms / 1000

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline


# --- exchanges --------------------------------------------------------------

def _value(piece_type: int | None) -> int:
    return PIECE_VALUES.get(piece_type, 0) if piece_type else 0


def _least_valuable_capture(board: chess.Board, square: int) -> chess.Move | None:
    """The side to move's legal capture on ``square`` with its least valuable piece (promoting to a queen)."""
    best: chess.Move | None = None
    best_key: tuple[int, int] | None = None
    for move in board.generate_legal_moves(to_mask=chess.BB_SQUARES[square]):
        if move.promotion not in (None, chess.QUEEN):
            continue
        key = (_value(board.piece_type_at(move.from_square)), move.from_square)
        if best_key is None or key < best_key:
            best, best_key = move, key
    return best


def _capture_value(board: chess.Board, move: chess.Move) -> int:
    """Material a capture wins on its own: the captured piece plus any promotion gain."""
    gained = _value(board.piece_type_at(move.to_square))
    if move.promotion:
        gained += _value(move.promotion) - 1
    return gained


def _exchange_gain(board: chess.Board, square: int) -> int:
    """Net material the side to move can win by starting captures on ``square`` (0 when it should not)."""
    move = _least_valuable_capture(board, square)
    if move is None:
        return 0
    gained = _capture_value(board, move)
    board.push(move)
    try:
        net = gained - _exchange_gain(board, square)
    finally:
        board.pop()
    return max(0, net)


def _hanging_on(board: chess.Board, square: int, offset: int) -> _Hanging | None:
    """Judge one mover piece with the opponent to move: hanging when the exchange gains more than ``offset``."""
    piece_type = board.piece_type_at(square)
    if not board.is_attacked_by(board.turn, square):
        return None
    first = _least_valuable_capture(board, square)
    if first is None:
        return None
    capturer_type = board.piece_type_at(first.from_square)
    gained = _capture_value(board, first)
    board.push(first)
    try:
        defended = _least_valuable_capture(board, square) is not None
        net = gained - _exchange_gain(board, square)
    finally:
        board.pop()
    if net <= offset:
        return None
    return _Hanging(square, piece_type, capturer_type, first.from_square, defended)


def _hanging_set(board: chess.Board, offsets: dict[int, int] | None = None) -> dict[int, _Hanging]:
    """Hanging knights, bishops, rooks and queens of the side NOT to move, keyed by square."""
    mover = not board.turn
    found: dict[int, _Hanging] = {}
    for piece_type in JUDGED_PIECES:
        for square in board.pieces(piece_type, mover):
            hanging = _hanging_on(board, square, (offsets or {}).get(square, 0))
            if hanging:
                found[square] = hanging
    return found


# --- mate -------------------------------------------------------------------

def _mating_replies(board: chess.Board, *, first_only: bool) -> list[chess.Move]:
    """The side to move's checkmating moves; only checking moves are pushed."""
    mates: list[chess.Move] = []
    for reply in board.legal_moves:
        if not board.gives_check(reply):
            continue
        board.push(reply)
        try:
            mate = board.is_checkmate()
        finally:
            board.pop()
        if mate:
            mates.append(reply)
            if first_only:
                break
    return mates


def _allows_mate(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return bool(_mating_replies(board, first_only=True))
    finally:
        board.pop()


# --- before and after -------------------------------------------------------

class _Position:
    """The position before the candidate, with the "before" facts worked out once."""

    def __init__(self, board: chess.Board) -> None:
        self.board = board
        self.in_check = board.is_check()
        self.mate_before = False
        self.hanging_before: frozenset[int] = frozenset()
        if not self.in_check:
            board.push(chess.Move.null())
            try:
                self.mate_before = bool(_mating_replies(board, first_only=True))
                self.hanging_before = frozenset(_hanging_set(board))
            finally:
                board.pop()

    def _follow(self, move: chess.Move) -> frozenset[int]:
        """The "before" hanging squares carried to where those pieces stand after ``move``."""
        moved = {move.from_square: move.to_square}
        if self.board.is_castling(move):
            rank = chess.square_rank(move.from_square)
            if self.board.is_kingside_castling(move):
                moved[chess.square(7, rank)] = chess.square(5, rank)
            else:
                moved[chess.square(0, rank)] = chess.square(3, rank)
        return frozenset(moved.get(square, square) for square in self.hanging_before)

    def _offset(self, move: chess.Move) -> int:
        """BR1.2 offset for the moved piece: what it captured, plus (promoted value - 1)."""
        captured = 1 if self.board.is_en_passant(move) else _value(self.board.piece_type_at(move.to_square))
        if move.promotion:
            captured += _value(move.promotion) - 1
        return captured

    def new_hanging(self, move: chess.Move) -> list[_Hanging]:
        """Pieces hanging after ``move`` that were not hanging before it (BR1.3)."""
        offsets = {move.to_square: self._offset(move)}
        before = self._follow(move)
        self.board.push(move)
        try:
            after = _hanging_set(self.board, offsets)
        finally:
            self.board.pop()
        if move.promotion:
            before = before - {move.to_square}
        return [hanging for square, hanging in after.items() if square not in before]


def _sweep_order(board: chess.Board, skip: chess.Move) -> list[chess.Move]:
    """Every legal move but ``skip``: quiet moves first, then captures and checks."""
    moves = [move for move in board.legal_moves if move != skip]
    return sorted(moves, key=lambda move: board.is_capture(move) or board.gives_check(move))


def _every_move_has(position: _Position, skip: chess.Move, problem: Callable[[chess.Move], bool],
                    clock: _Clock, kind: str) -> bool:
    """BR1.4: True when no legal move is free of ``problem``. Out of time: False, so the warning stands."""
    for move in _sweep_order(position.board, skip):
        if clock.expired():
            logger.debug("Blunder sweep for %s ran out of time; the warning stands", kind)
            return False
        if not problem(move):
            return False
    return True


def _pick_hanging(found: list[_Hanging]) -> _Hanging:
    """BR1.5: the most valuable piece, then the lowest square index."""
    return min(found, key=lambda hanging: (-_value(hanging.piece_type), hanging.square))


# --- entry point ------------------------------------------------------------

def _mate_warning(position: _Position, move: chess.Move, san: str, clock: _Clock) -> BlunderWarning | None:
    if position.mate_before:
        return None
    board = position.board
    board.push(move)
    try:
        mates = sorted(board.san(reply) for reply in _mating_replies(board, first_only=False))
    finally:
        board.pop()
    if not mates:
        return None
    if _every_move_has(position, move, lambda other: _allows_mate(board, other), clock, MATE_IN_ONE):
        return None
    return BlunderWarning(MATE_IN_ONE, san, mate=mates[0])


def _hanging_warning(position: _Position, move: chess.Move, san: str, clock: _Clock) -> BlunderWarning | None:
    found = position.new_hanging(move)
    if not found:
        return None
    if _every_move_has(position, move, lambda other: bool(position.new_hanging(other)), clock, HANGING_PIECE):
        return None
    hanging = _pick_hanging(found)
    return BlunderWarning(
        HANGING_PIECE, san,
        piece=chess.piece_name(hanging.piece_type),
        square=chess.square_name(hanging.square),
        capturer={"piece": chess.piece_name(hanging.capturer_type),
                  "square": chess.square_name(hanging.capturer_square)},
        defended=hanging.defended,
    )


def analyse(board: chess.Board, move: chess.Move, *, budget_ms: float = DEFAULT_BUDGET_MS) -> BlunderWarning | None:
    """Return the warning for ``move`` (legal for the side to move), or None.

    The caller's board is not changed: the work is done on a copy. Raises
    ``ValueError`` for a move that is not legal in the position.
    """
    if not isinstance(board, chess.Board) or not isinstance(move, chess.Move):
        raise TypeError("analyse needs a chess.Board and a chess.Move")
    if move not in board.legal_moves:
        raise ValueError(f"{move.uci()} is not legal in {board.fen()}")
    work = board.copy(stack=False)
    clock = _Clock(budget_ms)
    san = work.san(move)
    position = _Position(work)
    return _mate_warning(position, move, san, clock) or _hanging_warning(position, move, san, clock)
