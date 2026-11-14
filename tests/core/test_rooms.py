"""Tests for justchess.rooms (BR1.1-BR1.7, BR3.1-BR3.3)."""

from __future__ import annotations

import pytest

from justchess import DomainError
from justchess import rooms
from justchess.rooms import (
    ABANDON_AFTER,
    CONTINUE_TTL,
    CODE_PATTERN,
)


def make_room(db, now, code_factory=rooms.generate_code):
    with db.transaction() as conn:
        return rooms.create_room(conn, now, code_factory)


def test_code_format_normalisation_and_collision_retry(db, clock):
    for _ in range(50):
        assert CODE_PATTERN.match(rooms.generate_code())
    assert rooms.normalize_code(" ab12cd ") == "AB12CD"
    for bad in ("ABC12", "ABC1234", "ABC-12", "", "ÄBC123"):
        with pytest.raises(DomainError) as err:
            rooms.normalize_code(bad)
        assert err.value.status == 400

    make_room(db, clock(), lambda: "TAKEN1")
    codes = iter(["TAKEN1", "TAKEN1", "FRESH1"])
    room, seat, _ = make_room(db, clock(), lambda: next(codes))
    assert room.code == "FRESH1" and seat.slot == "A"

    with pytest.raises(DomainError) as err:  # only collisions: give up after 10 tries
        make_room(db, clock(), lambda: "TAKEN1")
    assert err.value.status == 503


def test_third_join_refused_and_rejoin_by_token(db, clock):
    room, seat_a, token_a = make_room(db, clock())
    with db.transaction() as conn:
        joined = rooms.join_room(conn, room.code, None, clock())
    assert joined.created and joined.seat.slot == "B"

    with db.transaction() as conn:
        again = rooms.join_room(conn, room.code, joined.token, clock())
        creator = rooms.join_room(conn, room.code, token_a, clock())
    assert (again.created, again.seat.slot, again.token) == (False, "B", joined.token)
    assert (creator.created, creator.seat.slot) == (False, "A")

    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.join_room(conn, room.code, "someone-else", clock())
    assert (err.value.status, err.value.message) == (409, "This game already has two players")

    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.join_room(conn, "NOPE00", None, clock())
    assert err.value.status == 404


def test_only_token_hash_is_stored_and_wrong_token_refused(db, clock):
    room, _, token = make_room(db, clock())
    assert len(token) >= 22  # at least 128 bits, URL-safe

    with db.read() as conn:
        stored = [tuple(row) for row in conn.execute("SELECT * FROM seats")]
        assert token not in repr(stored)
        assert stored[0][3] == rooms.hash_token(token)
        assert rooms.authorize_seat(conn, room.code, token).slot == "A"
        for wrong in (None, "", token + "x", rooms.hash_token(token)):
            with pytest.raises(DomainError) as err:
                rooms.authorize_seat(conn, room.code, wrong)
            assert (err.value.status, err.value.message) == (403, "This isn't your seat")


def test_continue_redeem_rotates_token_and_old_token_stops_working(db, clock):
    room, seat, token = make_room(db, clock())
    with db.transaction() as conn:
        first = rooms.issue_continue_token(conn, seat, clock())
        second = rooms.issue_continue_token(conn, seat, clock())  # replaces the first

    with db.transaction() as conn:
        with pytest.raises(DomainError):
            rooms.redeem_continue_token(conn, room.code, first, clock())
    with db.transaction() as conn:
        moved = rooms.redeem_continue_token(conn, room.code, second, clock())

    assert moved.seat.slot == "A" and moved.token != token
    assert moved.old_token_hash == rooms.hash_token(token)
    with db.read() as conn:
        assert rooms.find_seat(conn, room.code, token) is None
        assert rooms.find_seat(conn, room.code, moved.token).slot == "A"
        assert "continue" not in repr([tuple(r) for r in conn.execute("SELECT * FROM seats")])
    with pytest.raises(DomainError) as err:  # a used continue token is refused
        with db.transaction() as conn:
            rooms.redeem_continue_token(conn, room.code, second, clock())
    assert err.value.status == 403


def test_expired_continue_token_is_refused(db, clock):
    room, seat, token = make_room(db, clock())
    with db.transaction() as conn:
        link = rooms.issue_continue_token(conn, seat, clock())

    clock.advance(CONTINUE_TTL + 1)
    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.redeem_continue_token(conn, room.code, link, clock())

    assert err.value.status == 403
    with db.read() as conn:
        assert rooms.find_seat(conn, room.code, token) is not None  # seat unchanged


