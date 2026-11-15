"""Games: chess rules, game lifecycle, draw and win claims, and the snapshot.

Implements BR2.1-BR2.5. The board is always rebuilt from the standard starting
position by replaying the stored ``Move.uci`` list in ply order, so repetition
and move-count rules see the full history. ``Game.fen`` is a cache for display
and fast reads only, never the source for rules.

Writes take an open connection inside the caller's transaction. Any accepted
change increments ``Game.version`` exactly once.

The snapshot carries ``claimableDraw`` (bool) and, since U3,
``claimableDrawReason`` (``"threefold"``, ``"fifty_moves"`` or ``None``) so the
client can name the claim. The legacy fields of the old client (``moves``,
``legal``, ``white_score``, ``black_score``, ``outcome``) were removed with it.

P2 U2 (BR1.3, W2, W3): ``apply_move`` computes what the move captures before
pushing it (for en passant the passed pawn on its own square, otherwise the
piece on the arrival square) and stores ``captured_piece`` (FEN letter,
uppercase for a white piece) and ``captured_square`` on the move row. The
snapshot gains ``mode``, ``computerLevel`` and ``lastCapture``
(``{piece, square}`` for the last move, or ``None``); its other fields are
unchanged.

P2 U3 (pass-along, BR1.2, BR1.4, BR1.5): ``Game.counted`` is read from the row.
In pass-along mode seat A may move, claim and check moves for both colours
(``pass_along=True`` on the seat-check functions), and its snapshot carries the
legal moves whatever colour is to move. ``start_pass_along`` starts a waiting
game uncounted, ``mark_counted`` counts the current game only while it is not
finished, and ``start_pass_along_rematch`` is seat A's one-seat "Play again".
The snapshot gains ``joinRequest`` (``{expiresAt, expiresIn}`` for seat A
only, else ``None``) and ``counted``.

P2 U4 (computer games, BR4.1-BR4.3, BR3.4, BR7.1):

- ``end_for(board, computer)`` is ``automatic_end`` for friend rooms. For a
  computer room it also ends the game on a threefold repetition
  (``threefold_repetition``) or the 50-move rule (``fifty_moves``) of the
  position on the board; a draw the next move could only reach does not count.
  ``apply_move(..., computer=True)`` uses it; friend rooms are unchanged.
- ``takeback`` removes the player's last move and the computer's reply (or the
  player's last move alone when the computer is to move with no reply in
  flight), rebuilds the cached FEN by replay and bumps the version once.
- ``resign`` ends the game for the other side with end reason ``resigned``.
- ``create_computer_game`` starts game 1 already playing, and
  ``start_computer_rematch`` starts the next game at once with colours swapped
  or the colour the player chose.
- The snapshot gains ``computer``: ``{state, queuePosition, reason, level,
  available}`` for a computer room, ``None`` for a friend room. It is supplied
  by the caller in ``RoomView.computer``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from functools import cached_property

import chess

from justchess import DomainError

WAITING, PLAYING, FINISHED = "waiting", "playing", "finished"

GAME_OVER = "Game is over"
WAITING_FOR_OPPONENT = "Waiting for an opponent"
NOT_YOUR_TURN = "Not your turn"
ILLEGAL_MOVE = "Illegal move"
STALE_VERSION = "The board changed, here is the latest position"
DRAW_NOT_CLAIMABLE = "A draw can't be claimed right now"
NOT_AWAY_LONG_ENOUGH = "Your opponent hasn't been away long enough"
NOTHING_TO_TAKE_BACK = "Nothing to take back"
WAIT_FOR_COMPUTER = "Wait for the computer's move"
NOT_OVER_YET = "The game isn't over yet"
COLOURS = ("white", "black")

AUTOMATIC_ENDS = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
}


@dataclass(frozen=True)
class Game:
    """A game row. ``fen`` is a display cache; rules always replay the stored moves."""

    game_id: int
    room_code: str
    number: int
    white_slot: str
    fen: str
    version: int
    status: str
    end_reason: str | None
    result: str | None
    started_at: float | None
    ended_at: float | None
    counted: bool = True

    def colour_of(self, slot: str) -> str:
        """Return ``white`` or ``black`` for a seat slot in this game."""
        return "white" if slot == self.white_slot else "black"

    def slot_of(self, colour: bool) -> str:
        """Return the slot that plays ``colour`` (chess.WHITE or chess.BLACK)."""
        return self.white_slot if colour == chess.WHITE else ("B" if self.white_slot == "A" else "A")


@dataclass(frozen=True)
class StoredMove:
    """One stored half-move (1-based ply) and what it captured, if anything."""

    ply: int
    uci: str
    san: str
    played_at: float
    captured_piece: str | None = None
    captured_square: str | None = None


@dataclass(frozen=True)
class End:
    """How a game ended: the end reason enum value and the result string."""

    reason: str
    result: str


@dataclass(frozen=True)
class RoomView:
    """Room facts the snapshot needs, supplied by the caller (Rooms and LiveUpdates)."""

    code: str
    score: dict[str, int]
    presence: dict[str, str]
    rematch: dict[str, str | None]
    mode: str = "waiting"
    computer_level: str | None = None
    join_request: dict[str, float] | None = None  # P2 U3: shown to seat A only
    computer: dict[str, object] | None = None  # P2 U4 BR7.1: the computer's state, None for friend rooms
    stand_in: bool = False  # the computer holds seat B of a friend room until a friend joins
    can_switch_side: bool = False  # seat A may take the other colour now (rooms.can_switch_side)
    last_seen: dict[str, int] = field(default_factory=dict)  # slot -> seconds since last seen, whole minutes

    @property
    def pass_along(self) -> bool:
        """True while the room is in pass-along mode (BR1.2)."""
        return self.mode == "pass_along"


# --- reads ------------------------------------------------------------------

def _game_from_row(row: sqlite3.Row) -> Game:
    return Game(row["game_id"], row["room_code"], row["number"], row["white_slot"], row["fen"],
                row["version"], row["status"], row["end_reason"], row["result"],
                row["started_at"], row["ended_at"], bool(row["counted"]))


def current_game(conn: sqlite3.Connection, code: str) -> Game:
    """Return the room's highest-numbered game (there is no stored pointer)."""
    row = conn.execute(
        "SELECT * FROM games WHERE room_code = ? ORDER BY number DESC LIMIT 1", (code,)
    ).fetchone()
    if row is None:
        raise DomainError(404, "Room not found")
    return _game_from_row(row)


