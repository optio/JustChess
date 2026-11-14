"""P2 U4 reply races (BR5.1-BR5.6, ADR-009): stale replies are discarded, flags belong to their request.

The fake engine's ``--delay`` holds a reply in flight while the test takes
back, resigns or starts a rematch; each test then waits for the coordinator's
tasks to finish before asserting.
"""

from __future__ import annotations

import chess
from fastapi.testclient import TestClient

from justchess import computer, games, rooms
from tests.fakes.computer_api import (computer_client, computer_clock, create_computer, move, plies,  # noqa: F401
                                      services_of, state, wait_idle, wait_plies, wait_until)


def current_game(client: TestClient, code: str) -> games.Game:
    with services_of(client).db.read() as conn:
        return games.current_game(conn, code)


def test_a_stale_reply_is_discarded_after_a_takeback(computer_client) -> None:
    client = computer_client(["--delay", "0.3"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    flight = services_of(client).coordinator.any_reply(code)
    old = computer.ReplyInFlight(flight.game_id, flight.version, flight.request_id)
    refused = client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": 1})
    assert refused.status_code == 409, "the takeback waits for the flag to clear"
    replied = wait_plies(client, code, token, 2)
    taken = client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": replied["version"]})
    assert taken.status_code == 200 and plies(taken.json()) == 0
    svc = services_of(client)
    with svc.db.transaction() as conn:  # the old search's move arriving now must not land
        applied = svc.apply_reply(conn, svc.clock(), code, old, chess.Move.from_uci("a7a5"))
    assert applied is False
    assert plies(state(client, code, token)) == 0


def test_a_reply_is_discarded_after_a_resign(computer_client) -> None:
    client = computer_client(["--delay", "0.4"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    resigned = client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": 1})
    assert resigned.status_code == 200 and resigned.json()["computer"]["state"] == "idle"
    wait_idle(client)
    after = state(client, code, token)
    assert (after["status"], after["endReason"], plies(after)) == ("finished", "resigned", 1)
    assert services_of(client).coordinator.any_reply(code) is None


def test_resign_then_rematch_with_the_computer_white_gets_its_own_reply(computer_client) -> None:
    client = computer_client(["--delay", "0.5"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    old_request = services_of(client).coordinator.any_reply(code).request_id
    client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": 1})
    rematch = client.post(f"/api/rooms/{code}/rematch", json={"token": token, "colour": "black"})
    assert rematch.status_code == 200
    assert rematch.json()["computer"] == {"state": "queued", "queuePosition": 1, "reason": None, "level": "beginner",
                                          "available": True, "message": None}, "behind the old search"
    new_flight = services_of(client).coordinator.any_reply(code)
    assert new_flight.request_id != old_request and new_flight.game_id == current_game(client, code).game_id
    # The new request starts thinking only once the old search has ended (one search at a time, 0.5 s each).
    running = wait_until(lambda: (lambda f: f if f is not None and f.state == "thinking" else None)(
        services_of(client).coordinator.any_reply(code)), message="the old search to end")
    assert running.request_id == new_flight.request_id, "the old reply left the new flag alone"
    game_two = wait_plies(client, code, token, 1)
    assert (game_two["game"], game_two["colour"], game_two["moveList"][0]["white"]) == (2, "black", "a3")
    with services_of(client).db.read() as conn:
        first = conn.execute("SELECT game_id FROM games WHERE room_code = ? AND number = 1", (code,)).fetchone()[0]
        assert [m.uci for m in games.load_moves(conn, first)] == ["e2e4"], "the old reply was discarded"


def test_resume_asks_once_and_a_second_call_returns_the_state(computer_client) -> None:
    client = computer_client(["--delay", "0.3"])
    svc = services_of(client)
    with svc.db.transaction() as conn:  # a computer-white game with no reply asked for (as after a restart)
        made, _seat, token = rooms.create_computer_room(conn, svc.clock(), "casual", "B")
        games.create_computer_game(conn, made.code, "B", svc.clock())
    code = made.code
    assert state(client, code, token)["computer"]["state"] == "idle"
    first = client.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    assert first.status_code == 200 and first.json()["computer"]["state"] in ("queued", "thinking")
    request_id = svc.coordinator.any_reply(code).request_id
    second = client.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    assert second.json()["computer"]["state"] in ("queued", "thinking")
    assert svc.coordinator.any_reply(code).request_id == request_id, "no second request"
    assert wait_plies(client, code, token, 1)["moveList"][0]["white"] == "a3"
    stranger = client.post(f"/api/rooms/{code}/computer-move", json={"token": "y" * 43})
    assert stranger.status_code == 403


def test_a_failed_reply_leaves_the_game_unchanged_and_sets_the_backoff(computer_client, computer_clock) -> None:
    client = computer_client(["--illegal"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    wait_idle(client)
    after = state(client, code, token)
    assert (plies(after), after["version"], after["computer"]["state"]) == (1, 1, "idle")
    svc = services_of(client)
    assert svc.coordinator.in_backoff(code)
    held = client.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    assert held.json()["computer"]["state"] == "idle" and svc.coordinator.any_reply(code) is None
    computer_clock.advance(5)
    asked = client.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    assert asked.json()["computer"]["state"] in ("queued", "thinking"), "asked again once the backoff ends"
    wait_idle(client)
    assert plies(state(client, code, token)) == 1


def test_a_failed_reply_for_an_old_game_sets_no_backoff(computer_client) -> None:
    client = computer_client(["--illegal", "--delay", "0.4"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)  # this reply will fail, but only after the game has moved on
    client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": 1})
    rematch = client.post(f"/api/rooms/{code}/rematch", json={"token": token, "colour": "white"})
    assert rematch.status_code == 200 and rematch.json()["game"] == 2
    wait_idle(client)
    svc = services_of(client)
    assert svc.coordinator.in_backoff(code) is False, "the new game is not held up by the old game's failure"
    move(client, code, token, "d2d4", 0)  # the new game's own failure still sets it
    wait_idle(client)
    assert svc.coordinator.in_backoff(code) is True


def test_the_reply_is_asked_again_after_a_restart(computer_client, tmp_path) -> None:
    db_path = tmp_path / "restart.sqlite3"
    first = computer_client(["--delay", "5"], db_path=db_path)
    room = create_computer(first, colour="white")
    code, token = room["code"], room["token"]
    move(first, code, token, "e2e4", 0)
    assert services_of(first).coordinator.any_reply(code) is not None
    first.__exit__(None, None, None)  # shut the first app down: the flag and the search are gone

    second = computer_client([], db_path=db_path)
    before = state(second, code, token)
    assert (plies(before), before["turn"], before["computer"]["state"]) == (1, "black", "idle")
    resumed = second.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    assert resumed.json()["computer"]["state"] in ("queued", "thinking")
    assert wait_plies(second, code, token, 2)["moveList"][0]["black"] == "a5"
