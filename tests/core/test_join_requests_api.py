"""P2 U3 pass-along and join requests over HTTP (BR1.1, BR2.1-BR2.5, BR3.1, NFR4): justchess.api."""

from __future__ import annotations

import logging

from tests.core.conftest import create_room, join_room, move

MODE = "/api/rooms/{code}/mode"
ANSWER = "/api/rooms/{code}/join-request/answer"
STATUS = "/api/rooms/{code}/join-request/status"


def pass_along(client) -> tuple[str, str]:
    room = create_room(client)
    response = client.post(MODE.format(code=room["code"]), json={"token": room["token"], "mode": "pass_along"})
    assert response.status_code == 200, response.text
    return room["code"], room["token"]


def ask(client, code, token=None):
    return client.post(f"/api/rooms/{code}/join", json={"token": token} if token else {})


def state(client, code, token=None):
    headers = {"X-Seat-Token": token} if token else {}
    response = client.get(f"/api/rooms/{code}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_http_flow_mode_request_status_accept_then_the_request_token_is_seat_b(make_client):
    client = make_client()
    code, token_a = pass_along(client)
    snap = state(client, code, token_a)
    assert (snap["mode"], snap["status"], snap["counted"]) == ("pass_along", "playing", False)
    assert move(client, code, token_a, "e2e4", snap["version"]).status_code == 200
    assert move(client, code, token_a, "e7e5", snap["version"] + 1).status_code == 200, "seat A plays Black too"

    asked = ask(client, code)
    assert asked.status_code == 202, asked.text
    body = asked.json()
    request_token = body["requestToken"]
    assert body["requestPending"] is True and body["expiresIn"] == 600 and body["colour"] == "black"
    assert client.post(STATUS.format(code=code), json={"requestToken": request_token}).json() == {
        "status": "pending", "expiresAt": body["expiresAt"]}
    assert state(client, code, token_a)["joinRequest"]["expiresAt"] == body["expiresAt"]

    accepted = client.post(ANSWER.format(code=code), json={"token": token_a, "accept": True})
    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["mode"], accepted.json()["joinRequest"], accepted.json()["counted"]) == ("online", None, True)
    assert client.post(STATUS.format(code=code), json={"requestToken": request_token}).json()["status"] == "accepted"
    joiner = state(client, code, request_token)
    assert (joiner["slot"], joiner["colour"]) == ("B", "black")
    assert move(client, code, token_a, "g1f3", joiner["version"]).status_code == 200
    assert move(client, code, request_token, "b8c6", joiner["version"] + 1).status_code == 200, "the joiner moves as B"


def test_refusals_403_and_409(make_client):
    client = make_client()
    code, token_a = pass_along(client)
    assert client.post(MODE.format(code=code), json={"token": "not-a-seat-token", "mode": "waiting"}).status_code == 403
    assert client.post(MODE.format(code=code), json={"token": token_a, "mode": "computer"}).status_code == 400
    none = client.post(ANSWER.format(code=code), json={"token": token_a, "accept": True})
    assert (none.status_code, none.json()["detail"]) == (409, "No pending request")
    assert none.json()["snapshot"]["mode"] == "pass_along", "a 409 carries the latest snapshot"

    request_token = ask(client, code).json()["requestToken"]
    busy = ask(client, code)
    assert (busy.status_code, busy.json()["error"]) == (409, "busy")
    client.post(ANSWER.format(code=code), json={"token": token_a, "accept": True})
    by_b = client.post(ANSWER.format(code=code), json={"token": request_token, "accept": False})
    assert (by_b.status_code, by_b.json()["detail"]) == (403, "Only the creator can do this")
    again = client.post(MODE.format(code=code), json={"token": token_a, "mode": "pass_along"})
    assert (again.status_code, again.json()["detail"]) == (409, "A friend has already joined")
    assert client.post(STATUS.format(code="NOPE00"), json={"requestToken": request_token}).status_code == 404


def test_the_sixth_join_attempt_in_a_minute_gets_429(make_client, clock):
    client = make_client()
    code, _ = pass_along(client)
    answers = [ask(client, code).status_code for _ in range(5)]
    assert answers == [202, 409, 409, 409, 409]
    limited = ask(client, code)
    assert (limited.status_code, limited.json()["error"], limited.headers["Retry-After"]) == (429, "too_many", "60")
    assert limited.json()["detail"] == "Too many requests. Try again shortly."
    clock.advance(60)
    assert ask(client, code).status_code == 409, "the window slid: the room is still busy, but no longer limited"


def test_the_creator_rejoining_with_its_seat_token_creates_no_request(make_client):
    client = make_client()
    code, token_a = pass_along(client)
    rejoined = join_room(client, code, token_a)
    assert (rejoined["slot"], rejoined["token"]) == ("A", token_a)
    assert state(client, code, token_a)["joinRequest"] is None
    assert ask(client, code).status_code == 202, "the room is still free for a request"


def test_join_request_appears_only_in_seat_as_snapshot_and_lapses_on_read(make_client, clock):
    client = make_client()
    code, token_a = pass_along(client)
    request_token = ask(client, code).json()["requestToken"]
    assert state(client, code, token_a)["joinRequest"]["expiresIn"] == 600
    assert state(client, code)["joinRequest"] is None, "a watcher never sees it"
    assert state(client, code, request_token)["joinRequest"] is None, "nor does the joiner"

    with client.websocket_connect(f"/ws/{code}") as ws:
        ws.send_json({"type": "hello", "token": token_a, "visible": True})
        first = ws.receive_json()
        assert (first["type"], first["joinRequest"]["expiresIn"]) == ("state", 600)
        clock.advance(600)
        assert state(client, code, token_a)["joinRequest"] is None
        broadcast = ws.receive_json()
        if broadcast["joinRequest"] is not None:  # seat A's own presence change may come first
            broadcast = ws.receive_json()
        assert (broadcast["type"], broadcast["joinRequest"]) == ("state", None), "the lapse on read is broadcast"
    assert client.post(STATUS.format(code=code), json={"requestToken": request_token}).json()["status"] == "lapsed"


def test_no_token_reaches_the_logs(make_client, caplog):
    client = make_client()
    with caplog.at_level(logging.DEBUG):
        code, token_a = pass_along(client)
        request_token = ask(client, code).json()["requestToken"]
        ask(client, code)  # busy
        client.post(STATUS.format(code=code), json={"requestToken": request_token})
        client.post(ANSWER.format(code=code), json={"token": token_a, "accept": False})
        client.post(ANSWER.format(code=code), json={"token": token_a, "accept": True})  # 409
        client.post(MODE.format(code=code), json={"token": request_token, "mode": "waiting"})  # 403
    assert caplog.records, "the flow logs something, so the check below means something"
    for secret in (token_a, request_token):
        assert secret not in caplog.text
    assert code in caplog.text


def test_cross_origin_posts_to_the_new_routes_are_refused(make_client):
    client = make_client()
    code, token_a = pass_along(client)
    evil = {"Origin": "https://evil.example"}
    for path, body in ((MODE, {"token": token_a, "mode": "waiting"}),
                       (ANSWER, {"token": token_a, "accept": True}),
                       (STATUS, {"requestToken": "anything-at-all"})):
        response = client.post(path.format(code=code), json=body, headers=evil)
        assert response.status_code == 403, path
    assert client.post(f"/api/rooms/{code}/join", json={}, headers=evil).status_code == 403
    assert state(client, code, token_a)["mode"] == "pass_along", "nothing changed"
