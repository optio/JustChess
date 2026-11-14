"""Tests for justchess.games (BR2.1-BR2.5). Positions come from stored move sequences."""

from __future__ import annotations

import chess
import pytest

from justchess import DomainError
from justchess import games, rooms
from justchess.games import RoomView

FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]
KNIGHT_SHUFFLE = ["g1f3", "g8f6", "f3g1", "f6g8"]
LOYD_STALEMATE = [
    "e2e3", "a7a5", "d1h5", "a8a6", "h5a5", "h7h5", "h2h4", "a6h6", "a5c7", "f7f6",
    "c7d7", "e8f7", "d7b7", "d8d3", "b7b8", "d3h7", "b8c8", "f7g6", "c8e6",
]


@pytest.fixture
def code(db, clock):
    with db.transaction() as conn:
        room, _, _ = rooms.create_room(conn, clock())
        rooms.join_room(conn, room.code, None, clock())
        game = games.create_first_game(conn, room.code, clock())
        games.mark_playing(conn, game, clock())
    return room.code


def current(db, code):
    with db.read() as conn:
        return games.current_game(conn, code)


def play(db, code, clock, ucis):
    """Play moves through apply_move, each in its own transaction, as the API does."""
    game = current(db, code)
    for uci in ucis:
        slot = game.slot_of(chess.WHITE if game.version % 2 == 1 else chess.BLACK)
        with db.transaction() as conn:
            game = games.apply_move(conn, game, slot, uci, game.version, clock())
    return game


def view(db, code):
    game = current(db, code)
    with db.read() as conn:
        return games.GameView(game, games.load_moves(conn, game.game_id))


ROOM = RoomView("ABC123", {"A": 0, "B": 0, "draws": 0}, {"A": "connected", "B": "away"},
                {"state": "none", "requestedBy": None})


def refusal(db, action):
    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            action(conn)
    return err.value.status, err.value.message


def test_legal_move_accepted_and_illegal_rejected(db, code, clock):
    start = current(db, code)
    assert (start.status, start.version, start.white_slot) == ("playing", 1, "A")

    moved = play(db, code, clock, ["e2e4"])
    assert moved.version == 2 and "4P3" in moved.fen

    for bad in ("e7e5x", "zz99", "e4e6", "e2e4"):  # malformed, nonsense, illegal, piece gone
        assert refusal(db, lambda c: games.apply_move(c, moved, "B", bad, 2, clock())) == (400, "Illegal move")
    assert current(db, code).version == 2


def test_wrong_side_and_stale_version_rejected(db, code, clock):
    game = current(db, code)
    assert refusal(db, lambda c: games.apply_move(c, game, "B", "e7e5", game.version, clock())) == (403, "Not your turn")

    moved = play(db, code, clock, ["e2e4"])
    # a duplicate of the same move with the old version is refused as stale
    status, message = refusal(db, lambda c: games.apply_move(c, moved, "A", "e2e4", game.version, clock()))
    assert status == 409 and "latest position" in message
    with db.read() as conn:
        assert len(games.load_moves(conn, moved.game_id)) == 1


def test_fools_mate_ends_with_checkmate_and_further_moves_refused(db, code, clock):
    finished = play(db, code, clock, FOOLS_MATE)

    assert (finished.status, finished.end_reason, finished.result) == ("finished", "checkmate", "0-1")
    assert finished.version == 1 + len(FOOLS_MATE)  # the ending move increments only once
    assert finished.ended_at == clock()
    assert refusal(db, lambda c: games.apply_move(c, finished, "A", "a2a3", finished.version, clock())) == (409, "Game is over")


def test_stalemate_and_insufficient_material(db, code, clock):
    finished = play(db, code, clock, LOYD_STALEMATE)
    assert (finished.end_reason, finished.result) == ("stalemate", "1/2-1/2")

    # insufficient material: White captures the last pawn, leaving king and knight against king
    board = chess.Board("4k3/8/8/8/8/8/3p4/3NK3 w - - 0 1")
    assert games.automatic_end(board) is None
    board.push_uci("e1d2")
    end = games.automatic_end(board)
    assert (end.reason, end.result) == ("insufficient_material", "1/2-1/2")


