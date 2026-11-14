"""WebSocket integration tests for justchess.live through FastAPI's TestClient."""

from __future__ import annotations

import json
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import create_room, join_room, move


def hello(ws, token=None, visible=True):
    ws.send_json({"type": "hello", "token": token, "visible": visible})
    return ws.receive_json()


def receive_until(ws, predicate, limit=10):
    """Read messages until one matches; fail instead of hanging past ``limit`` messages."""
    for _ in range(limit):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("expected message not received")


def test_hello_gets_snapshot_and_bad_handshakes_are_refused(make_client):
    client = make_client()
    a = create_room(client)

    with client.websocket_connect(f"/ws/{a['code'].lower()}") as ws:
        state = hello(ws, a["token"])
        assert (state["type"], state["code"], state["slot"]) == ("state", a["code"], "A")
        assert state["seats"]["A"]["presence"] == "connected"
        assert state["status"] == "waiting"

    with client.websocket_connect(f"/ws/{a['code']}") as ws:
        ws.send_json({"type": "ping"})  # not a hello
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008

    with pytest.raises(WebSocketDisconnect) as unknown:
        with client.websocket_connect("/ws/NOPE00"):
            pass
    assert unknown.value.code == 1008


def test_seat_and_watcher_get_different_snapshots(make_client):
    client = make_client()
    a = create_room(client)
    b = join_room(client, a["code"])

    with client.websocket_connect(f"/ws/{a['code']}") as seat_a, \
            client.websocket_connect(f"/ws/{a['code']}") as watcher:
        hello(seat_a, a["token"])
        first = hello(watcher, "forged-token")  # an invalid token means watcher, not an error
        assert (first["slot"], first["colour"], first["legalMoves"]) == (None, None, [])

        assert move(client, a["code"], a["token"], "e2e4", 1).status_code == 200
        mine = receive_until(seat_a, lambda m: m.get("version") == 2)
        theirs = receive_until(watcher, lambda m: m.get("version") == 2)

    assert (mine["slot"], mine["colour"]) == ("A", "white")
    assert (theirs["slot"], theirs["colour"]) == (None, None)
    assert mine["moveList"] == theirs["moveList"] == [{"number": 1, "white": "e4", "black": None}]
    assert theirs["seats"]["A"]["presence"] == "connected"
    assert b["slot"] == "B"


def test_legal_moves_only_for_the_side_to_move(make_client):
    client = make_client()
    a = create_room(client)
    b = join_room(client, a["code"])

    with client.websocket_connect(f"/ws/{a['code']}") as seat_a, \
            client.websocket_connect(f"/ws/{a['code']}") as seat_b:
        hello(seat_a, a["token"])
        before_b = hello(seat_b, b["token"])
        before_a = receive_until(seat_a, lambda m: m["seats"]["B"]["presence"] == "connected")
        assert "e2e4" in before_a["legalMoves"] and before_b["legalMoves"] == []

        assert move(client, a["code"], a["token"], "e2e4", 1).status_code == 200
        after_a = receive_until(seat_a, lambda m: m.get("version") == 2)
        after_b = receive_until(seat_b, lambda m: m.get("version") == 2)

    assert after_a["legalMoves"] == [] and "legal" not in after_a
    assert "e7e5" in after_b["legalMoves"] and after_b["turn"] == "black"


def test_presence_becomes_away_after_receive_timeout(make_client):
    client = make_client(receive_timeout=0.3)
    a = create_room(client)
    join_room(client, a["code"])

    with client.websocket_connect(f"/ws/{a['code']}") as ws:
        assert hello(ws, a["token"])["seats"]["A"]["presence"] == "connected"
        time.sleep(0.6)  # no ping
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4408

    state = client.get(f"/api/rooms/{a['code']}").json()
    assert state["seats"]["A"]["presence"] == "away"


def test_continue_redeem_tells_old_socket_seat_moved(make_client):
    client = make_client()
    a = create_room(client)

    with client.websocket_connect(f"/ws/{a['code']}") as old_device:
        hello(old_device, a["token"])
        link = client.post(f"/api/rooms/{a['code']}/continue-link", json={"token": a["token"]})
        assert link.status_code == 200 and link.json()["expiresIn"] == 600
        redeemed = client.post(f"/api/rooms/{a['code']}/continue",
                               json={"continueToken": link.json()["continueToken"]})
        assert redeemed.status_code == 200, redeemed.text

        assert old_device.receive_json() == {"type": "seat-moved"}
        now_watching = old_device.receive_json()
        assert (now_watching["type"], now_watching["slot"]) == ("state", None)
        assert now_watching["seats"]["A"]["presence"] == "away"

    new = redeemed.json()
    assert (new["slot"], new["colour"]) == ("A", "white") and new["token"] != a["token"]
    url = f"/api/rooms/{a['code']}"
    assert client.get(url, headers={"X-Seat-Token": new["token"]}).json()["slot"] == "A"
    assert client.get(url, headers={"X-Seat-Token": a["token"]}).json()["slot"] is None
    assert client.post(f"/api/rooms/{a['code']}/continue-link", json={"token": a["token"]}).status_code == 403


def test_oversized_or_malformed_message_closes_socket(make_client):
    client = make_client()
    a = create_room(client)

    with client.websocket_connect(f"/ws/{a['code']}") as ws:
        hello(ws, a["token"])
        ws.send_text(json.dumps({"type": "ping", "pad": "x" * 2000}))
        with pytest.raises(WebSocketDisconnect) as too_big:
            ws.receive_json()
        assert too_big.value.code == 1009

    with client.websocket_connect(f"/ws/{a['code']}") as ws:
        hello(ws)
        ws.send_text("{not json")
        with pytest.raises(WebSocketDisconnect) as malformed:
            ws.receive_json()
        assert malformed.value.code == 1003
