"""Vercel coordination uses disposable databases and fake push/engine transports."""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess import games, notifications, outbox, rooms, vapid, work
from justchess.api import create_app
from justchess.db import prepare_database
from tests.test_postgres import pg_database  # noqa: F401
from tests.test_push_api import FakeClock, FakeSender, subscription
from tests.fakes.computer_api import computer_client, computer_clock, create_computer, plies  # noqa: F401


def clients(pg_database, tmp_path, monkeypatch):
    _, url = pg_database
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda *_: stockfish_install.EngineResult(error="disabled in tests"))
    return [TestClient(create_app(database_url=url, engine_dir=tmp_path / "engine")) for _ in range(2)]


def test_postgres_two_instances_serialize_same_version(pg_database, tmp_path, monkeypatch):
    with ExitStack() as stack:
        a, b = [stack.enter_context(c) for c in clients(pg_database, tmp_path, monkeypatch)]
        made = a.post("/api/rooms").json()
        code = made["code"]
        assert b.post(f"/api/rooms/{code}/join", json={}).status_code == 200
        def move(client, uci):
            return client.post(f"/api/rooms/{code}/moves", json={"token": made["token"], "uci": uci, "version": 1})
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            first = pool.submit(move, a, "e2e4")
            second = pool.submit(move, b, "d2d4")
            answers = [first.result(10), second.result(10)]
        assert sorted(r.status_code for r in answers) == [200, 409]
        assert next(r for r in answers if r.status_code == 409).json()["snapshot"]["version"] == 2
        db, _ = pg_database
        with db.read() as conn:
            game = games.current_game(conn, code)
            assert len(games.load_moves(conn, game.game_id)) == 1


def test_postgres_event_reaches_other_instance_and_presence_expires(pg_database, tmp_path, monkeypatch):
    with ExitStack() as stack:
        a, b = [stack.enter_context(c) for c in clients(pg_database, tmp_path, monkeypatch)]
        made = a.post("/api/rooms").json()
        code = made["code"]
        joined = a.post(f"/api/rooms/{code}/join", json={}).json()
        with b.websocket_connect(f"/ws/{code}") as ws:
            ws.send_json({"type": "hello", "token": joined["token"], "visible": True})
            assert ws.receive_json()["version"] == 1
            assert a.app.state.services.presence_of(code, "B").page_covers_it
            moved = a.post(f"/api/rooms/{code}/moves", json={"token": made["token"], "uci": "e2e4", "version": 1})
            assert moved.status_code == 200
            for _ in range(5):
                snapshot = ws.receive_json()
                if snapshot.get("version") == 2:
                    break
            assert snapshot["version"] == 2
        db, _ = pg_database
        with db.read() as conn:
            assert conn.execute("SELECT count(*) FROM live_presence").fetchone()[0] == 0
        # An abrupt instance loss leaves a bounded presence row, never permanent online state.
        svc = a.app.state.services
        svc.coordination.touch(code, "abandoned", "B", True, svc.clock() - 11)
        assert not svc.presence_of(code, "B").connected
        with b.websocket_connect(f"/ws/{code}") as ws:
            ws.send_json({"type": "hello"})
            assert ws.receive_json()["version"] == 2, "reconnect starts with authoritative state"


def seed(db, clock):
    with db.transaction() as conn:
        room, _, _ = rooms.create_room(conn, clock(), lambda: "OUT001")
        game = games.create_first_game(conn, room.code, clock())
        rooms.join_room(conn, room.code, None, clock())
        games.mark_playing(conn, game, clock())
        game = games.current_game(conn, room.code)
        game = games.apply_move(conn, game, "A", "e2e4", game.version, clock())
        event = notifications.event_after_move(room.code, "A", game, 1, "e4")
        for i in (1, 2):
            value = subscription(i)
            notifications.save_subscription(conn, room.code, "B", value["endpoint"],
                                            value["keys"]["p256dh"], value["keys"]["auth"], clock())
        outbox.enqueue(conn, event, clock())
    return event


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_outbox_retry_leases_freshness_and_partial_success(backend, request, tmp_path):
    from cryptography.hazmat.primitives.asymmetric import ec
    db = request.getfixturevalue("pg_database")[0] if backend == "postgres" else prepare_database(tmp_path / "queue.sqlite3")
    clock = FakeClock()
    event = seed(db, clock)
    attempts = []
    def sender(info, payload, keys):
        attempts.append(info["endpoint"])
        return notifications.PushResult(201 if len(attempts) == 1 else 503)
    keys = vapid.config_for(ec.generate_private_key(ec.SECP256R1()))
    queue = outbox.Outbox(db, keys, sender, clock, lambda *_: notifications.Presence(False, False))
    assert queue.drain() == 1
    assert len(attempts) == 2
    with db.read() as conn:
        row = conn.execute("SELECT status, attempts FROM notification_outbox").fetchone()
        assert tuple(row) == ("pending", 1)
    clock.advance(61)
    queue.sender = lambda info, *_: attempts.append(info["endpoint"]) or notifications.PushResult(201)
    assert queue.drain() == 1 and len(attempts) == 3, "acknowledged endpoint is never replayed"
    assert queue.drain() == 0
    with db.transaction() as conn:
        # Simulate an interrupted owner; an expired lease is retryable.
        conn.execute("UPDATE notification_outbox SET status = 'pending', lease_owner = 'dead', lease_until = ?",
                     (clock() + 60,))
    assert queue.drain() == 0
    clock.advance(400)
    assert queue.drain() == 1 and len(attempts) == 3, "stale turn alert is discarded after lease recovery"
    with db.read() as conn:
        assert conn.execute("SELECT status FROM notification_outbox").fetchone()[0] == "skipped"