def count_games(conn: sqlite3.Connection, code: str) -> int:
    """Return how many games the room has had."""
    return conn.execute("SELECT count(*) FROM games WHERE room_code = ?", (code,)).fetchone()[0]


def load_moves(conn: sqlite3.Connection, game_id: int) -> list[StoredMove]:
    """Return the game's moves in ply order."""
    rows = conn.execute(
        "SELECT ply, uci, san, played_at, captured_piece, captured_square FROM moves "
        "WHERE game_id = ? ORDER BY ply", (game_id,)
    ).fetchall()
    return [StoredMove(row["ply"], row["uci"], row["san"], row["played_at"],
                       row["captured_piece"], row["captured_square"]) for row in rows]


def replay_board(moves: list[StoredMove]) -> chess.Board:
    """Rebuild the board from the starting position by replaying every stored move."""
    board = chess.Board()
    for move in moves:
        board.push_uci(move.uci)
    return board


# --- lifecycle --------------------------------------------------------------

def start_game(conn: sqlite3.Connection, code: str, number: int, white_slot: str,
               status: str, now: float, counted: bool = True) -> Game:
    """Insert a new game for the room and return it."""
    started = now if status == PLAYING else None
    conn.execute(
        "INSERT INTO games (room_code, number, white_slot, fen, version, status, started_at, counted) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
        (code, number, white_slot, chess.STARTING_FEN, status, started, int(counted)),
    )
    return current_game(conn, code)


def create_first_game(conn: sqlite3.Connection, code: str, now: float, white_slot: str = "A") -> Game:
    """Create game 1, waiting for seat B; seat A (the creator) plays white unless ``white_slot`` is B."""
    return start_game(conn, code, 1, white_slot, WAITING, now)