def test_score_follows_slot_across_colour_swap(db, clock):
    room, _, _ = make_room(db, clock())
    with db.transaction() as conn:
        rooms.record_result(conn, room.code, "1-0", white_slot="A")  # A wins as white
        rooms.record_result(conn, room.code, "1-0", white_slot="B")  # B wins as white
        rooms.record_result(conn, room.code, "1-0", white_slot="A")  # A again
        rooms.record_result(conn, room.code, "0-1", white_slot="B")  # A wins as black
        rooms.record_result(conn, room.code, "1/2-1/2", white_slot="A")
        updated = rooms.get_room(conn, room.code)

    assert (updated.wins_a, updated.wins_b, updated.draws) == (3, 1, 1)


def test_rematch_needs_both_seats_and_repeat_is_idempotent(db, clock):
    room, _, _ = make_room(db, clock())
    with db.transaction() as conn:
        with pytest.raises(DomainError) as err:
            rooms.request_rematch(conn, room, "A", game_finished=False, now=clock())
        assert (err.value.status, err.value.message) == (409, "Finish this game first")

        assert rooms.request_rematch(conn, room, "A", True, clock()) == "recorded"
        pending = rooms.get_room(conn, room.code)
        assert rooms.request_rematch(conn, pending, "A", True, clock()) == "unchanged"
        assert rooms.get_room(conn, room.code) == pending
        assert rooms.request_rematch(conn, pending, "B", True, clock()) == "start"
        assert rooms.get_room(conn, room.code).rematch_requested_by is None


def test_rematch_lapses_when_other_seat_abandoned_and_presence(db, clock):
    room, _, _ = make_room(db, clock())
    with db.transaction() as conn:
        rooms.join_room(conn, room.code, None, clock())
        rooms.request_rematch(conn, room, "A", True, clock())

    clock.advance(ABANDON_AFTER + 1)
    with db.read() as conn:
        pending = rooms.get_room(conn, room.code)
        seats = rooms.get_seats(conn, room.code)
    presence = {slot: rooms.seat_presence(seats.get(slot), False, clock()) for slot in "AB"}
    assert presence == {"A": "abandoned", "B": "abandoned"}
    assert rooms.rematch_state(pending, presence) == {"state": "lapsed", "requestedBy": "A"}

    # B comes back: the request reads as pending again (lapsed is never stored)
    with db.transaction() as conn:
        assert rooms.touch_seat(conn, room.code, "B", clock())
        assert not rooms.touch_seat(conn, room.code, "B", clock() + 30)  # throttled
        seats = rooms.get_seats(conn, room.code)
    presence = {slot: rooms.seat_presence(seats.get(slot), slot == "B", clock()) for slot in "AB"}
    assert presence["B"] == "connected"
    assert rooms.seat_presence(seats["B"], False, clock()) == "away"
    assert rooms.seat_presence(None, False, clock()) == "empty"
    assert rooms.rematch_state(pending, presence)["state"] == "pending"


def test_idle_listing_and_delete(db, clock):
    old, _, _ = make_room(db, clock())
    clock.advance(10)
    recent, _, _ = make_room(db, clock())
    with db.transaction() as conn:
        assert rooms.list_idle_rooms(conn, cutoff=clock() - 5) == [old.code]
        rooms.delete_room(conn, old.code)
        assert not rooms.room_exists(conn, old.code)
        assert rooms.room_exists(conn, recent.code)
        assert conn.execute("SELECT count(*) FROM seats").fetchone()[0] == 1


# --- P2 U2: room modes (BR1.2) -------------------------------------------------

def test_new_room_is_waiting_with_no_computer_level(db, clock):
    room, _, token = make_room(db, clock())

    assert (room.mode, room.computer_level) == ("waiting", None)
    with db.transaction() as conn:  # the creator rejoining does not change the mode
        rejoined = rooms.join_room(conn, room.code, token, clock())
        assert not rejoined.created
        assert rooms.get_room(conn, room.code).mode == "waiting"


def test_join_taking_seat_b_turns_the_room_online_in_the_same_transaction(db, clock):
    room, _, _ = make_room(db, clock())

    with pytest.raises(RuntimeError):  # a join rolled back leaves the room waiting
        with db.transaction() as conn:
            rooms.join_room(conn, room.code, None, clock())
            assert rooms.get_room(conn, room.code).mode == "online"
            raise RuntimeError("abort")
    with db.read() as conn:
        assert rooms.get_room(conn, room.code).mode == "waiting"

    with db.transaction() as conn:
        joined = rooms.join_room(conn, room.code, None, clock())
    with db.read() as conn:
        after = rooms.get_room(conn, room.code)
        seats = rooms.get_seats(conn, room.code)
    assert joined.created and after.mode == "online"
    assert not any(seat.is_computer for seat in seats.values())