def test_daily_cron_requires_secret_and_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("CRON_SECRET", "test-only-cron-secret")
    monkeypatch.setattr(stockfish_install, "ensure_stockfish", lambda *_: stockfish_install.EngineResult(error="off"))
    with TestClient(create_app(db_path=tmp_path / "cron.sqlite3", engine_dir=tmp_path / "engine")) as client:
        assert client.get("/api/cron/maintenance").status_code == 401
        assert client.get("/api/cron/maintenance", headers={"Authorization": "Bearer forged"}).status_code == 401
        assert client.get("/api/cron/maintenance", headers={"Authorization": "Bearer test-only-cron-secret"}).json() == {
            "processed": 0, "deleted": 0}


def test_serverless_computer_reply_finishes_in_request(computer_client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    client = computer_client([])
    made = create_computer(client, colour="white")
    answer = client.post(f"/api/rooms/{made['code']}/moves", json={"token": made["token"], "uci": "e2e4", "version": 0})
    assert answer.status_code == 200 and plies(answer.json()) == 2
    assert not client.app.state.services.coordinator.tasks
    repeated = client.post(f"/api/rooms/{made['code']}/computer-move", json={"token": made["token"]})
    assert plies(repeated.json()) == 2


def test_postgres_claims_and_limits_shared_between_instances(pg_database):
    from justchess.ratelimit import SharedRateLimiter
    db, _ = pg_database
    first = SharedRateLimiter(db, "test", 1)
    second = SharedRateLimiter(db, "test", 1)
    assert first.allow("same visitor", 10)
    assert not second.allow("same visitor", 11)
    assert second.allow("same visitor", 71)
    with db.transaction() as conn:
        owner = work.claim(conn, "engine:test", 10, 60)
    with db.transaction() as conn:
        assert work.claim(conn, "engine:test", 11, 60) is None
        assert work.claim(conn, "engine:test", 71, 60) != owner
        work.release(conn, "engine:test", owner)
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM work_claims").fetchone()[0] == 1


def test_postgres_engine_duplicate_requests_and_stale_completion(pg_database, computer_client, computer_clock, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    db, url = pg_database
    first = computer_client(["--delay", "0.3"], database_url=url)
    second = computer_client(["--delay", "0.3"], database_url=url)
    with db.transaction() as conn:
        room, _, token = rooms.create_computer_room(conn, computer_clock(), "beginner", "B", lambda: "ENG001")
        games.create_computer_game(conn, room.code, "B", computer_clock())
    path = f"/api/rooms/{room.code}/computer-move"
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        answers = list(pool.map(lambda client: client.post(path, json={"token": token}), (first, second)))
    assert all(answer.status_code == 200 for answer in answers)
    snapshot = second.get(f"/api/rooms/{room.code}").json()
    assert plies(snapshot) == 1, "two instance requests commit exactly one computer reply"
    with db.transaction() as conn:
        room2, _, token2 = rooms.create_computer_room(conn, computer_clock(), "beginner", "B", lambda: "ENG002")
        games.create_computer_game(conn, room2.code, "B", computer_clock())
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        running = pool.submit(first.post, f"/api/rooms/{room2.code}/computer-move", json={"token": token2})
        deadline = time.monotonic() + 5
        while first.app.state.services.coordinator.any_reply(room2.code) is None:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        resigned = second.post(f"/api/rooms/{room2.code}/resign", json={"token": token2, "version": 0})
        assert resigned.status_code == 200
        assert running.result(10).status_code == 200
    ended = first.get(f"/api/rooms/{room2.code}").json()
    assert ended["status"] == "finished" and plies(ended) == 0, "stale result cannot land after other instance resigns"


def test_postgres_engine_abandoned_claim_retries_after_expiry(pg_database, computer_client, computer_clock, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    db, url = pg_database
    client = computer_client([], database_url=url)
    with db.transaction() as conn:
        room, _, token = rooms.create_computer_room(conn, computer_clock(), "beginner", "B", lambda: "RETRY1")
        game = games.create_computer_game(conn, room.code, "B", computer_clock())
        assert work.claim(conn, f"engine:{room.code}:{game.game_id}:{game.version}", computer_clock(), 60)
    path = f"/api/rooms/{room.code}/computer-move"
    assert plies(client.post(path, json={"token": token}).json()) == 0
    computer_clock.advance(61)
    assert plies(client.post(path, json={"token": token}).json()) == 1


def test_postgres_concurrent_outbox_attempts_send_each_endpoint_once(pg_database):
    import threading
    from cryptography.hazmat.primitives.asymmetric import ec
    db, _ = pg_database
    clock = FakeClock()
    event = seed(db, clock)
    seen = []
    guard = threading.Lock()
    def sender(info, *_):
        with guard:
            seen.append(info["endpoint"])
        time.sleep(0.05)
        return notifications.PushResult(201)
    keys = vapid.config_for(ec.generate_private_key(ec.SECP256R1()))
    queues = [outbox.Outbox(db, keys, sender, clock, lambda *_: notifications.Presence(False, False)) for _ in range(2)]
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda queue: queue.dispatch(event), queues))
    assert len(seen) == len(set(seen)) == 2


def test_outbox_coalesces_obsolete_turn_and_rechecks_game(tmp_path):
    from cryptography.hazmat.primitives.asymmetric import ec
    db, clock = prepare_database(tmp_path / "coalesce.sqlite3"), FakeClock()
    event = seed(db, clock)
    with db.transaction() as conn:
        game = games.current_game(conn, event.room_code)
        game = games.apply_move(conn, game, "B", "e7e5", game.version, clock())
        game = games.apply_move(conn, game, "A", "g1f3", game.version, clock())
        newest = notifications.event_after_move(event.room_code, "A", game, 3, "Nf3")
        outbox.enqueue(conn, newest, clock())
    sender = FakeSender()
    queue = outbox.Outbox(db, vapid.config_for(ec.generate_private_key(ec.SECP256R1())), sender, clock,
                          lambda *_: notifications.Presence(False, False))
    assert queue.drain() == 1
    assert {item["key"] for item in sender.sends} == {"move:1:3"}
    with db.read() as conn:
        assert conn.execute("SELECT status FROM notification_outbox WHERE event_key = ?", (event.event_key,)).fetchone()[0] == "skipped"


def test_postgres_decline_cooldown_shared_across_instances(pg_database, tmp_path, monkeypatch):
    with ExitStack() as stack:
        a, b = [stack.enter_context(c) for c in clients(pg_database, tmp_path, monkeypatch)]
        made = a.post("/api/rooms").json()
        code = made["code"]
        assert a.post(f"/api/rooms/{code}/mode", json={"token": made["token"], "mode": "pass_along"}).status_code == 200
        assert a.post(f"/api/rooms/{code}/join", json={}).status_code == 202
        assert b.post(f"/api/rooms/{code}/join-request/answer", json={"token": made["token"], "accept": False}).status_code == 200
        answer = a.post(f"/api/rooms/{code}/join", json={})
        assert answer.status_code == 409 and answer.json()["error"] == "declined_recently"


def test_vercel_entrypoint_uses_temporary_engine_and_never_loads_env(monkeypatch):
    import runpy
    import tempfile
    from pathlib import Path
    from justchess import envfile
    from justchess.db import DatabaseStartupError
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(envfile, "load", lambda: pytest.fail("Vercel must not read local env"))
    entry = runpy.run_path(str(Path(__file__).resolve().parents[1] / "app.py"))
    assert Path(tempfile.gettempdir()) in entry["ENGINE_DIR"].parents
    with pytest.raises(DatabaseStartupError, match="requires DATABASE_URL"):
        entry["configured_database_url"]()


def test_serverless_failed_reply_preserves_durable_backoff(computer_client, computer_clock, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    client = computer_client(["--illegal"])
    made = create_computer(client, colour="white")
    response = client.post(f"/api/rooms/{made['code']}/moves",
                           json={"token": made["token"], "uci": "e2e4", "version": 0})
    assert response.status_code == 200 and plies(response.json()) == 1
    svc = client.app.state.services
    with svc.db.read() as conn:
        row = conn.execute("SELECT owner, expires_at FROM work_claims").fetchone()
        assert row["expires_at"] == computer_clock() + svc.gameplay.retry_backoff
        owner = row["owner"]
    client.post(f"/api/rooms/{made['code']}/computer-move", json={"token": made["token"]})
    with svc.db.read() as conn:
        assert conn.execute("SELECT owner FROM work_claims").fetchone()[0] == owner