def start_rematch(conn: sqlite3.Connection, previous: Game, now: float) -> Game:
    """Create the next game with colours flipped, already playing (BR3.2)."""
    flipped = "B" if previous.white_slot == "A" else "A"
    return start_game(conn, previous.room_code, previous.number + 1, flipped, PLAYING, now)


def mark_playing(conn: sqlite3.Connection, game: Game, now: float) -> bool:
    """Move a waiting game to playing when seat B joins; return True if it changed."""
    if game.status != WAITING:
        return False
    conn.execute(
        "UPDATE games SET status = ?, started_at = ?, version = version + 1 WHERE game_id = ?",
        (PLAYING, now, game.game_id),
    )
    return True


def start_pass_along(conn: sqlite3.Connection, game: Game, now: float) -> bool:
    """BR1.1/BR1.4: entering pass-along starts a waiting game, uncounted; return True if it changed."""
    if game.status != WAITING:
        return False
    conn.execute(
        "UPDATE games SET status = ?, started_at = ?, counted = 0, version = version + 1 WHERE game_id = ?",
        (PLAYING, now, game.game_id),
    )
    return True


def mark_counted(conn: sqlite3.Connection, game: Game) -> bool:
    """BR1.4: seat B was taken; count the current game unless it already finished. True if it changed."""
    if game.status == FINISHED or game.counted:
        return False
    conn.execute("UPDATE games SET counted = 1 WHERE game_id = ?", (game.game_id,))
    return True


def start_pass_along_rematch(conn: sqlite3.Connection, previous: Game, now: float) -> Game:
    """BR1.5: seat A's one-seat "Play again" in pass-along: next game at once, colours swapped, uncounted."""
    if previous.status != FINISHED:
        raise DomainError(409, "Finish this game first")
    flipped = "B" if previous.white_slot == "A" else "A"
    return start_game(conn, previous.room_code, previous.number + 1, flipped, PLAYING, now, counted=False)


def create_computer_game(conn: sqlite3.Connection, code: str, white_slot: str, now: float) -> Game:
    """P2 U4 BR3.1: game 1 of a computer room, already playing, counted."""
    return start_game(conn, code, 1, white_slot, PLAYING, now)


def white_slot_for(colour: str | None, previous_white: str) -> str:
    """BR3.4: the player (seat A) takes ``white`` or ``black``; anything else (random, none) swaps colours."""
    if colour == "white":
        return "A"
    if colour == "black":
        return "B"
    return "B" if previous_white == "A" else "A"


def start_computer_rematch(conn: sqlite3.Connection, previous: Game, now: float, colour: str | None = None,
                           counted: bool = True) -> Game:
    """P2 U4 BR3.4: the next computer game at once; colours swap unless the player named one.

    A computer stand-in's games pass ``counted=False`` (they never touch the friends' score).
    """
    if previous.status != FINISHED:
        raise DomainError(409, NOT_OVER_YET)
    white = white_slot_for(colour, previous.white_slot)
    return start_game(conn, previous.room_code, previous.number + 1, white, PLAYING, now, counted=counted)


def bump_version(conn: sqlite3.Connection, game: Game) -> None:
    """Increment the version for an accepted change that is not a move (a rematch request)."""
    conn.execute("UPDATE games SET version = version + 1 WHERE game_id = ?", (game.game_id,))


def _require_playing(game: Game) -> None:
    if game.status == WAITING:
        raise DomainError(409, WAITING_FOR_OPPONENT)
    if game.status != PLAYING:
        raise DomainError(409, GAME_OVER)


def require_playing(game: Game) -> None:
    """409 "Waiting for an opponent" or "Game is over" unless the game is playing (P2 U4 routes use it)."""
    _require_playing(game)


def may_move(game: Game, slot: str, colour: bool, pass_along: bool = False) -> bool:
    """BR1.2: the seat holds the side to move, or it is seat A in pass-along mode (both colours)."""
    if pass_along and slot == "A":
        return True
    return game.slot_of(colour) == slot


def _require_turn(board: chess.Board, game: Game, slot: str, pass_along: bool = False) -> None:
    if not may_move(game, slot, board.turn, pass_along):
        raise DomainError(403, NOT_YOUR_TURN)


