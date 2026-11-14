"""U4 Analysis (``justchess/analysis.py``): BR1.1-BR1.5 on fixed positions.

Every FEN below was checked with python-chess: it is a valid position, the
side to move is the one named in the comment, and the candidate move is legal.
No mocks: ``analyse`` is pure and runs on ``chess.Board(fen)``.
"""

from __future__ import annotations

import chess
import pytest

from justchess.analysis import HANGING_PIECE, MATE_IN_ONE, BlunderWarning, analyse

# White to move after 1.f3 e5 (Fool's mate setup): g4?? allows Qh4#.
FOOLS_MATE_SETUP = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2"
# White to move; Rd1 guards the back rank against Re8-e1.
BACK_RANK = "4r1k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
# White to move after 1.e4 d6 2.Nf3 Nf6: Ne5?? dxe5.
KNIGHT_TO_E5 = "rnbqkb1r/ppp1pppp/3p1n2/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
# White to move after 1.e4 Nf6: Qh5?? Nxh5.
QUEEN_TO_H5 = "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2"
# White to move in the Ruy Lopez after 3...a6: Bxc6 dxc6 is an even trade.
RUY_LOPEZ = "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
# White to move: Rd5 is defended by e4 but the knight on f6 takes it (5 for 3).
ROOK_FOR_KNIGHT = "4k3/8/5n2/8/4P3/8/8/3RK3 w - - 0 1"
# White to move: the knight on e5 already hangs to d6.
KNIGHT_ALREADY_HANGING = "rnbqkb1r/ppp1pppp/3p1n2/4N3/4P3/8/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
# White to move, in zugzwang: every legal move allows mate in one, none does now.
EVERY_MOVE_ALLOWS_MATE = "8/7q/4K3/1q6/8/1k4N1/8/1n1q4 w - - 0 1"
# White to move, Black already threatens Qh4# (after 1.f3 e5 2.g4 d6).
MATE_ALREADY_THREATENED = "rnbqkbnr/ppp2ppp/3p4/4p3/6P1/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 3"
# White to move, in check from the rook on a1; the knight on c3 hangs to b4.
IN_CHECK_KNIGHT_HANGS = "7k/8/8/8/1p6/2N5/8/r3K3 w - - 0 1"
# The same without the checking rook: the knight already hung, so nothing is new.
NOT_IN_CHECK_KNIGHT_HANGS = "7k/8/8/8/1p6/2N5/8/4K3 w - - 0 1"
# White to move: Rd7 both allows Re1# and hangs the rook to Bc8.
MATE_AND_HANGING = "2b1r1k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
# White to move: d5 takes the d4 pawn's guard off both Re5 (Re8) and Nc5 (Ba7).
TWO_PIECES_LEFT = "4r1k1/b4ppp/8/2N1R3/3P4/8/5PPP/6K1 w - - 0 1"
# White to move: Ne5 is "defended" by d4, but d4 is pinned to the king by Ba7.
PINNED_DEFENDER = "6k1/b4ppp/2n5/8/3P4/5N2/6PP/6K1 w - - 0 1"
# The same without the pinning bishop: Nxe5 dxe5 is an even trade.
UNPINNED_DEFENDER = "6k1/5ppp/2n5/8/3P4/5N2/6PP/6K1 w - - 0 1"
# White to move: e8=Q, Rxe8, Rxe8 (the promotion is defended by Re1).
DEFENDED_PROMOTION = "r7/4P2k/8/8/8/8/6PP/4R1K1 w - - 0 1"
# The same without Re1: the new queen is taken for free.
FREE_PROMOTION = "r7/4P2k/8/8/8/8/6PP/6K1 w - - 0 1"
# White to move: O-O takes the king's guard off the knight on e2 (Nc3 attacks it).
CASTLING_LEAVES_KNIGHT = "4k3/8/8/8/8/2n5/4N1PP/4K2R w K - 0 1"
# White to move after ...d7-d5: exd6 e.p. opens the e-file onto the knight on e2.
EN_PASSANT_OPENS_FILE = "4r1k1/5ppp/8/3pP3/8/8/4NPPP/6K1 w - d6 0 2"
# White to move: Rd8 is checkmate.
MATING_MOVE = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


def judge(fen: str, uci: str, **kwargs) -> BlunderWarning | None:
    board = chess.Board(fen)
    assert board.is_valid(), board.status()
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves, f"{uci} is not legal in {fen}"
    return analyse(board, move, **kwargs)


def hanging(warning: BlunderWarning | None) -> tuple:
    assert warning is not None and warning.kind == HANGING_PIECE, warning
    return warning.piece, warning.square, warning.capturer, warning.defended


# --- BR1.1 mate in one ------------------------------------------------------

def test_fools_mate_setup_g4_allows_qh4_mate() -> None:
    warning = judge(FOOLS_MATE_SETUP, "g2g4")
    assert warning == BlunderWarning(MATE_IN_ONE, "g4", mate="Qh4#")
    assert warning.to_dict() == {"kind": "mate_in_one", "move": "g4", "mate": "Qh4#"}