def test_threefold_through_stored_moves_is_claimable_not_ended(db, code, clock):
    game = play(db, code, clock, KNIGHT_SHUFFLE * 2)  # start position now seen three times

    assert game.status == "playing"
    assert view(db, code).snapshot(ROOM, "A")["claimableDraw"] is True
    assert refusal(db, lambda c: games.claim_draw(c, game, "B", clock())) == (403, "Not your turn")

    with db.transaction() as conn:
        claimed = games.claim_draw(conn, game, "A", clock())
    assert (claimed.status, claimed.end_reason, claimed.result) == ("finished", "threefold_claimed", "1/2-1/2")
    assert claimed.version == game.version + 1


def test_fivefold_repetition_ends_automatically(db, code, clock):
    game = play(db, code, clock, KNIGHT_SHUFFLE * 4)

    assert (game.status, game.end_reason, game.result) == ("finished", "fivefold_repetition", "1/2-1/2")


def test_claims_refused_when_not_allowed(db, code, clock):
    game = play(db, code, clock, ["e2e4", "e7e5"])
    assert refusal(db, lambda c: games.claim_draw(c, game, "A", clock())) == (409, "A draw can't be claimed right now")
    assert refusal(db, lambda c: games.claim_win(c, game, "A", False, clock())) == (409, "Your opponent hasn't been away long enough")

    with db.transaction() as conn:
        won = games.claim_win(conn, game, "B", True, clock())  # B plays black
    assert (won.end_reason, won.result) == ("abandoned", "0-1")
    assert refusal(db, lambda c: games.claim_win(c, won, "A", True, clock())) == (409, "Game is over")

    with db.transaction() as conn:
        rematch = games.start_rematch(conn, won, clock())
    assert (rematch.number, rematch.white_slot, rematch.status, rematch.version) == (2, "B", "playing", 0)


def test_snapshot_numbered_moves_and_per_viewer_fields(db, code, clock):
    play(db, code, clock, ["e2e4", "e7e5", "g1f3"])
    gv = view(db, code)

    seat_b = gv.snapshot(ROOM, "B")  # black to move
    watcher = gv.snapshot(ROOM, None)
    seat_a = gv.snapshot(ROOM, "A")

    assert seat_b["moveList"] == [{"number": 1, "white": "e4", "black": "e5"},
                                  {"number": 2, "white": "Nf3", "black": None}]
    assert (seat_b["slot"], seat_b["colour"], seat_b["turn"]) == ("B", "black", "black")
    assert "b8c6" in seat_b["legalMoves"]
    assert (watcher["slot"], watcher["colour"], watcher["legalMoves"]) == (None, None, [])
    assert seat_a["legalMoves"] == [] and seat_a["colour"] == "white"
    assert seat_a["seats"] == {"A": {"presence": "connected", "colour": "white"},
                               "B": {"presence": "away", "colour": "black"}}
    for key in ("fen", "turn", "status", "check", "result", "score", "version", "lastMove", "claimableDrawReason"):
        assert key in watcher
    for legacy in ("moves", "legal", "white_score", "black_score", "outcome"):
        assert legacy not in watcher, f"legacy field {legacy} is still in the snapshot"


def test_claimable_draw_reason_names_threefold_and_none(db, code, clock):
    play(db, code, clock, ["e2e4"])
    assert view(db, code).snapshot(ROOM, "B")["claimableDrawReason"] is None

    game = play(db, code, clock, ["e7e5", *KNIGHT_SHUFFLE * 2])  # e4 e5 position seen three times
    snap = view(db, code).snapshot(ROOM, "A")
    assert game.status == "playing"
    assert (snap["claimableDraw"], snap["claimableDrawReason"]) == (True, "threefold")


