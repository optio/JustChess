"""P2 U3 pass-along mode in the domain modules (BR1.1-BR1.5): justchess.rooms and justchess.games."""

from __future__ import annotations

import pytest

from justchess import DomainError, games, rooms


def new_room(db, now):
    """A room with seat A and game 1 (waiting), as POST /api/rooms makes it."""
    with db.transaction() as conn:
        room, seat_a, token_a = rooms.create_room(conn, now)
        games.create_first_game(conn, room.code, now)
    return room.code, seat_a, token_a


def enter_pass_along(db, code, seat_a, now):
    with db.transaction() as conn:
        return rooms.set_mode(conn, code, seat_a, rooms.MODE_PASS_ALONG, now)


def current(db, code):
    with db.read() as conn:
        return rooms.get_room(conn, code), games.current_game(conn, code)


def play(db, code, slot, uci, now, pass_along=True):
    with db.transaction() as conn:
        game = games.current_game(conn, code)
        return games.apply_move(conn, game, slot, uci, game.version, now, pass_along=pass_along)


def test_only_seat_a_can_switch_mode_and_entering_starts_an_uncounted_game(db, clock):
    code, seat_a, _ = new_room(db, clock())
    seat_b = rooms.Seat(0, code, "B", "not-a-real-hash", None, None, clock())
    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.set_mode(conn, code, seat_b, rooms.MODE_PASS_ALONG, clock())
    assert (err.value.status, err.value.message) == (403, rooms.CREATOR_ONLY)
    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.set_mode(conn, code, seat_a, "online", clock())
    assert err.value.status == 400

    change = enter_pass_along(db, code, seat_a, clock())
    room, game = current(db, code)
    assert (change.changed, room.mode) == (True, "pass_along")
    assert (game.status, game.counted, game.version) == ("playing", False, 1)
    assert enter_pass_along(db, code, seat_a, clock()).changed is False, "a repeat changes nothing"


def test_switching_is_refused_once_seat_b_exists_and_in_a_computer_room(db, clock):
    code, seat_a, _ = new_room(db, clock())
    with db.transaction() as conn:
        rooms.join_room(conn, code, None, clock())
    with pytest.raises(DomainError) as err:
        enter_pass_along(db, code, seat_a, clock())
    assert (err.value.status, err.value.message) == (409, "A friend has already joined")

    other, seat_c, _ = new_room(db, clock())
    with db.transaction() as conn:
        conn.execute("UPDATE rooms SET mode = 'computer', computer_level = 'casual' WHERE code = ?", (other,))
    with pytest.raises(DomainError) as err:
        enter_pass_along(db, other, seat_c, clock())
    assert (err.value.status, err.value.message) == (409, rooms.COMPUTER_ROOM)


def test_both_colours_move_in_pass_along_and_only_your_colour_otherwise(db, clock):
    code, seat_a, _ = new_room(db, clock())
    enter_pass_along(db, code, seat_a, clock())
    play(db, code, "A", "e2e4", clock())
    after_black = play(db, code, "A", "e7e5", clock())
    assert after_black.version == 3

    with db.transaction() as conn:  # back to waiting: seat A plays White only again
        rooms.set_mode(conn, code, seat_a, rooms.MODE_WAITING, clock())
    play(db, code, "A", "g1f3", clock(), pass_along=False)
    with pytest.raises(DomainError) as err:
        play(db, code, "A", "b8c6", clock(), pass_along=False)
    assert (err.value.status, err.value.message) == (403, games.NOT_YOUR_TURN)
    with pytest.raises(DomainError):  # seat B never moves White, pass-along or not
        play(db, code, "B", "b1c3", clock(), pass_along=True)