def _finish(conn: sqlite3.Connection, game: Game, fen: str, end: End | None, now: float) -> Game:
    if end is None:
        conn.execute("UPDATE games SET fen = ?, version = version + 1 WHERE game_id = ?",
                     (fen, game.game_id))
    else:
        conn.execute(
            "UPDATE games SET fen = ?, version = version + 1, status = ?, end_reason = ?, "
            "result = ?, ended_at = ? WHERE game_id = ?",
            (fen, FINISHED, end.reason, end.result, now, game.game_id),
        )
    return current_game(conn, game.room_code)


# --- rules ------------------------------------------------------------------

def automatic_end(board: chess.Board) -> End | None:
    """Return the automatic end of the position (BR2.2), ignoring claimable draws."""
    outcome = board.outcome(claim_draw=False)
    if outcome is None:
        return None
    reason = AUTOMATIC_ENDS.get(outcome.termination)
    if reason is None:  # variant terminations cannot occur in standard chess
        return None
    return End(reason, outcome.result())


def end_for(board: chess.Board, computer: bool = False) -> End | None:
    """P2 U4 BR4.2: the automatic end, plus threefold repetition and the 50-move rule in computer rooms.

    Only the position on the board counts (``is_repetition(3)``,
    ``is_fifty_moves()``), never a draw the next move could reach.
    """
    end = automatic_end(board)
    if end is not None or not computer:
        return end
    if board.is_repetition(3):
        return End("threefold_repetition", "1/2-1/2")
    if board.is_fifty_moves():
        return End("fifty_moves", "1/2-1/2")
    return None


def claimable_draw(board: chess.Board) -> str | None:
    """Return the claim reason available to the side to move, or None (BR2.3)."""
    if board.can_claim_fifty_moves():
        return "fifty_moves_claimed"
    if board.can_claim_threefold_repetition():
        return "threefold_claimed"
    return None


# Short names for the snapshot's ``claimableDrawReason`` (U3 labels the claim button with it).
CLAIM_REASON_NAMES = {"threefold_claimed": "threefold", "fifty_moves_claimed": "fifty_moves"}


def _parse_legal_move(board: chess.Board, uci: str) -> chess.Move:
    try:
        move = chess.Move.from_uci(uci)
    except (chess.InvalidMoveError, ValueError):
        raise DomainError(400, ILLEGAL_MOVE) from None
    if move not in board.legal_moves:
        raise DomainError(400, ILLEGAL_MOVE)
    return move


def parse_legal_move(board: chess.Board, uci: str) -> chess.Move:
    """Return the move for ``uci`` when it is legal on ``board``, else raise 400 "Illegal move"."""
    return _parse_legal_move(board, uci)


def require_move_turn(game: Game, slot: str, version: int, ply_count: int, pass_along: bool = False) -> None:
    """U4 check-move: the checks of ``apply_move`` before legality, without replaying the board.

    Same order as ``apply_move``: game playing (409), version current (409), the
    seat holds the side to move (403). The side to move follows from the number
    of stored half-moves, because every game starts from the standard position.
    """
    _require_playing(game)
    if version != game.version:
        raise DomainError(409, STALE_VERSION)
    if not may_move(game, slot, chess.WHITE if ply_count % 2 == 0 else chess.BLACK, pass_along):
        raise DomainError(403, NOT_YOUR_TURN)


def capture_info(board: chess.Board, move: chess.Move) -> tuple[str | None, str | None]:
    """Return ``(piece letter, square name)`` of what ``move`` captures on ``board``, or ``(None, None)``.

    Call before the move is pushed (BR1.3). En passant takes the passed pawn,
    which stands beside the arrival square, on the mover's starting rank.
    """
    if board.is_castling(move):
        return None, None
    if board.is_en_passant(move):
        square = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
    else:
        square = move.to_square
    piece = board.piece_at(square)
    if piece is None:
        return None, None
    return piece.symbol(), chess.square_name(square)