def test_claimable_draw_reason_names_the_fifty_move_rule(db, clock):
    # The reason maps from claimable_draw(); a position with halfmove clock 100 is claimable at once.
    board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 100 80")
    assert games.claimable_draw(board) == "fifty_moves_claimed"
    assert games.CLAIM_REASON_NAMES[games.claimable_draw(board)] == "fifty_moves"

    with db.transaction() as conn:
        room, _, _ = rooms.create_room(conn, clock())
        game = games.create_first_game(conn, room.code, clock())
    gv = games.GameView(game, [])
    gv.board = board  # the replayed start position swapped for the 50-move position
    gv.game = games.Game(game.game_id, game.room_code, 1, "A", board.fen(), 0, "playing", None, None, None, None)
    snap = gv.snapshot(ROOM, "A")
    assert (snap["claimableDraw"], snap["claimableDrawReason"]) == (True, "fifty_moves")
    gv_finished = games.GameView(game, [])
    assert gv_finished.snapshot(ROOM, "A")["claimableDrawReason"] is None  # waiting game: nothing claimable


# --- P2 U2: capture info (BR1.3, W2) and the snapshot's new fields (W3) -----------

def stored_captures(db, code):
    """Return ``{ply: (captured_piece, captured_square)}`` as stored on the move rows."""
    game = current(db, code)
    with db.read() as conn:
        rows = conn.execute("SELECT ply, captured_piece, captured_square FROM moves WHERE game_id = ? ORDER BY ply",
                            (game.game_id,)).fetchall()
    return {row["ply"]: (row["captured_piece"], row["captured_square"]) for row in rows}


def test_a_normal_capture_stores_the_taken_piece_and_its_square(db, code, clock):
    play(db, code, clock, ["e2e4", "d7d5", "e4d5", "d8d5"])  # pawn takes pawn, queen takes pawn back

    captures = stored_captures(db, code)
    assert captures[3] == ("p", "d5"), "a black pawn taken on the arrival square"
    assert captures[4] == ("P", "d5"), "uppercase: the taken pawn was white"


def test_en_passant_stores_the_passed_pawns_square_not_the_arrival_square(db, code, clock):
    play(db, code, clock, ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"])

    assert stored_captures(db, code)[5] == ("p", "d5")
    snap = view(db, code).snapshot(ROOM, "B")
    assert snap["lastMove"] == "e5d6" and snap["lastCapture"] == {"piece": "p", "square": "d5"}


def test_promotion_with_capture_stores_the_taken_rook(db, code, clock):
    play(db, code, clock, ["a2a4", "b7b5", "a4b5", "a7a6", "b5a6", "c8b7", "a6b7", "g8f6", "b7a8q"])

    captures = stored_captures(db, code)
    assert captures[7] == ("b", "b7"), "the pawn took the bishop on b7"
    assert captures[9] == ("r", "a8"), "the promoting pawn took the rook on a8"
    assert view(db, code).board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_quiet_moves_and_castling_store_no_capture(db, code, clock):
    play(db, code, clock, ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1"])

    assert set(stored_captures(db, code).values()) == {(None, None)}
    assert view(db, code).snapshot(ROOM, "B")["lastCapture"] is None
    board = chess.Board()
    assert games.capture_info(board, chess.Move.from_uci("e2e4")) == (None, None)


def test_snapshot_carries_mode_computer_level_and_last_capture(db, code, clock):
    online = RoomView("ABC123", ROOM.score, ROOM.presence, ROOM.rematch, mode="online")
    play(db, code, clock, ["e2e4", "d7d5", "e4d5"])
    snap = view(db, code).snapshot(online, "B")
    assert (snap["mode"], snap["computerLevel"]) == ("online", None)
    assert snap["lastCapture"] == {"piece": "p", "square": "d5"}

    play(db, code, clock, ["g8f6"])  # a quiet reply clears lastCapture: it is about the last move only
    assert view(db, code).snapshot(online, "A")["lastCapture"] is None
    assert view(db, code).snapshot(ROOM, None)["mode"] == "waiting", "RoomView defaults to waiting"
