"""P2 U4 computer HTTP flows with the fake UCI engine (W1-W7, BR3.x, BR4.x, BR5.5, BR6.1, BR7.1, BR7.2)."""

from __future__ import annotations

import asyncio
import logging

import chess

from justchess import api, engine as engine_module, games, rooms
from justchess.engine import Engine
from tests.fakes.computer_api import (computer_client, computer_clock, create_computer, move, plies,  # noqa: F401
                                      services_of, state, wait_idle, wait_plies, wait_until)
from tests.fakes.engines import AlwaysRandom, fake_opener


def test_create_play_and_the_reply_arrives(computer_client) -> None:
    client = computer_client(["--delay", "0.1"])
    room = create_computer(client, level="beginner", colour="white")
    assert (room["slot"], room["colour"]) == ("A", "white")
    assert room["computer"] == {"state": "idle", "queuePosition": None, "reason": None, "level": "beginner",
                                "available": True, "message": None}
    answer = move(client, room["code"], room["token"], "e2e4", 0)
    assert answer.status_code == 200, answer.text
    assert answer.json()["computer"]["state"] in ("queued", "thinking")
    after = wait_plies(client, room["code"], room["token"], 2)
    assert after["moveList"][0] == {"number": 1, "white": "e4", "black": "a5"}  # the fake's first legal move
    assert after["computer"]["state"] == "idle" and after["turn"] == "white" and after["legalMoves"]
    assert after["seats"]["B"]["presence"] == "computer" and after["mode"] == "computer"


def test_a_level_random_roll_replaces_the_engine_reply_but_not_at_maximum(computer_client) -> None:
    client = computer_client([], move_chooser=AlwaysRandom())
    beginner = create_computer(client, level="beginner", colour="white")  # random-move chance 0.35
    move(client, beginner["code"], beginner["token"], "e2e4", 0)
    replied = wait_plies(client, beginner["code"], beginner["token"], 2)
    assert replied["moveList"][0]["black"] == "h6", "the last other legal move in UCI order, not the engine's a5"
    maximum = create_computer(client, level="maximum", colour="white")  # chance 0: the engine's move stands
    move(client, maximum["code"], maximum["token"], "e2e4", 0)
    assert wait_plies(client, maximum["code"], maximum["token"], 2)["moveList"][0]["black"] == "a5"


def test_bad_kind_level_or_colour_is_400_and_random_uses_the_chooser(computer_client) -> None:
    client = computer_client([], chooser=lambda colours: "black")
    for body in ({"kind": "computer", "level": "grandmaster", "colour": "white"},
                 {"kind": "computer", "level": "club", "colour": "purple"},
                 {"kind": "computer", "level": "club"},
                 {"kind": "robot"}):
        response = client.post("/api/rooms", json=body)
        assert response.status_code == 400, body
    room = create_computer(client, level="club", colour="random")
    assert room["colour"] == "black"
    first = wait_plies(client, room["code"], room["token"], 1)  # the computer plays white and moves at once
    assert first["colour"] == "black" and first["turn"] == "black"
    friend = client.post("/api/rooms")
    assert friend.status_code == 201 and friend.json()["colour"] == "white", "friend rooms are unchanged"


def test_503_while_the_engine_is_unavailable(computer_client) -> None:
    missing = computer_client(installed=False)
    refused = missing.post("/api/rooms", json={"kind": "computer", "level": "casual", "colour": "white"})
    assert (refused.status_code, refused.json()["detail"]) == (503, "No chess engine is installed")
    assert missing.get("/api/engine").json() == {"available": False, "path_source": None, "version": None,
                                                 "reason": "No chess engine is installed"}

    client = computer_client([])
    room = create_computer(client, colour="white")
    services_of(client).engine._make_unavailable(engine_module.STOPPED_WORKING)
    blocked = move(client, room["code"], room["token"], "e2e4", 0)
    assert (blocked.status_code, blocked.json()["detail"]) == (503, api.ENGINE_DOWN)
    snapshot = state(client, room["code"], room["token"])
    assert plies(snapshot) == 0
    assert snapshot["computer"]["state"] == "unavailable"
    assert snapshot["computer"]["reason"] == "The computer stopped working"
    resigned = client.post(f"/api/rooms/{room['code']}/resign", json={"token": room["token"], "version": 0})
    assert resigned.status_code == 200 and resigned.json()["endReason"] == "resigned", "resign still works"


def test_hint_flow_and_its_errors(computer_client, monkeypatch) -> None:
    client = computer_client(["--delay", "0.4"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    hint = client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 0})
    assert hint.status_code == 200, hint.text
    body = hint.json()
    assert chess.Move.from_uci(body["uci"]) in chess.Board().legal_moves
    assert (body["from"], body["to"], body["version"]) == (body["uci"][:2], body["uci"][2:4], 0)
    assert body["san"] == chess.Board().san(chess.Move.from_uci(body["uci"]))
    assert plies(state(client, code, token)) == 0, "a hint changes nothing"

    stale = client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 5})
    assert stale.status_code == 409 and stale.json()["snapshot"]["version"] == 0

    svc = services_of(client)
    svc.coordinator.begin_hint(code)
    pending = client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 0})
    assert (pending.status_code, pending.json()["detail"]) == (409, api.HINT_PENDING)
    svc.coordinator.end_hint(code)

    monkeypatch.setattr(svc.engine, "queued_count", lambda: 16)
    busy = client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 0})
    assert (busy.status_code, busy.json()["detail"]) == (503, engine_module.BUSY)
    monkeypatch.undo()

    move(client, code, token, "e2e4", 0)  # the computer is now to move, its reply in flight
    computers_turn = client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 1})
    assert (computers_turn.status_code, computers_turn.json()["detail"]) == (409, api.COMPUTERS_TURN)
    wait_plies(client, code, token, 2)


