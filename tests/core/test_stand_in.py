"""The computer stand-in: a waiting friend room plays the computer until a friend
joins and takes over the computer's seat (2026-11-15 follow-up).

Domain checks use justchess.rooms/games directly; HTTP checks use the fake UCI engine.
"""

from __future__ import annotations

import pytest

from justchess import DomainError, games, rooms
from tests.fakes.computer_api import (computer_client, computer_clock, move, services_of, state,  # noqa: F401
                                      wait_idle, wait_plies)


def new_room(db, now):
    with db.transaction() as conn:
        room, seat_a, token_a = rooms.create_room(conn, now)
        games.create_first_game(conn, room.code, now)
    return room.code, seat_a, token_a


def set_mode(db, code, seat, mode, now, level=None):
    with db.transaction() as conn:
        return rooms.set_mode(conn, code, seat, mode, now, level=level)


def current(db, code):
    with db.read() as conn:
        return rooms.get_room(conn, code), games.current_game(conn, code), rooms.get_seats(conn, code)


# --- domain -------------------------------------------------------------------

def test_entering_the_stand_in_adds_the_computer_seat_and_starts_an_uncounted_game(db, clock):
    code, seat_a, _ = new_room(db, clock())
    change = set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock(), level="club")
    room, game, seats = current(db, code)
    assert (change.changed, room.mode, room.computer_level) == (True, "computer", "club")
    assert seats["B"].is_computer and seats["B"].token_hash is None
    assert (game.status, game.counted) == ("playing", False)
    with db.read() as conn:
        assert rooms.is_stand_in(conn, code)
    assert set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock()).changed is False, "a repeat changes nothing"


def test_default_level_unknown_level_and_creator_only(db, clock):
    code, seat_a, _ = new_room(db, clock())
    seat_b = rooms.Seat(0, code, "B", "not-a-real-hash", None, None, clock())
    with pytest.raises(DomainError) as err:
        set_mode(db, code, seat_b, rooms.MODE_COMPUTER, clock())
    assert err.value.status == 403
    with pytest.raises(DomainError) as err:
        set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock(), level="grandmaster")
    assert (err.value.status, err.value.message) == (400, rooms.UNKNOWN_LEVEL)
    set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    assert current(db, code)[0].computer_level == rooms.STAND_IN_DEFAULT_LEVEL


def test_refused_after_a_friend_joined_from_pass_along_and_in_a_lobby_computer_room(db, clock):
    code, seat_a, _ = new_room(db, clock())
    with db.transaction() as conn:
        rooms.join_room(conn, code, None, clock())
    with pytest.raises(DomainError) as err:
        set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    assert (err.value.status, err.value.message) == (409, rooms.ALREADY_JOINED)

    other, seat_c, _ = new_room(db, clock())
    set_mode(db, other, seat_c, rooms.MODE_PASS_ALONG, clock())
    with pytest.raises(DomainError) as err:
        set_mode(db, other, seat_c, rooms.MODE_COMPUTER, clock())
    assert (err.value.status, err.value.message) == (409, rooms.WAIT_FIRST)

    with db.transaction() as conn:
        lobby_room, lobby_seat, _ = rooms.create_computer_room(conn, clock(), "casual", "A")
        games.create_computer_game(conn, lobby_room.code, "A", clock())
    with pytest.raises(DomainError) as err:
        set_mode(db, lobby_room.code, lobby_seat, rooms.MODE_WAITING, clock())
    assert (err.value.status, err.value.message) == (409, rooms.COMPUTER_ROOM)
    with pytest.raises(DomainError) as err:
        with db.transaction() as conn:
            rooms.join_room(conn, lobby_room.code, None, clock())
    assert (err.value.status, err.value.message) == (409, rooms.COMPUTER_ROOM)


def test_a_joiner_takes_over_the_computer_seat_in_the_game_under_way(db, clock):
    code, seat_a, token_a = new_room(db, clock())
    set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    with db.transaction() as conn:
        game = games.current_game(conn, code)
        game = games.apply_move(conn, game, "A", "e2e4", game.version, clock(), computer=True)
        game = games.apply_move(conn, game, "B", "e7e5", game.version, clock(), computer=True)
    version_before = game.version
    with db.transaction() as conn:
        joined = rooms.join_room(conn, code, None, clock())
    room, game, seats = current(db, code)
    assert joined.created and joined.seat.slot == "B" and joined.token
    assert (room.mode, room.computer_level) == ("online", None)
    assert not seats["B"].is_computer and rooms.token_matches(joined.token, seats["B"].token_hash)
    assert game.version == version_before + 1, "the takeover discards an engine reply still in flight"
    with db.read() as conn:
        assert not rooms.is_stand_in(conn, code)
        assert len(games.load_moves(conn, game.game_id)) == 2, "the position is kept"
        assert rooms.find_seat(conn, code, token_a).slot == "A"
    with pytest.raises(DomainError):  # a third visitor is refused as in any full room
        with db.transaction() as conn:
            rooms.join_room(conn, code, None, clock())


def test_leaving_the_stand_in_keeps_the_position_for_a_friend(db, clock):
    code, seat_a, _ = new_room(db, clock())
    set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    with db.transaction() as conn:
        game = games.current_game(conn, code)
        games.apply_move(conn, game, "A", "d2d4", game.version, clock(), computer=True)
    change = set_mode(db, code, seat_a, rooms.MODE_WAITING, clock())
    room, game, seats = current(db, code)
    assert (change.changed, room.mode, room.computer_level) == (True, "waiting", None)
    assert "B" not in seats
    with db.read() as conn:
        assert not rooms.is_stand_in(conn, code)
    assert game.status == "playing"
    with db.transaction() as conn:
        joined = rooms.join_room(conn, code, None, clock())
    assert joined.seat.slot == "B" and current(db, code)[0].mode == "online"
    with pytest.raises(DomainError) as err:  # and back to the stand-in is refused now
        set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    assert err.value.status == 409


