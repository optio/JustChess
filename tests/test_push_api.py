"""U5 HTTP boundary: push routes, ``/sw.js`` and the alert dispatch after join, move and claims.

Every app runs on a temporary database with an injected clock, in-memory VAPID
keys (or none) and a fake push sender, so nothing reaches a push service.
Background tasks run inside the TestClient call; the "response first" test
drives the ASGI app directly and checks the response body was sent before the
slow fake send started.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import threading
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import stockfish_install
from justchess import notifications, vapid
from justchess.api import create_app
from justchess.live import LiveHub
from justchess.notifications import PushResult

START = 1_800_000_000.0


class FakeClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSender:
    """Records every send (payload and time); can be slow or broken."""

    def __init__(self, result: PushResult = PushResult(201), delay: float = 0.0, error: Exception | None = None) -> None:
        self.result, self.delay, self.error = result, delay, error
        self.sends: list[dict] = []
        self.started: list[float] = []
        self.done = threading.Event()

    def __call__(self, info, payload, config):
        self.started.append(time.monotonic())
        if self.delay:
            time.sleep(self.delay)
        self.sends.append({"endpoint": info["endpoint"], **json.loads(payload)})
        self.done.set()
        if self.error:
            raise self.error
        return self.result


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def subscription(n: int = 1) -> dict:
    point = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"endpoint": f"https://fcm.googleapis.com/fcm/send/api-test-{n}",
            "keys": {"p256dh": b64(point), "auth": b64(secrets.token_bytes(16))}}


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_client(tmp_path, monkeypatch, clock):
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    clients = []

    def factory(*, enabled: bool = True, sender: FakeSender | None = None, name: str = "push") -> TestClient:
        keys = vapid.config_for(ec.generate_private_key(ec.SECP256R1())) if enabled else vapid.disabled("off in tests")
        app = create_app(db_path=tmp_path / f"{name}.sqlite3", engine_dir=tmp_path / "engines", clock=clock,
                         receive_timeout=30.0, vapid=keys, push_sender=sender or FakeSender())
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


def two_seats(client) -> tuple[dict, dict]:
    a = client.post("/api/rooms").json()
    b = client.post(f"/api/rooms/{a['code']}/join", json={}).json()
    return a, b


def subscribe(client, code, token, n=1):
    return client.post(f"/api/rooms/{code}/push/subscribe", json={"token": token, **subscription(n)})


def alerts(client, code) -> list[tuple[str, str, str]]:
    with client.app.state.services.db.read() as conn:
        rows = conn.execute("SELECT slot, event_key, status FROM alert_records WHERE room_code = ? "
                            "ORDER BY rowid", (code,)).fetchall()
    return [(r["slot"], r["event_key"], r["status"]) for r in rows]


def wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


# --- routes -------------------------------------------------------------------

def test_key_route_when_enabled_and_disabled(make_client):
    on = make_client(name="on")
    off = make_client(enabled=False, name="off")

    key = on.get("/api/push/key")
    assert key.status_code == 200 and key.json()["enabled"] is True
    assert len(base64.urlsafe_b64decode(key.json()["publicKey"] + "=")) == 65
    assert key.json()["publicKey"] == on.app.state.services.vapid.public_key
    disabled = off.get("/api/push/key")
    assert (disabled.status_code, disabled.json()["enabled"]) == (404, False)
    assert "PRIVATE" not in key.text


def test_subscribe_as_seat_foreign_token_invalid_endpoint_and_disabled(make_client):
    client = make_client()
    a, _b = two_seats(client)
    code = a["code"]

    assert subscribe(client, code, a["token"]).json() == {"ok": True}
    assert subscribe(client, code, a["token"]).status_code == 200, "re-subscribing is an upsert"
    foreign = subscribe(client, code, "someone-elses-token", n=2)
    assert (foreign.status_code, foreign.json()["detail"]) == (403, "This isn't your seat")
    bad = client.post(f"/api/rooms/{code}/push/subscribe",
                      json={"token": a["token"], **subscription(), "endpoint": "https://169.254.169.254/latest"})
    assert (bad.status_code, bad.json()["detail"]) == (400, "Invalid push subscription")
    no_keys = client.post(f"/api/rooms/{code}/push/subscribe", json={"token": a["token"], "endpoint": subscription()["endpoint"]})
    assert no_keys.status_code == 400
    with client.app.state.services.db.read() as conn:
        assert [s.slot for s in notifications.list_subscriptions(conn, code, "A")] == ["A"]

    off = make_client(enabled=False, name="off")
    a2, _ = two_seats(off)
    assert subscribe(off, a2["code"], a2["token"]).status_code == 404


def test_unsubscribe_with_and_without_endpoint(make_client):
    client = make_client()
    a, b = two_seats(client)
    code = a["code"]
    subscribe(client, code, b["token"], n=7)
    url = f"/api/rooms/{code}/push/unsubscribe"

    missing = client.post(url, json={"token": b["token"]})
    assert missing.status_code == 400
    assert client.post(url, json={"token": "forged", "endpoint": subscription(7)["endpoint"]}).status_code == 403
    removed = client.post(url, json={"token": b["token"], "endpoint": subscription(7)["endpoint"]})
    assert removed.json() == {"ok": True, "removed": 1}
    assert client.post(url, json={"token": b["token"], "endpoint": subscription(7)["endpoint"]}).json()["removed"] == 0


def test_service_worker_route_headers(make_client):
    client = make_client()
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-type"].startswith("text/javascript")
    assert 'addEventListener("push"' in response.text and 'addEventListener("notificationclick"' in response.text


def test_foreign_origin_is_refused_on_push_routes(make_client):
    client = make_client()
    a, _b = two_seats(client)
    evil = {"Origin": "http://evil.example"}
    for path in ("subscribe", "unsubscribe"):
        response = client.post(f"/api/rooms/{a['code']}/push/{path}", headers=evil,
                               json={"token": a["token"], **subscription()})
        assert response.status_code == 403, path
    assert client.get("/api/push/key", headers=evil).status_code == 200  # reads are not guarded


# --- dispatch -------------------------------------------------------------------

def test_join_alerts_seat_a_and_a_move_dispatches_one_claim_for_the_opponent(make_client):
    sender = FakeSender()
    client = make_client(sender=sender)
    a = client.post("/api/rooms").json()
    code = a["code"]
    assert subscribe(client, code, a["token"], n=1).status_code == 200
    b = client.post(f"/api/rooms/{code}/join", json={}).json()
    assert subscribe(client, code, b["token"], n=2).status_code == 200

    moved = client.post(f"/api/rooms/{code}/moves", json={"token": a["token"], "uci": "e2e4", "version": 1})

    assert moved.status_code == 200
    assert alerts(client, code) == [("A", "joined", "sent"), ("B", "move:1:1", "sent")]
    assert [(s["endpoint"][-1], s["tag"], s["title"]) for s in sender.sends] == [
        ("1", f"{code}:joined", "Your opponent has joined"), ("2", f"{code}:move:1:1", "Your move")]
    assert sender.sends[1]["url"] == f"/r/{code}" and sender.sends[1]["body"] == "Your opponent played e4."
    # a stale resend of the same move is refused by U1 and makes no second claim
    again = client.post(f"/api/rooms/{code}/moves", json={"token": a["token"], "uci": "e2e4", "version": 1})
    assert again.status_code == 409 and len(sender.sends) == 2


def test_final_move_and_claim_win_alert_ended_only(make_client, clock):
    sender = FakeSender()
    client = make_client(sender=sender)
    a, b = two_seats(client)
    code = a["code"]
    version = 1
    for i, uci in enumerate(["f2f3", "e7e5", "g2g4", "d8h4"]):
        answer = client.post(f"/api/rooms/{code}/moves",
                             json={"token": (a, b)[i % 2]["token"], "uci": uci, "version": version}).json()
        version = answer["version"]
    keys = [key for _slot, key, _status in alerts(client, code)]
    assert keys == ["joined", "move:1:1", "move:1:2", "move:1:3", "ended:1"], "the mating move gives only ended:1"
    assert alerts(client, code)[-1][:2] == ("A", "ended:1")

    client.post(f"/api/rooms/{code}/rematch", json={"token": a["token"]})
    client.post(f"/api/rooms/{code}/rematch", json={"token": b["token"]})
    clock.advance(25 * 3600)
    won = client.post(f"/api/rooms/{code}/claim-win", json={"token": a["token"]})
    assert won.status_code == 200 and won.json()["endReason"] == "abandoned"
    assert alerts(client, code)[-1][:2] == ("B", "ended:2")


def hello(ws, token, visible=True):
    ws.send_json({"type": "hello", "token": token, "visible": visible})
    return ws.receive_json()


def test_presence_fresh_visible_skips_stale_or_hidden_sends(make_client, clock):
    sender = FakeSender()
    client = make_client(sender=sender)
    a, b = two_seats(client)
    code = a["code"]
    subscribe(client, code, b["token"])
    hub = client.app.state.services.hub

    with client.websocket_connect(f"/ws/{code}") as seat_b:
        hello(seat_b, b["token"], visible=True)
        client.post(f"/api/rooms/{code}/moves", json={"token": a["token"], "uci": "e2e4", "version": 1})
        client.post(f"/api/rooms/{code}/moves", json={"token": b["token"], "uci": "e7e5", "version": 2})
        clock.advance(7)  # B's page still says visible, but nothing was heard for 7 s
        client.post(f"/api/rooms/{code}/moves", json={"token": a["token"], "uci": "g1f3", "version": 3})
        client.post(f"/api/rooms/{code}/moves", json={"token": b["token"], "uci": "b8c6", "version": 4})
        seat_b.send_json({"type": "visibility", "visible": False})
        wait_for(lambda: not any(c.visible for c in hub.connections(code) if c.slot == "B"))
        client.post(f"/api/rooms/{code}/moves", json={"token": a["token"], "uci": "f1c4", "version": 5})

    by_key = {key: status for slot, key, status in alerts(client, code) if slot == "B"}
    assert by_key == {"move:1:1": "skipped", "move:1:3": "sent", "move:1:5": "sent"}
    assert [s["tag"] for s in sender.sends] == [f"{code}:move:1:3", f"{code}:move:1:5"]


def test_hub_freshness_rule():
    clock = FakeClock()
    hub = LiveHub(snapshot_source=lambda code: (lambda slot: {}), identify=lambda c, t: None,
                  mark_seen=lambda c, s: None, clock=clock)
    from justchess.live import Connection

    visible = Connection(ws=None, slot="B", token_hash="h", visible=True, last_heard=START)
    hidden = Connection(ws=None, slot="A", token_hash="h2", visible=False, last_heard=START)
    hub._register("ROOM01", visible)
    hub._register("ROOM01", hidden)

    assert hub.is_fresh_visible("ROOM01", "B", START + 6.0)
    assert not hub.is_fresh_visible("ROOM01", "B", START + 6.1)
    assert not hub.is_fresh_visible("ROOM01", "A", START), "a hidden page never counts"
    assert not hub.is_fresh_visible("OTHER1", "B", START)


def test_a_failing_send_never_fails_the_request(make_client, caplog):
    sender = FakeSender(error=RuntimeError("push transport exploded"))
    client = make_client(sender=sender)
    a, b = two_seats(client)
    subscribe(client, a["code"], b["token"])

    moved = client.post(f"/api/rooms/{a['code']}/moves", json={"token": a["token"], "uci": "e2e4", "version": 1})

    assert moved.status_code == 200 and moved.json()["version"] == 2
    assert any("could not be dispatched" in r.getMessage() for r in caplog.records)
    assert ("B", "move:1:1", "failed") in alerts(client, a["code"])
    with client.app.state.services.db.read() as conn:
        pending = conn.execute("SELECT status, attempts FROM notification_outbox WHERE event_key = 'move:1:1'").fetchone()
    assert tuple(pending) == ("pending", 1), "transport failure is durably retained for retry"


async def _call_asgi(app, path: str, body: dict, events: list) -> None:
    raw = json.dumps(body).encode()
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
             "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                         (b"content-length", str(len(raw)).encode())],
             "client": ("testclient", 50000), "server": ("testserver", 80)}
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.sleep(10)
        return {"type": "http.disconnect"}

    async def send(message):
        events.append((time.monotonic(), message["type"], message.get("status"), message.get("more_body", False)))

    await app(scope, receive, send)


def test_the_response_does_not_wait_for_a_slow_send(make_client):
    sender = FakeSender(delay=0.5)
    client = make_client(sender=sender)
    a, b = two_seats(client)
    subscribe(client, a["code"], b["token"])
    events: list = []

    client.portal.call(_call_asgi, client.app, f"/api/rooms/{a['code']}/moves",
                       {"token": a["token"], "uci": "e2e4", "version": 1}, events)

    start = next(e for e in events if e[1] == "http.response.start")
    body_done = next(e for e in events if e[1] == "http.response.body" and not e[3])
    assert start[2] == 200
    assert sender.done.is_set() and len(sender.started) == 1
    assert body_done[0] <= sender.started[0], "the whole response was sent before the push started"
    assert ("B", "move:1:1", "sent") in alerts(client, a["code"])
