"""P2 U4 automatic draws and resign (BR4.2, BR4.3): computer games only; friend games keep their claims."""

from __future__ import annotations

import chess

from justchess import api, games, rooms
from tests.core.conftest import create_room, join_room
from tests.fakes.computer_rooms import current, new_computer_room, play, room_of

KNIGHT_SHUFFLE = ["g1f3", "g8f6", "f3g1", "f6g8"] * 2  # the start position occurs a third time


def test_threefold_repetition_ends_a_computer_game(db, clock) -> None:
    code, _ = new_computer_room(db, clock())
    game = play(db, code, clock(), KNIGHT_SHUFFLE)
    assert (game.status, game.end_reason, game.result) == ("finished", "threefold_repetition", "1/2-1/2")
    assert room_of(db, code).draws == 1


def test_fifty_move_rule_ends_a_computer_game(db, clock) -> None:
    board = chess.Board("8/8/8/4k3/8/8/4K3/R7 w - - 99 80")
    board.push_uci("a1a2")  # the hundredth half-move without a capture or pawn move
    assert games.end_for(board, computer=True) == games.End("fifty_moves", "1/2-1/2")
    assert games.end_for(board, computer=False) is None, "friend rooms keep the claim"
    reachable = chess.Board("8/8/8/4k3/8/8/4K3/R7 w - - 99 80")  # only one move away: not yet an end
    assert games.end_for(reachable, computer=True) is None


def test_a_friend_game_still_needs_a_claim(db, clock) -> None:
    with db.transaction() as conn:
        room, _, _ = rooms.create_room(conn, clock())
        rooms.join_room(conn, room.code, None, clock())
        game = games.create_first_game(conn, room.code, clock())
        games.mark_playing(conn, game, clock())
    game = play(db, room.code, clock(), KNIGHT_SHUFFLE, computer=False)
    assert game.status == "playing"
    with db.read() as conn:
        assert games.claimable_draw(games.replay_board(games.load_moves(conn, game.game_id))) == "threefold_claimed"


def test_resign_ends_with_the_computer_winning_and_counts(db, clock) -> None:
    for white_slot, result in (("A", "0-1"), ("B", "1-0")):
        code, _ = new_computer_room(db, clock(), white_slot=white_slot)
        game = current(db, code)
        with db.transaction() as conn:
            ended = games.resign(conn, game, "A", clock(), version=game.version)
            rooms.record_result(conn, code, ended.result, ended.white_slot, counted=ended.counted)
        assert (ended.status, ended.end_reason, ended.result, ended.version) == ("finished", "resigned", result, 1)
        room = room_of(db, code)
        assert (room.wins_a, room.wins_b, room.draws) == (0, 1, 0)


def test_resign_is_refused_in_a_friend_room(make_client) -> None:
    client = make_client()
    created = create_room(client)
    join_room(client, created["code"])
    refused = client.post(f"/api/rooms/{created['code']}/resign", json={"token": created["token"], "version": 1})
    assert (refused.status_code, refused.json()["detail"]) == (409, api.RESIGN_ONLY)
    after = client.get(f"/api/rooms/{created['code']}", headers={"X-Seat-Token": created["token"]}).json()
    assert (after["status"], after["score"]) == ("playing", {"A": 0, "B": 0, "draws": 0})