def apply_move(conn: sqlite3.Connection, game: Game, slot: str, uci: str, version: int,
               now: float, pass_along: bool = False, computer: bool = False) -> Game:
    """Validate and apply one move (BR2.1), then evaluate the automatic end (BR2.2).

    Checks run in this order: game playing, version current, seat holds the side
    to move, move legal. A stale version is checked before the turn so that any
    client acting on an outdated board gets the 409 with the latest snapshot.
    P2 U4: ``computer=True`` (computer rooms only) uses the claim-aware end of ``end_for``.
    """
    _require_playing(game)
    if version != game.version:
        raise DomainError(409, STALE_VERSION)
    moves = load_moves(conn, game.game_id)
    board = replay_board(moves)
    _require_turn(board, game, slot, pass_along)
    move = _parse_legal_move(board, uci)
    san = board.san(move)
    captured_piece, captured_square = capture_info(board, move)
    board.push(move)
    conn.execute(
        "INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece, captured_square) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (game.game_id, len(moves) + 1, move.uci(), san, now, captured_piece, captured_square),
    )
    return _finish(conn, game, board.fen(), end_for(board, computer), now)


def _require_version(game: Game, version: int | None) -> None:
    if version is not None and version != game.version:
        raise DomainError(409, STALE_VERSION)


def takeback(conn: sqlite3.Connection, game: Game, now: float, computer_to_move_without_reply: bool,
             version: int | None = None, player_slot: str = "A") -> Game:
    """P2 U4 BR4.1: take back moves in a playing computer game; return the game after it.

    On the player's turn, after at least one player move: the last two plies
    (the computer's reply and the player's move). On the computer's turn with no
    reply in flight (``computer_to_move_without_reply``): the player's last move
    only. Otherwise 409 "Nothing to take back" (or "Wait for the computer's move"
    on the computer's turn). The FEN is rebuilt by replaying what remains and the
    version goes up once. ``now`` is unused (a takeback stamps nothing) and kept
    for the uniform write signature.
    """
    del now
    _require_playing(game)
    _require_version(game, version)
    moves = load_moves(conn, game.game_id)
    board = replay_board(moves)
    players_turn = game.slot_of(board.turn) == player_slot
    player_first = game.white_slot == player_slot
    player_moves = (len(moves) + 1) // 2 if player_first else len(moves) // 2
    if players_turn:
        remove = 2 if player_moves >= 1 else 0
    elif not computer_to_move_without_reply:
        raise DomainError(409, WAIT_FOR_COMPUTER)
    else:
        remove = 1 if player_moves >= 1 else 0
    if remove == 0:
        raise DomainError(409, NOTHING_TO_TAKE_BACK)
    keep = len(moves) - remove
    conn.execute("DELETE FROM moves WHERE game_id = ? AND ply > ?", (game.game_id, keep))
    fen = replay_board(moves[:keep]).fen()
    conn.execute("UPDATE games SET fen = ?, version = version + 1 WHERE game_id = ?", (fen, game.game_id))
    return current_game(conn, game.room_code)


def resign(conn: sqlite3.Connection, game: Game, slot: str, now: float, version: int | None = None) -> Game:
    """P2 U4 BR4.3: ``slot`` resigns a playing game; the other side wins with end reason ``resigned``."""
    _require_playing(game)
    _require_version(game, version)
    result = "0-1" if game.colour_of(slot) == "white" else "1-0"
    return _finish(conn, game, game.fen, End("resigned", result), now)


def claim_draw(conn: sqlite3.Connection, game: Game, slot: str, now: float, pass_along: bool = False) -> Game:
    """End the game as a claimed draw when claimable by the seat to move (BR2.3)."""
    _require_playing(game)
    board = replay_board(load_moves(conn, game.game_id))
    _require_turn(board, game, slot, pass_along)
    reason = claimable_draw(board)
    if reason is None:
        raise DomainError(409, DRAW_NOT_CLAIMABLE)
    return _finish(conn, game, board.fen(), End(reason, "1/2-1/2"), now)


