"""P2 U3 join requests in the domain module (BR2.1-BR2.4): justchess.rooms and housekeeping's lapse."""

from __future__ import annotations

import pytest

from justchess import DomainError, games, housekeeping, rooms


def pass_along_room(db, now):
    """A room with seat A, game 1, switched to pass-along."""
    with db.transaction() as conn:
        room, seat_a, token_a = rooms.create_room(conn, now)
        games.create_first_game(conn, room.code, now)
        rooms.set_mode(conn, room.code, seat_a, rooms.MODE_PASS_ALONG, now)
    return room.code, seat_a, token_a


def ask(db, code, now, token=None, declined_recently=False):
    with db.transaction() as conn:
        return rooms.create_join_request(conn, code, token, now, declined_recently)


def answer(db, code, seat, accept, now, addresses=None):
    with db.transaction() as conn:
        return rooms.answer_request(conn, code, seat, accept, now, addresses)


def status_of(db, code, token, now):
    with db.transaction() as conn:
        return rooms.request_status(conn, code, token, now)


def test_a_request_is_created_with_a_fresh_token_whose_hash_alone_is_stored(db, clock):
    code, _, _ = pass_along_room(db, clock())
    outcome = ask(db, code, clock())
    assert outcome.kind == "created" and len(outcome.token) >= 22
    assert outcome.request.expires_at == clock() + rooms.REQUEST_TTL
    with db.read() as conn:
        rows = [tuple(row) for row in conn.execute("SELECT * FROM join_requests")]
    assert outcome.token not in repr(rows)
    assert rows[0][2] == rooms.hash_token(outcome.token) and rows[0][3] == "pending"


def test_a_second_visitor_gets_busy_while_a_request_is_pending(db, clock):
    code, _, _ = pass_along_room(db, clock())
    ask(db, code, clock())
    busy = ask(db, code, clock() + 5)
    assert (busy.kind, busy.token, busy.request) == ("busy", None, None)
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM join_requests").fetchone()[0] == 1


def test_the_same_visitor_gets_its_pending_request_back_with_the_same_expiry(db, clock):
    code, _, _ = pass_along_room(db, clock())
    first = ask(db, code, clock())
    clock.advance(30)
    again = ask(db, code, clock(), token=first.token)
    assert again.kind == "existing"
    assert (again.request.request_id, again.request.expires_at, again.token) == (
        first.request.request_id, first.request.expires_at, first.token)


def test_accept_makes_the_request_token_a_working_seat_token_for_b(db, clock):
    code, seat_a, token_a = pass_along_room(db, clock())
    outcome = ask(db, code, clock())
    result = answer(db, code, seat_a, True, clock())
    assert result.kind == "accepted" and result.seat.slot == "B"
    with db.read() as conn:
        assert rooms.authorize_seat(conn, code, outcome.token).slot == "B"
        assert rooms.authorize_seat(conn, code, token_a).slot == "A"
        room, game = rooms.get_room(conn, code), games.current_game(conn, code)
    assert (room.mode, game.counted) == ("online", True)
    assert status_of(db, code, outcome.token, clock())[0]["status"] == "accepted"


def test_decline_then_the_same_address_is_declined_recently_for_ten_minutes(db, clock):
    code, seat_a, _ = pass_along_room(db, clock())
    addresses = rooms.RequestAddressBook()
    outcome = ask(db, code, clock())
    addresses.note_request(outcome.request.request_id, "203.0.113.7")
    assert answer(db, code, seat_a, False, clock(), addresses).kind == "declined"
    assert status_of(db, code, outcome.token, clock())[0]["status"] == "declined"

    assert addresses.declined_recently(code, "203.0.113.7", clock() + 60)
    assert not addresses.declined_recently(code, "198.51.100.1", clock() + 60), "another address may ask"
    blocked = ask(db, code, clock() + 60, declined_recently=addresses.declined_recently(code, "203.0.113.7", clock() + 60))
    assert blocked.kind == "declined_recently"
    assert not addresses.declined_recently(code, "203.0.113.7", clock() + rooms.DECLINE_MEMORY)


def test_a_request_lapses_on_read_and_through_housekeeping(db, clock):
    code, _, _ = pass_along_room(db, clock())
    outcome = ask(db, code, clock())
    clock.advance(rooms.REQUEST_TTL)
    status, lapsed = status_of(db, code, outcome.token, clock())
    assert (status["status"], lapsed) == ("lapsed", True)
    assert ask(db, code, clock()).kind == "created", "a lapsed request frees the room"

    other, _, _ = pass_along_room(db, clock())
    left = ask(db, other, clock())
    clock.advance(rooms.REQUEST_TTL + 1)
    assert housekeeping.run_lapse(db, clock()) == 2  # both rooms' pending requests are past their expiry
    with db.read() as conn:
        assert rooms.visible_request(conn, other, clock()) is None
    assert status_of(db, other, left.token, clock()) == ({"status": "lapsed", "expiresAt": left.request.expires_at}, False)


def test_only_seat_a_can_answer(db, clock):
    code, _, _ = pass_along_room(db, clock())
    ask(db, code, clock())
    stranger = rooms.Seat(0, code, "B", "not-a-real-hash", None, None, clock())
    with pytest.raises(DomainError) as err:
        answer(db, code, stranger, True, clock())
    assert (err.value.status, err.value.message) == (403, rooms.CREATOR_ONLY)


def test_a_stale_accept_after_switching_back_finds_no_pending_request(db, clock):
    code, seat_a, _ = pass_along_room(db, clock())
    outcome = ask(db, code, clock())
    with db.transaction() as conn:
        rooms.set_mode(conn, code, seat_a, rooms.MODE_WAITING, clock())
    assert answer(db, code, seat_a, True, clock()).kind == "none"
    with db.read() as conn:
        assert rooms.find_seat(conn, code, outcome.token) is None
        assert "B" not in rooms.get_seats(conn, code)

    lapsing, seat_l, _ = pass_along_room(db, clock())
    ask(db, lapsing, clock())
    clock.advance(rooms.REQUEST_TTL)
    late = answer(db, lapsing, seat_l, True, clock())
    assert (late.kind, late.lapsed) == ("none", True), "an accept after expiry lapses the request and accepts nothing"


def test_status_for_unknown_pending_accepted_and_lapsed(db, clock):
    code, seat_a, _ = pass_along_room(db, clock())
    assert status_of(db, code, "no-such-request-token", clock()) == ({"status": "unknown"}, False)
    assert status_of(db, code, None, clock()) == ({"status": "unknown"}, False)
    first = ask(db, code, clock())
    assert status_of(db, code, first.token, clock())[0] == {"status": "pending", "expiresAt": first.request.expires_at}
    other, _, _ = pass_along_room(db, clock())
    assert status_of(db, other, first.token, clock())[0] == {"status": "unknown"}, "a token is bound to its room"
    answer(db, code, seat_a, True, clock())
    assert status_of(db, code, first.token, clock())[0]["status"] == "accepted"
    with pytest.raises(DomainError) as err:
        status_of(db, "NOPE00", first.token, clock())
    assert err.value.status == 404
