"""HTTP integration tests for justchess.api through FastAPI's TestClient (temporary database)."""

from __future__ import annotations

import logging
import threading

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import create_room, join_room, move
from justchess import housekeeping
from justchess.rooms import ABANDON_AFTER

FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]
DAY = 24 * 3600.0


def play_fools_mate(client, code, white, black):
    version = 1
    body = None
    for i, uci in enumerate(FOOLS_MATE):
        response = move(client, code, white if i % 2 == 0 else black, uci, version)
        assert response.status_code == 200, response.text
        body = response.json()
        version = body["version"]
    return body


def run_together(*calls):
    """Start each call in its own thread at the same moment; return their responses."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(index, call):
        barrier.wait()
        results[index] = call()

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    return results


def test_create_join_move_end_and_score(make_client):
    client = make_client()
    created = client.post("/api/rooms")
    assert created.status_code == 201
    a = created.json()
    assert (a["slot"], a["colour"], created.headers["location"]) == ("A", "white", f"/r/{a['code']}")
    b = join_room(client, a["code"].lower())  # codes match case-insensitively
    assert (b["slot"], b["colour"]) == ("B", "black")

    assert client.post(f"/api/rooms/{a['code']}/join", json={}).json()["detail"] == "This game already has two players"
    assert client.post("/api/rooms/BAD!/join").status_code == 400
    assert client.post("/api/rooms/NOPE00/join").status_code == 404
    assert move(client, a["code"], b["token"], "e7e5", 1).json()["detail"] == "Not your turn"
    assert move(client, a["code"], "not-a-seat", "e2e4", 1).status_code == 403
    assert move(client, a["code"], a["token"], "e2e5", 1).json()["detail"] == "Illegal move"

    final = play_fools_mate(client, a["code"], a["token"], b["token"])

    assert (final["status"], final["endReason"], final["result"]) == ("finished", "checkmate", "0-1")
    assert final["score"] == {"A": 0, "B": 1, "draws": 0}
    assert final["claimableDrawReason"] is None and "white_score" not in final
    after = move(client, a["code"], a["token"], "a2a3", final["version"])
    assert after.status_code == 409 and after.json()["detail"] == "Game is over"
    assert after.json()["snapshot"]["version"] == final["version"]
    assert client.get("/r/" + a["code"]).status_code == 200


def test_state_read_uses_header_token_only(make_client, caplog):
    client = make_client()
    caplog.set_level(logging.DEBUG)
    a = create_room(client)
    join_room(client, a["code"])
    url = f"/api/rooms/{a['code']}"

    seat = client.get(url, headers={"X-Seat-Token": a["token"]}).json()
    by_query = client.get(url, params={"token": a["token"]}).json()
    anonymous = client.get(url).json()
    wrong = client.get(url, headers={"X-Seat-Token": "forged"}).json()

    assert (seat["slot"], seat["colour"]) == ("A", "white") and seat["legalMoves"]
    for watcher in (by_query, anonymous, wrong):
        assert (watcher["slot"], watcher["colour"], watcher["legalMoves"]) == (None, None, [])
    assert client.get("/api/rooms/NOPE00").status_code == 404
    assert client.get("/api/rooms/x").status_code == 400
    app_logs = [r.getMessage() for r in caplog.records if r.name.startswith("justchess")]
    assert app_logs and not any(a["token"] in line for line in app_logs)


def test_foreign_origin_refused_on_post_and_socket(make_client):
    client = make_client()
    evil = {"Origin": "http://evil.example"}

    assert client.post("/api/rooms", headers=evil).status_code == 403
    assert client.post("/api/rooms", headers={"Origin": "http://testserver"}).status_code == 201
    forwarded = {"Origin": "https://testserver", "X-Forwarded-Proto": "https"}
    assert client.post("/api/rooms", headers=forwarded).status_code == 201
    code = create_room(client)["code"]
    assert client.get(f"/api/rooms/{code}", headers=evil).status_code == 200  # reads are not guarded

    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"/ws/{code}", headers=evil):
            pass
    assert refused.value.code == 1008

    configured = make_client(origin="https://chess.example")
    assert configured.post("/api/rooms", headers={"Origin": "http://testserver"}).status_code == 403
    assert configured.post("/api/rooms", headers={"Origin": "https://chess.example"}).status_code == 201


def test_body_over_4kb_returns_413(make_client):
    client = make_client()
    code = create_room(client)["code"]
    padding = "x" * 5000

    declared = client.post(f"/api/rooms/{code}/join", json={"token": padding})
    chunked = client.post(f"/api/rooms/{code}/join", content=(c for c in [b'{"token": "', padding.encode(), b'"}']),
                          headers={"Content-Type": "application/json"})
    small = client.post(f"/api/rooms/{code}/join", json={"token": None})

    assert declared.status_code == 413
    assert chunked.status_code == 413
    assert small.status_code == 200


def test_concurrent_moves_give_one_success_and_one_conflict(make_client):
    client = make_client()
    a = create_room(client)
    join_room(client, a["code"])

    results = run_together(lambda: move(client, a["code"], a["token"], "e2e4", 1),
                           lambda: move(client, a["code"], a["token"], "d2d4", 1))

    assert sorted(r.status_code for r in results) == [200, 409]
    conflict = next(r for r in results if r.status_code == 409).json()
    assert conflict["snapshot"]["version"] == 2 and len(conflict["snapshot"]["moveList"]) == 1


def test_concurrent_rematch_requests_create_exactly_one_game(make_client):
    client = make_client()
    a = create_room(client)
    b = join_room(client, a["code"])
    finished = play_fools_mate(client, a["code"], a["token"], b["token"])
    url = f"/api/rooms/{a['code']}/rematch"

    repeat = run_together(lambda: client.post(url, json={"token": a["token"]}),
                          lambda: client.post(url, json={"token": a["token"]}))
    assert [r.status_code for r in repeat] == [200, 200]
    pending = client.get(f"/api/rooms/{a['code']}").json()
    assert pending["rematch"] == {"state": "pending", "requestedBy": "A"}
    assert pending["version"] == finished["version"] + 1  # the repeat changed nothing

    both = run_together(lambda: client.post(url, json={"token": b["token"]}),
                        lambda: client.post(url, json={"token": a["token"]}))
    assert all(r.status_code in (200, 409) for r in both)
    state = client.get(f"/api/rooms/{a['code']}", headers={"X-Seat-Token": a["token"]}).json()
    assert (state["game"], state["status"], state["colour"], state["version"]) == (2, "playing", "black", 0)
    assert state["rematch"]["state"] == "none" and state["score"] == {"A": 0, "B": 1, "draws": 0}
    with client.app.state.services.db.read() as conn:
        assert conn.execute("SELECT count(*) FROM games WHERE room_code = ?", (a["code"],)).fetchone()[0] == 2


def test_claim_win_refused_before_24h_and_accepted_after(make_client, clock):
    client = make_client()
    a = create_room(client)
    join_room(client, a["code"])
    url = f"/api/rooms/{a['code']}/claim-win"

    clock.advance(3600)
    early = client.post(url, json={"token": a["token"]})
    assert (early.status_code, early.json()["detail"]) == (409, "Your opponent hasn't been away long enough")
    assert early.json()["snapshot"]["seats"]["B"]["presence"] == "away"

    clock.advance(ABANDON_AFTER)
    won = client.post(url, json={"token": a["token"]})
    assert won.status_code == 200, won.text
    body = won.json()
    assert (body["endReason"], body["result"], body["score"]["A"]) == ("abandoned", "1-0", 1)
    assert body["seats"]["B"]["presence"] == "abandoned"


def test_housekeeping_deletes_idle_room_and_retries_after_failure(make_client, clock, caplog):
    client = make_client()
    old = create_room(client)
    join_room(client, old["code"])
    assert move(client, old["code"], old["token"], "e2e4", 1).status_code == 200
    clock.advance(31 * DAY)
    recent = create_room(client)
    db = client.app.state.services.db

    def failing_hook(conn, code):
        raise RuntimeError("push store unavailable")

    with caplog.at_level(logging.ERROR, logger="justchess.housekeeping"):
        assert housekeeping.run_cleanup(db, clock(), hooks=[failing_hook]) == 0
    assert old["code"] in caplog.text
    assert client.get(f"/api/rooms/{old['code']}").status_code == 200  # rolled back, kept for next run

    seen = []
    assert housekeeping.run_cleanup(db, clock(), hooks=[lambda conn, code: seen.append(code)]) == 1
    assert seen == [old["code"]]
    assert client.get(f"/api/rooms/{old['code']}").status_code == 404
    assert client.get(f"/api/rooms/{recent['code']}").status_code == 200
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM moves").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM seats").fetchone()[0] == 1
