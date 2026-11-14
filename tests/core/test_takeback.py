"""P2 U4 takeback at the data layer (BR4.1): what is removed, when it is refused, and the state after it."""

from __future__ import annotations

import pytest

from justchess import DomainError, games
from tests.fakes.computer_rooms import current, moves_of, new_computer_room, play


def take_back(db, code, now, *, no_reply_in_flight=False, version=None):
    game = current(db, code)
    with db.transaction() as conn:
        return games.takeback(conn, game, now, no_reply_in_flight, version=game.version if version is None else version)


def test_two_plies_on_the_players_turn(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, code, clock(), ["e2e4", "e7e5", "g1f3", "b8c6"])
    after = take_back(db, code, clock())
    assert moves_of(db, code) == ["e2e4", "e7e5"]
    assert after.status == "playing"


def test_one_ply_on_the_computers_turn_when_no_reply_is_in_flight(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="B")  # the player is black
    play(db, code, clock(), ["d2d4", "d7d5"])  # the computer is to move, its reply never came
    take_back(db, code, clock(), no_reply_in_flight=True)
    assert moves_of(db, code) == ["d2d4"]


def test_nothing_to_take_back(db, clock) -> None:
    fresh, _ = new_computer_room(db, clock(), white_slot="A")
    computer_first, _ = new_computer_room(db, clock(), white_slot="B")
    play(db, computer_first, clock(), ["e2e4"])  # only the computer has moved
    waiting, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, waiting, clock(), ["e2e4"])  # computer to move with its reply in flight
    for code, flag, message in ((fresh, False, games.NOTHING_TO_TAKE_BACK),
                                (computer_first, False, games.NOTHING_TO_TAKE_BACK),
                                (waiting, False, games.WAIT_FOR_COMPUTER)):
        with pytest.raises(DomainError) as refused:
            take_back(db, code, clock(), no_reply_in_flight=flag)
        assert (refused.value.status, refused.value.message) == (409, message)
    assert moves_of(db, computer_first) == ["e2e4"] and moves_of(db, waiting) == ["e2e4"]


def test_refused_when_the_game_is_over(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, code, clock(), ["e2e4", "e7e5"])
    with db.transaction() as conn:
        games.resign(conn, games.current_game(conn, code), "A", clock())
    with pytest.raises(DomainError) as refused:
        take_back(db, code, clock())
    assert (refused.value.status, refused.value.message) == (409, games.GAME_OVER)
    assert moves_of(db, code) == ["e2e4", "e7e5"]


def test_a_stale_version_is_refused(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, code, clock(), ["e2e4", "e7e5"])
    with pytest.raises(DomainError) as refused:
        take_back(db, code, clock(), version=current(db, code).version - 1)
    assert (refused.value.status, refused.value.message) == (409, games.STALE_VERSION)
    assert moves_of(db, code) == ["e2e4", "e7e5"]


def test_fen_captures_and_version_after_a_takeback(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, code, clock(), ["e2e4", "d7d5", "e4d5", "d8d5"])  # a capture each, then take both back
    before = current(db, code)
    after = take_back(db, code, clock())
    assert after.version == before.version + 1
    assert after.fen == "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    with db.read() as conn:
        view = games.GameView(after, games.load_moves(conn, after.game_id))
    snapshot = view.snapshot(games.RoomView(code, {"A": 0, "B": 0, "draws": 0}, {}, {"state": "none"}), "A")
    assert snapshot["lastCapture"] is None and snapshot["lastMove"] == "d7d5"
    assert snapshot["fen"] == after.fen and snapshot["turn"] == "white"


def test_takebacks_can_repeat_back_to_the_start(db, clock) -> None:
    code, _ = new_computer_room(db, clock(), white_slot="A")
    play(db, code, clock(), ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"])
    for remaining in (4, 2, 0):
        take_back(db, code, clock())
        assert len(moves_of(db, code)) == remaining
    assert current(db, code).fen == games.chess.STARTING_FEN
    play(db, code, clock(), ["d2d4", "d7d5"])  # the game goes on normally afterwards
    assert moves_of(db, code) == ["d2d4", "d7d5"]
