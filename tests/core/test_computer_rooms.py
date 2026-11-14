"""P2 U4 computer rooms at the data layer (BR3.1-BR3.4, BR3.6): creation, seats, joining, score, rematch."""

from __future__ import annotations

import pytest

from justchess import DomainError, games, rooms
from tests.fakes.computer_rooms import current, new_computer_room, play, room_of

FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]  # White (here the player) is mated


def test_creation_with_white_and_with_black_sets_seats_and_game(db, clock) -> None:
    for white_slot, colour in (("A", "white"), ("B", "black")):
        code, token = new_computer_room(db, clock(), "club", white_slot)
        with db.read() as conn:
            room, seats = rooms.get_room(conn, code), rooms.get_seats(conn, code)
            game = games.current_game(conn, code)
        assert (room.mode, room.computer_level) == ("computer", "club")
        assert set(seats) == {"A", "B"} and seats["B"].is_computer and not seats["A"].is_computer
        assert rooms.token_matches(token, seats["A"].token_hash)
        assert (game.number, game.status, game.white_slot, game.version, game.counted) == (1, "playing", white_slot, 0, True)
        assert game.colour_of("A") == colour


def test_bad_level_or_colour_creates_nothing(db, clock) -> None:
    with db.transaction() as conn:
        with pytest.raises(DomainError) as level:
            rooms.create_computer_room(conn, clock(), "grandmaster", "A")
        with pytest.raises(DomainError) as slot:
            rooms.create_computer_room(conn, clock(), "casual", "C")
        assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0
    assert (level.value.status, level.value.message) == (400, rooms.UNKNOWN_LEVEL)
    assert (slot.value.status, slot.value.message) == (400, rooms.UNKNOWN_SLOT)


def test_computer_seat_has_no_hash_and_no_token_matches_it(db, clock) -> None:
    code, token = new_computer_room(db, clock())
    with db.read() as conn:
        computer_seat = rooms.get_seats(conn, code)["B"]
        assert computer_seat.token_hash is None
        for presented in (None, "", "x" * 43, token):
            found = rooms.find_seat(conn, code, presented)
            assert found is None or found.slot == "A"
        with pytest.raises(DomainError) as refused:
            rooms.authorize_seat(conn, code, None)
    assert refused.value.status == 403


def test_join_is_refused_while_seat_a_rejoins(db, clock) -> None:
    code, token = new_computer_room(db, clock())
    with db.transaction() as conn:
        for stranger in (None, "not-a-seat-token-at-all"):
            with pytest.raises(DomainError) as refused:
                rooms.join_room(conn, code, stranger, clock())
            assert (refused.value.status, refused.value.message) == (409, rooms.COMPUTER_ROOM)
        rejoined = rooms.join_room(conn, code, token, clock())
        assert (rejoined.seat.slot, rejoined.created) == ("A", False)
        assert len(rooms.get_seats(conn, code)) == 2


def test_score_is_recorded_against_the_computer(db, clock) -> None:
    code, _token = new_computer_room(db, clock(), "beginner", "A")
    game = play(db, code, clock(), FOOLS_MATE)
    assert (game.status, game.end_reason, game.result) == ("finished", "checkmate", "0-1")
    room = room_of(db, code)
    assert (room.wins_a, room.wins_b, room.draws) == (0, 1, 0)


def test_rematch_swaps_colours_or_keeps_the_chosen_colour(db, clock) -> None:
    code, _token = new_computer_room(db, clock(), "casual", "A")
    play(db, code, clock(), FOOLS_MATE)
    with db.transaction() as conn:
        second = games.start_computer_rematch(conn, games.current_game(conn, code), clock())
    assert (second.number, second.status, second.white_slot, second.version) == (2, "playing", "B", 0)
    with db.transaction() as conn:
        games.resign(conn, second, "A", clock())
        third = games.start_computer_rematch(conn, games.current_game(conn, code), clock(), "black")
        assert third.white_slot == "B", "the player chose black: the computer keeps white"
        games.resign(conn, third, "A", clock())
        fourth = games.start_computer_rematch(conn, games.current_game(conn, code), clock(), "white")
    assert (fourth.number, fourth.white_slot) == (4, "A")


def test_rematch_before_the_end_is_refused(db, clock) -> None:
    code, _token = new_computer_room(db, clock())
    with db.transaction() as conn:
        with pytest.raises(DomainError) as refused:
            games.start_computer_rematch(conn, games.current_game(conn, code), clock())
    assert (refused.value.status, refused.value.message) == (409, games.NOT_OVER_YET)
    assert current(db, code).number == 1


def test_presence_of_the_computer_seat_is_computer(db, clock) -> None:
    code, _token = new_computer_room(db, clock())
    clock.advance(rooms.ABANDON_AFTER * 3)  # never away or abandoned, however long
    with db.read() as conn:
        seats = rooms.get_seats(conn, code)
    assert rooms.seat_presence(seats["B"], False, clock()) == "computer"
    assert rooms.seat_presence(seats["A"], False, clock()) == "abandoned"


def test_mode_switch_is_refused_in_a_computer_room(db, clock) -> None:
    code, token = new_computer_room(db, clock())
    with db.transaction() as conn:
        seat = rooms.authorize_seat(conn, code, token)
        with pytest.raises(DomainError) as refused:
            rooms.set_mode(conn, code, seat, "pass_along", clock())
    assert (refused.value.status, refused.value.message) == (409, rooms.COMPUTER_ROOM)
    assert room_of(db, code).mode == "computer"