def test_counted_turns_true_when_seat_b_is_taken_but_a_finished_practice_game_stays_uncounted(db, clock):
    code, seat_a, _ = new_room(db, clock())
    enter_pass_along(db, code, seat_a, clock())
    with db.transaction() as conn:
        rooms.set_mode(conn, code, seat_a, rooms.MODE_WAITING, clock())
        # With no move made, going back to waiting makes the game wait again, counted (2026-11-15 fix).
        assert games.current_game(conn, code).status == "waiting"
        rooms.join_room(conn, code, None, clock())
        assert games.mark_counted(conn, games.current_game(conn, code)) is False, "already counted"
    assert current(db, code)[1].counted is True

    finished, seat_f, _ = new_room(db, clock())
    enter_pass_along(db, finished, seat_f, clock())
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        play(db, finished, "A", uci, clock())
    with db.transaction() as conn:
        game = games.current_game(conn, finished)
        assert game.status == "finished"
        assert games.mark_counted(conn, game) is False
    assert current(db, finished)[1].counted is False


def test_no_score_is_recorded_while_the_game_is_uncounted(db, clock):
    code, _, _ = new_room(db, clock())
    with db.transaction() as conn:
        rooms.record_result(conn, code, "1-0", "A", counted=False)
        rooms.record_result(conn, code, "0-1", "A", counted=True)
        room = rooms.get_room(conn, code)
    assert (room.wins_a, room.wins_b, room.draws) == (0, 1, 0)


def test_leaving_pass_along_keeps_the_position_and_declines_the_pending_request(db, clock):
    code, seat_a, _ = new_room(db, clock())
    enter_pass_along(db, code, seat_a, clock())
    play(db, code, "A", "d2d4", clock())
    with db.transaction() as conn:
        outcome = rooms.create_join_request(conn, code, None, clock())
    with db.transaction() as conn:
        change = rooms.set_mode(conn, code, seat_a, rooms.MODE_WAITING, clock())
        status, _ = rooms.request_status(conn, code, outcome.token, clock())
    room, game = current(db, code)
    assert (change.changed, change.declined_request) == (True, True)
    assert status["status"] == "declined"
    assert (room.mode, game.status, game.version) == ("waiting", "playing", 3), "position kept; version bumped on the way back"


def test_play_again_in_pass_along_needs_no_second_seat_and_stays_uncounted(db, clock):
    code, seat_a, _ = new_room(db, clock())
    enter_pass_along(db, code, seat_a, clock())
    with db.transaction() as conn:
        with pytest.raises(DomainError) as err:
            games.start_pass_along_rematch(conn, games.current_game(conn, code), clock())
        assert (err.value.status, err.value.message) == (409, "Finish this game first")
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        play(db, code, "A", uci, clock())
    with db.transaction() as conn:
        nxt = games.start_pass_along_rematch(conn, games.current_game(conn, code), clock())
    assert (nxt.number, nxt.white_slot, nxt.status, nxt.counted) == (2, "B", "playing", False)
    play(db, code, "A", "e2e4", clock())  # seat A now moves White's pieces for seat B's colour too


def test_snapshot_carries_the_mode_and_gives_seat_a_the_legal_moves_of_either_colour(db, clock):
    code, seat_a, _ = new_room(db, clock())
    enter_pass_along(db, code, seat_a, clock())
    play(db, code, "A", "e2e4", clock())
    with db.read() as conn:
        room = rooms.get_room(conn, code)
        game = games.current_game(conn, code)
        view = games.GameView(game, games.load_moves(conn, game.game_id))
    room_view = games.RoomView(code, {"A": 0, "B": 0, "draws": 0}, {"A": "connected", "B": "empty"},
                               {"state": "none", "requestedBy": None}, mode=room.mode,
                               join_request={"expiresAt": 1.0, "expiresIn": 1.0})
    seat_view, watcher = view.snapshot(room_view, "A"), view.snapshot(room_view, None)
    assert (seat_view["mode"], seat_view["turn"], seat_view["counted"]) == ("pass_along", "black", False)
    assert "e7e5" in seat_view["legalMoves"], "seat A gets Black's moves in pass-along"
    assert seat_view["joinRequest"] == {"expiresAt": 1.0, "expiresIn": 1.0}
    assert (watcher["legalMoves"], watcher["joinRequest"]) == ([], None)