def test_leaving_the_back_rank_allows_mate_but_a_quiet_move_does_not() -> None:
    assert judge(BACK_RANK, "d1d7") == BlunderWarning(MATE_IN_ONE, "Rd7", mate="Re1#")
    assert judge(BACK_RANK, "h2h3") is None


def test_a_move_that_checkmates_gets_no_warning() -> None:
    assert judge(MATING_MOVE, "d1d8") is None


# --- BR1.2 hanging pieces ---------------------------------------------------

def test_a_hanging_knight_then_a_hanging_queen() -> None:
    assert hanging(judge(KNIGHT_TO_E5, "f3e5")) == ("knight", "e5", {"piece": "pawn", "square": "d6"}, False)
    queen = judge(QUEEN_TO_H5, "d1h5")
    assert hanging(queen) == ("queen", "h5", {"piece": "knight", "square": "f6"}, False)
    assert queen.to_dict() == {"kind": "hanging_piece", "move": "Qh5", "piece": "queen", "square": "h5",
                               "capturer": {"piece": "knight", "square": "f6"}, "defended": False}


def test_an_even_trade_is_not_a_blunder() -> None:
    assert judge(RUY_LOPEZ, "b5c6") is None


def test_a_defended_piece_that_loses_to_a_cheaper_attacker_is_marked_defended() -> None:
    assert hanging(judge(ROOK_FOR_KNIGHT, "d1d5")) == ("rook", "d5", {"piece": "knight", "square": "f6"}, True)


def test_a_pinned_recapturer_does_not_defend() -> None:
    assert hanging(judge(PINNED_DEFENDER, "f3e5")) == ("knight", "e5", {"piece": "knight", "square": "c6"}, False)
    assert judge(UNPINNED_DEFENDER, "f3e5") is None, "with the pin gone, dxe5 makes it an even trade"


def test_promotion_offset_a_defended_queen_is_not_free_an_undefended_one_is() -> None:
    assert judge(DEFENDED_PROMOTION, "e7e8q") is None
    assert hanging(judge(FREE_PROMOTION, "e7e8q")) == ("queen", "e8", {"piece": "rook", "square": "a8"}, False)


def test_castling_and_en_passant_positions() -> None:
    assert hanging(judge(CASTLING_LEAVES_KNIGHT, "e1g1")) == ("knight", "e2", {"piece": "knight", "square": "c3"}, False)
    assert judge(CASTLING_LEAVES_KNIGHT, "h2h3") is None, "the king still guards e2"
    ep = judge(EN_PASSANT_OPENS_FILE, "e5d6")
    assert ep.move == "exd6"
    assert hanging(ep) == ("knight", "e2", {"piece": "rook", "square": "e8"}, False)


# --- BR1.3 only new problems ------------------------------------------------

def test_a_piece_already_hanging_does_not_warn_on_an_unrelated_move() -> None:
    assert judge(KNIGHT_ALREADY_HANGING, "h2h3") is None


def test_a_mate_threat_that_already_existed_does_not_warn() -> None:
    assert judge(MATE_ALREADY_THREATENED, "a2a3") is None


def test_mover_in_check_has_empty_before_sets() -> None:
    assert hanging(judge(IN_CHECK_KNIGHT_HANGS, "e1f2")) == ("knight", "c3", {"piece": "pawn", "square": "b4"}, False)
    assert judge(NOT_IN_CHECK_KNIGHT_HANGS, "e1f2") is None, "not in check: the knight hung before the move"


# --- BR1.4 no alternative ---------------------------------------------------

def test_every_move_allows_mate_so_no_mate_warning() -> None:
    assert judge(EVERY_MOVE_ALLOWS_MATE, "e6f6") is None


def test_when_the_mate_warning_is_dropped_the_hanging_warning_is_still_reported() -> None:
    warning = judge(EVERY_MOVE_ALLOWS_MATE, "g3h5")
    assert hanging(warning) == ("knight", "h5", {"piece": "queen", "square": "d1"}, False)


def test_an_exhausted_budget_keeps_the_warning() -> None:
    assert judge(EVERY_MOVE_ALLOWS_MATE, "g3h5", budget_ms=0) == BlunderWarning(MATE_IN_ONE, "Nh5", mate="Qbf5#")


# --- BR1.5 priority ---------------------------------------------------------

def test_mate_takes_priority_over_a_hanging_piece() -> None:
    assert judge(MATE_AND_HANGING, "d1d7") == BlunderWarning(MATE_IN_ONE, "Rd7", mate="Re1#")


def test_the_most_valuable_hanging_piece_is_reported() -> None:
    assert hanging(judge(TWO_PIECES_LEFT, "d4d5")) == ("rook", "e5", {"piece": "rook", "square": "e8"}, False)


# --- contract ---------------------------------------------------------------

def test_input_is_validated_and_the_callers_board_is_untouched() -> None:
    board = chess.Board(FOOLS_MATE_SETUP)
    with pytest.raises(ValueError):
        analyse(board, chess.Move.from_uci("e1e3"))
    with pytest.raises(TypeError):
        analyse(FOOLS_MATE_SETUP, chess.Move.from_uci("g2g4"))  # type: ignore[arg-type]
    analyse(board, chess.Move.from_uci("g2g4"))
    assert board.fen() == FOOLS_MATE_SETUP