def test_deleting_a_stand_in_room_removes_its_mark(db, clock):
    code, seat_a, _ = new_room(db, clock())
    set_mode(db, code, seat_a, rooms.MODE_COMPUTER, clock())
    with db.transaction() as conn:
        games.delete_games_for_room(conn, code)
        rooms.delete_room(conn, code)
        assert conn.execute("SELECT COUNT(*) FROM room_stand_ins").fetchone()[0] == 0


# --- HTTP -----------------------------------------------------------------------

def _friend_room(client):
    created = client.post("/api/rooms")
    assert created.status_code == 201, created.text
    return created.json()


def _mode(client, code, token, mode, level=None):
    return client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": mode, "level": level})


def test_http_stand_in_plays_then_a_friend_takes_over(computer_client) -> None:
    client = computer_client(["--delay", "0.05"])
    room = _friend_room(client)
    code, token = room["code"], room["token"]
    answer = _mode(client, code, token, "computer", "beginner")
    assert answer.status_code == 200, answer.text
    snap = answer.json()
    assert (snap["mode"], snap["standIn"], snap["computerLevel"], snap["counted"]) == ("computer", True, "beginner", False)
    assert snap["seats"]["B"]["presence"] == "computer"
    assert move(client, code, token, "e2e4", snap["version"]).status_code == 200
    after = wait_plies(client, code, token, 2)
    assert after["moveList"][0]["black"], "the computer answered"

    joined = client.post(f"/api/rooms/{code}/join", json={"token": None})
    assert joined.status_code == 200, joined.text
    friend = joined.json()
    assert (friend["slot"], friend["colour"]) == ("B", "black")
    wait_idle(client)
    mine = state(client, code, token)
    theirs = state(client, code, friend["token"])
    assert (mine["mode"], mine["standIn"], mine["counted"]) == ("online", False, True)
    assert mine["seats"]["B"]["presence"] != "computer" and mine["computer"] is None
    assert len(theirs["moveList"]) == 1 and theirs["turn"] == "white"
    # The friend now plays seat B themselves; the computer does not answer any more.
    assert move(client, code, token, "g1f3", mine["version"]).status_code == 200
    wait_idle(client)
    assert state(client, code, token)["turn"] == "black"
    assert move(client, code, friend["token"], "b8c6", state(client, code, token)["version"]).status_code == 200


def test_http_a_reply_in_flight_is_discarded_after_the_takeover(computer_client) -> None:
    client = computer_client(["--delay", "0.6"])
    room = _friend_room(client)
    code, token = room["code"], room["token"]
    snap = _mode(client, code, token, "computer").json()
    assert move(client, code, token, "e2e4", snap["version"]).status_code == 200
    friend = client.post(f"/api/rooms/{code}/join", json={"token": None}).json()
    wait_idle(client)
    after = state(client, code, friend["token"])
    assert after["moveList"][0]["black"] is None, "the computer's late reply was not played for the friend"
    assert after["turn"] == "black" and after["legalMoves"]


def test_http_wait_for_a_friend_again_and_uncounted_rematch(computer_client) -> None:
    client = computer_client(["--delay", "0.05"])
    room = _friend_room(client)
    code, token = room["code"], room["token"]
    snap = _mode(client, code, token, "computer").json()
    resign = client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": snap["version"]})
    assert resign.status_code == 200, resign.text
    again = client.post(f"/api/rooms/{code}/rematch", json={"token": token})
    assert again.status_code == 200, again.text
    assert again.json()["counted"] is False and again.json()["score"] == {"A": 0, "B": 0, "draws": 0}
    wait_idle(client)
    back = _mode(client, code, token, "waiting")
    assert back.status_code == 200, back.text
    assert (back.json()["mode"], back.json()["standIn"], back.json()["seats"]["B"]["presence"]) == ("waiting", False, "empty")
    assert _mode(client, code, token, "computer", "nonsense").status_code == 400
    services_of(client)  # the app is still healthy


def test_http_stand_in_refused_while_the_engine_is_unavailable(make_client) -> None:
    client = make_client()  # the core fixture runs without any engine
    room = _friend_room(client)
    answer = _mode(client, room["code"], room["token"], "computer")
    assert (answer.status_code, answer.json()["detail"]) == (503, "The computer is not available right now")
    assert state(client, room["code"], room["token"])["mode"] == "waiting"


def test_http_player_profile_keeps_a_stand_in_room_a_friend_seat(computer_client) -> None:
    """The lobby's Play reopens a level's computer room from the saved seats; a stand-in room is not one."""
    client = computer_client()
    player = client.post("/api/player/create", json={}).json()
    headers = {"X-Player-Token": player["token"]}
    room = _friend_room(client)
    assert client.post("/api/player/seats", json={"code": room["code"], "token": room["token"]}, headers=headers).status_code == 200
    assert _mode(client, room["code"], room["token"], "computer", "club").status_code == 200
    lobby = client.post("/api/rooms", json={"kind": "computer", "level": "club", "colour": "white"}).json()
    client.post("/api/player/seats", json={"code": lobby["code"], "token": lobby["token"]}, headers=headers)
    seats = {seat["code"]: seat for seat in client.post("/api/player/profile", json={}, headers=headers).json()["seats"]}
    assert (seats[room["code"]]["kind"], seats[room["code"]]["computerLevel"]) == ("friend", None)
    assert (seats[lobby["code"]]["kind"], seats[lobby["code"]]["computerLevel"]) == ("computer", "club")
