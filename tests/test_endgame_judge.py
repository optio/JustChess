"""P2 U6 attempt judging (BR2.1-BR2.4, BR2.6): hand-picked positions and short move lists, no engine."""

from __future__ import annotations

import chess
import pytest

from justchess import endgames
from justchess.endgames import EndgamePosition, JudgeLimits, judge, needs_defender

ROOK_BOX = "8/8/8/4k3/8/8/8/R3K3 w - - 0 1"
HOLD = "8/8/3k4/8/4K3/4P3/8/8 b - - 0 1"  # the shipped opp-hold-the-opposition position, Black holds


def play(fen: str, goal: str, moves: list[str], limits: JudgeLimits = JudgeLimits()):
    """Replay ``moves`` through the route's validator and judge the result as the side to move in ``fen``."""
    position = EndgamePosition("test-position", "queen-mate", "T", fen, goal, "H", 1)
    board = endgames.replay(position, moves, limits.max_plies) if len(moves) % 2 else _replay_even(fen, moves)
    player = chess.Board(fen).turn
    verdict = judge(board, goal, player, endgames.player_moves_in(moves), limits)
    return board, verdict, player


def _replay_even(fen: str, moves: list[str]) -> chess.Board:
    """After the defender's reply the list has even length (the route judges again after pushing the reply)."""
    board = chess.Board(fen)
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, uci
        board.push(move)
    return board


def test_mate_passes() -> None:
    board, verdict, player = play("4k3/8/4K3/8/8/8/8/7R w - - 0 1", "mate", ["h1h8"])
    assert (verdict.status, verdict.reason, verdict.player_moves, verdict.moves_left) == ("passed", "checkmate", 1, None)
    assert not needs_defender(board, verdict, player), "the player's own finishing move does not ask the engine"


def test_stalemate_fails_a_mate_goal() -> None:
    board, verdict, player = play("k7/8/8/2Q5/8/8/8/6K1 w - - 0 1", "mate", ["c5b6"])
    assert (verdict.status, verdict.reason) == ("failed", "stalemate")
    assert not needs_defender(board, verdict, player)


def test_repetition_fails_a_mate_goal_and_passes_a_draw_goal() -> None:
    shuffle = ["a1a2", "e5d5", "a2a1", "d5e5"] * 2  # the start position comes back a third time
    _board, mate_verdict, _ = play(ROOK_BOX, "mate", shuffle)
    assert (mate_verdict.status, mate_verdict.reason) == ("failed", "threefold_repetition")
    _board, short, _ = play(ROOK_BOX, "mate", shuffle[:4])
    assert short.status == "playing", "twice is not yet a repetition"
    held = ["d6e6", "e4d4", "e6d6", "d4e4"] * 2
    _board, draw_verdict, _ = play(HOLD, "draw", held)
    assert (draw_verdict.status, draw_verdict.reason, draw_verdict.moves_left) == ("passed", "threefold_repetition", 26)


def test_promotion_passes() -> None:
    board, verdict, player = play("8/4P1k1/8/8/8/8/8/K7 w - - 0 1", "promote", ["e7e8q"])
    assert (verdict.status, verdict.reason) == ("passed", "promoted")
    assert not needs_defender(board, verdict, player)
    _b, under, _ = play("8/4P1k1/8/8/8/8/8/K7 w - - 0 1", "promote", ["e7e8n"])
    assert under.reason == "promoted", "any promotion meets the goal"


def test_losing_every_pawn_fails_before_the_bare_kings_draw() -> None:
    _board, verdict, _ = play("8/8/8/8/3k4/8/2P5/K7 w - - 0 1", "promote", ["c2c3", "d4c3"])
    assert (verdict.status, verdict.reason) == ("failed", "pawns_lost")


@pytest.mark.parametrize("goal", ["promote", "draw"])
def test_the_defender_checkmated_passes_a_promote_goal_and_a_draw_goal(goal) -> None:
    board, verdict, player = play("7k/8/6K1/8/8/8/P7/5Q2 w - - 0 1", goal, ["f1f8"])
    assert (verdict.status, verdict.reason) == ("passed", "checkmate")
    assert not needs_defender(board, verdict, player), "a finished board is never sent to the engine"


def test_thirty_player_moves_held_passes_once_the_defender_has_replied() -> None:
    board = chess.Board(HOLD)
    player = board.turn
    assert judge(board, "draw", player, 30) == endgames.Verdict("passed", "held_moves", 30, 0)
    board.push_uci("d6e6")  # the 30th player move: the defender still replies once
    waiting = judge(board, "draw", player, 30)
    assert (waiting.status, waiting.moves_left) == ("playing", 0)
    assert needs_defender(board, waiting, player)
    early = judge(chess.Board(HOLD), "draw", player, 12)
    assert (early.status, early.reason, early.moves_left) == ("playing", None, 18)


def test_the_player_mated_fails() -> None:
    _board, verdict, _ = play("7K/5k2/8/6q1/8/8/8/R7 w - - 0 1", "mate", ["a1a2", "g5g7"])
    assert (verdict.status, verdict.reason) == ("failed", "player_mated")


def test_an_attempt_that_reaches_the_ply_cap_while_playing_is_too_long() -> None:
    limits = JudgeLimits(hold_moves=30, max_plies=4)
    _board, verdict, _ = play(ROOK_BOX, "mate", ["a1a2", "e5d5", "a2a1", "d5e5"], limits)
    assert (verdict.status, verdict.reason) == ("failed", "too_long")
    _board, under, _ = play(ROOK_BOX, "mate", ["a1a2", "e5d5"], limits)
    assert under.status == "playing"
    position = EndgamePosition("test-position", "rook-mate", "T", ROOK_BOX, "mate", "H", 1)
    with pytest.raises(endgames.EndgameError, match="too long"):
        endgames.replay(position, ["a1a2", "e5d5", "a2a1", "d5e5", "a1a2"], max_plies=4)


def test_needs_defender_only_while_playing_with_a_legal_reply_and_bad_lists_are_refused() -> None:
    board, verdict, player = play(ROOK_BOX, "mate", ["a1a7"])
    assert verdict.status == "playing" and needs_defender(board, verdict, player)
    board.push_uci("e5d5")
    assert not needs_defender(board, judge(board, "mate", player, 1), player), "never on the player's own turn"
    position = EndgamePosition("test-position", "rook-mate", "T", ROOK_BOX, "mate", "H", 1)
    for moves, message in (([], "Invalid moves"), ("a1a7", "Invalid moves"), (["a1a7", "e5d5"], "end with your move"),
                           (["a1a8"], None), (["e1e3"], "move 1"), (["a1a7", "e5e4", "zz"], "move 3"),
                           (["a1a7", "e5e7", "a7a8"], "move 2")):  # e7 is covered by the rook
        if message is None:
            endgames.replay(position, moves)  # legal: no error
            continue
        with pytest.raises(endgames.EndgameError, match=message):
            endgames.replay(position, moves)