def claim_win(conn: sqlite3.Connection, game: Game, slot: str, opponent_abandoned: bool,
              now: float) -> Game:
    """End the game in the claimant's favour when the opponent is abandoned (BR2.4)."""
    _require_playing(game)
    if not opponent_abandoned:
        raise DomainError(409, NOT_AWAY_LONG_ENOUGH)
    result = "1-0" if game.colour_of(slot) == "white" else "0-1"
    return _finish(conn, game, game.fen, End("abandoned", result), now)


def delete_games_for_room(conn: sqlite3.Connection, code: str) -> None:
    """Delete every game and move of the room (used by Housekeeping)."""
    conn.execute(
        "DELETE FROM moves WHERE game_id IN (SELECT game_id FROM games WHERE room_code = ?)", (code,)
    )
    conn.execute("DELETE FROM games WHERE room_code = ?", (code,))


# --- snapshot ---------------------------------------------------------------

def numbered_moves(moves: list[StoredMove]) -> list[dict[str, object]]:
    """Group half-moves as ``[{number, white, black}]``."""
    grouped: list[dict[str, object]] = []
    for move in moves:
        if move.ply % 2 == 1:
            grouped.append({"number": (move.ply + 1) // 2, "white": move.san, "black": None})
        else:
            grouped[-1]["black"] = move.san
    return grouped


@dataclass
class GameView:
    """A game with its replayed board, computed once and shared by every viewer's snapshot."""

    game: Game
    moves: list[StoredMove]
    board: chess.Board = field(init=False)

    def __post_init__(self) -> None:
        self.board = replay_board(self.moves)

    @cached_property
    def legal_moves(self) -> list[str]:
        """Legal moves in UCI for the side to move; empty unless the game is playing."""
        if self.game.status != PLAYING:
            return []
        return [move.uci() for move in self.board.legal_moves]

    @cached_property
    def claimable(self) -> str | None:
        """The draw claim reason available to the side to move, or None."""
        return claimable_draw(self.board) if self.game.status == PLAYING else None

    def snapshot(self, room: RoomView, viewer_slot: str | None) -> dict[str, object]:
        """Build the snapshot for one viewer (BR2.5); legal moves only for the seat to move."""
        game, board = self.game, self.board
        turn = "white" if board.turn == chess.WHITE else "black"
        # Waiting for a friend: nobody moves until seat B is taken (also after leaving pass-along mid-game).
        alone = room.mode == "waiting" and room.presence.get("B", "empty") == "empty"
        mover = viewer_slot is not None and not alone and may_move(game, viewer_slot, board.turn, room.pass_along)
        legal = self.legal_moves if mover else []
        return {
            "code": room.code,
            "game": game.number,
            "fen": board.fen(),
            "turn": turn,
            "status": game.status,
            "endReason": game.end_reason,
            "result": game.result,
            "check": board.is_check(),
            "moveList": numbered_moves(self.moves),
            "lastMove": self.moves[-1].uci if self.moves else None,
            "version": game.version,
            "claimableDraw": self.claimable is not None,
            "claimableDrawReason": CLAIM_REASON_NAMES.get(self.claimable) if self.claimable else None,
            "seats": {slot: {"presence": room.presence.get(slot, "empty"), "colour": game.colour_of(slot),
                             "lastSeenSeconds": room.last_seen.get(slot)}
                      for slot in ("A", "B")},
            "score": dict(room.score),
            "rematch": dict(room.rematch),
            "slot": viewer_slot,
            "colour": game.colour_of(viewer_slot) if viewer_slot else None,
            "legalMoves": legal,
            "mode": room.mode,
            "computerLevel": room.computer_level,
            "lastCapture": self.last_capture,
            "counted": game.counted,
            "joinRequest": dict(room.join_request) if room.join_request and viewer_slot == "A" else None,
            "computer": dict(room.computer) if room.computer is not None else None,
            "standIn": room.stand_in,
            "canSwitchSides": room.can_switch_side and viewer_slot == "A",
        }

    @property
    def last_capture(self) -> dict[str, str] | None:
        """``{piece, square}`` captured by the last move, or None (BR1.3)."""
        if not self.moves or self.moves[-1].captured_piece is None:
            return None
        last = self.moves[-1]
        return {"piece": last.captured_piece, "square": last.captured_square}