def test_a_hint_whose_client_goes_away_is_cancelled() -> None:
    class GoneRequest:
        async def is_disconnected(self) -> bool:
            return True

    async def scenario():
        engine = Engine(fake_opener(["--delay", "2"]))
        await engine.start("fake")
        running = engine.submit(chess.Board(), 0, 0.05)
        await asyncio.sleep(0.05)
        waiting = engine.submit(chess.Board(), 20, 0.5)
        try:
            await api._await_hint(GoneRequest(), waiting)
        except api.DomainError as error:
            outcome = (error.status, error.message)
        queued_after = engine.queued_count()
        await engine.stop()
        await asyncio.gather(running.result(), return_exceptions=True)
        return outcome, queued_after, waiting._request.future.cancelled()

    outcome, queued_after, cancelled = asyncio.run(scenario())
    assert outcome == (409, api.HINT_CANCELLED)
    assert queued_after == 0 and cancelled, "the queued hint left the queue"


def test_takeback_and_resign_over_http(computer_client) -> None:
    client = computer_client(["--delay", "0.4"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    in_flight = client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": 1})
    assert (in_flight.status_code, in_flight.json()["detail"]) == (409, games.WAIT_FOR_COMPUTER)
    replied = wait_plies(client, code, token, 2)
    taken = client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": replied["version"]})
    assert taken.status_code == 200 and plies(taken.json()) == 0 and taken.json()["version"] == replied["version"] + 1
    resigned = client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": taken.json()["version"]})
    assert resigned.status_code == 200
    assert (resigned.json()["result"], resigned.json()["score"]) == ("0-1", {"A": 0, "B": 1, "draws": 0})
    again = client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": resigned.json()["version"]})
    assert (again.status_code, again.json()["detail"]) == (409, games.GAME_OVER)
    friend = client.post("/api/rooms").json()
    refused = client.post(f"/api/rooms/{friend['code']}/takeback", json={"token": friend["token"], "version": 0})
    assert (refused.status_code, refused.json()["detail"]) == (409, api.TAKEBACK_ONLY)
    assert client.post(f"/api/rooms/{code}/takeback", json={"token": "x" * 43, "version": 0}).status_code == 403


def test_claims_are_refused_and_rematch_takes_a_colour(computer_client) -> None:
    client = computer_client([])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    for route in ("claim-draw", "claim-win"):
        refused = client.post(f"/api/rooms/{code}/{route}", json={"token": token})
        assert (refused.status_code, refused.json()["detail"]) == (409, api.NOT_FOR_COMPUTER), route
    early = client.post(f"/api/rooms/{code}/rematch", json={"token": token})
    assert (early.status_code, early.json()["detail"]) == (409, games.NOT_OVER_YET)
    client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": 0})
    second = client.post(f"/api/rooms/{code}/rematch", json={"token": token, "colour": "white"})
    assert second.status_code == 200 and (second.json()["game"], second.json()["colour"]) == (2, "white")
    bad = client.post(f"/api/rooms/{code}/rematch", json={"token": token, "colour": "green"})
    assert (bad.status_code, bad.json()["detail"]) == (400, api.UNKNOWN_COLOUR)
    joined = client.post(f"/api/rooms/{code}/join", json={})
    assert (joined.status_code, joined.json()["detail"]) == (409, rooms.COMPUTER_ROOM)


def test_computer_state_in_the_snapshot_and_socket_events(computer_client) -> None:
    client = computer_client(["--delay", "0.3"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    assert state(client, code)["computer"]["level"] == "beginner", "watchers see the computer too"
    friend = client.post("/api/rooms").json()
    assert state(client, friend["code"], friend["token"])["computer"] is None
    with client.websocket_connect(f"/ws/{code}") as ws:
        ws.send_json({"type": "hello", "token": token, "visible": True})
        assert ws.receive_json()["type"] == "state"
        move(client, code, token, "e2e4", 0)
        seen = []
        while True:
            message = ws.receive_json()
            seen.append(message)
            if message["type"] == "state" and plies(message) == 2:
                break
        events = [m for m in seen if m["type"] == "computer"]
        assert {"type": "computer", "state": "thinking", "queuePosition": None} in events
        assert any(m["type"] == "state" and m["computer"]["state"] in ("queued", "thinking") for m in seen)
        wait_idle(client)
        version = state(client, code, token)["version"]
        client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": version})
        assert ws.receive_json() == {"type": "takeback"}
        after = ws.receive_json()
        assert after["type"] == "state" and plies(after) == 0


def test_no_token_appears_in_the_logs(computer_client, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    client = computer_client(["--illegal"])
    room = create_computer(client, colour="white")
    code, token = room["code"], room["token"]
    move(client, code, token, "e2e4", 0)
    wait_idle(client)
    client.post(f"/api/rooms/{code}/hint", json={"token": token, "version": 1})
    client.post(f"/api/rooms/{code}/computer-move", json={"token": token})
    client.post(f"/api/rooms/{code}/takeback", json={"token": token, "version": 1})
    client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": 2})
    wait_idle(client)
    assert f"The computer's reply in room {code} failed: The computer did not find a legal move" in caplog.text
    assert token not in caplog.text
    assert rooms.hash_token(token) not in caplog.text
