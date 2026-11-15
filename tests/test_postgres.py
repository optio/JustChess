"""Optional PostgreSQL persistence and configuration regressions; no real app data."""

from __future__ import annotations

import os
import sqlite3
import sys
import traceback
import uuid
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import pytest

from justchess import db as database, postgres
from justchess import DomainError, games, housekeeping, notifications, rooms, summaries


@pytest.mark.parametrize("value", [None, ""])
def test_no_database_url_keeps_sqlite(tmp_path, value):
    path = tmp_path / "local.sqlite3"
    env = {"JUSTCHESS_DB": str(path)}
    if value is not None:
        env["DATABASE_URL"] = value
    db = database.prepare_configured_database(env=env)
    assert db.backend == "sqlite" and db.path == path
    assert database.resolve_db_path({}).name == "justchess.sqlite3"


def test_url_wins_but_explicit_path_isolates_callers(tmp_path, monkeypatch):
    url = "postgresql://unused.invalid/test"
    marker = object()
    monkeypatch.setattr(database, "_prepare_postgres", lambda selected: marker if selected == url else None)
    path = tmp_path / "unused.sqlite3"
    assert database.prepare_configured_database(env={"DATABASE_URL": url, "JUSTCHESS_DB": str(path)}) is marker
    assert not path.exists()
    db = database.prepare_configured_database(path, env={"DATABASE_URL": url})
    assert db.backend == "sqlite"


@pytest.mark.parametrize("url", ["mysql://user:sentinel@host/db", " ", "postgresql://host/db ", "sentinel"])
def test_invalid_url_stops_without_fallback_or_leak(tmp_path, url, caplog):
    path = tmp_path / "unused.sqlite3"
    with pytest.raises(database.DatabaseStartupError) as caught:
        database.prepare_configured_database(env={"DATABASE_URL": url, "JUSTCHESS_DB": str(path)})
    assert "sentinel" not in str(caught.value) + caplog.text
    assert not path.exists()


def test_driver_failure_is_safe_and_does_not_touch_sqlite(tmp_path, monkeypatch):
    import psycopg

    path = tmp_path / "retained.sqlite3"
    database.prepare_database(path)
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise psycopg.OperationalError("password sentinel: postgresql://user:sentinel@host/db")

    monkeypatch.setattr(psycopg, "connect", fail)
    settings = {"DATABASE_URL": "postgresql://user:sentinel@host/db", "JUSTCHESS_DB": str(path)}
    with pytest.raises(database.DatabaseStartupError) as caught:
        database.prepare_configured_database(env=settings)
    assert "sentinel" not in "".join(traceback.format_exception(caught.value))
    assert path.read_bytes() == before


def test_sql_parameters_and_rows_preserve_domain_access():
    assert postgres.parameters("SELECT '?' AS mark, ? AS value, 'it''s ?' AS text") == \
        "SELECT '?' AS mark, %s AS value, 'it''s ?' AS text"
    row = postgres.Row(["id", "name"], [12, "room"])
    assert row[0] == row["id"] == 12 and tuple(row) == (12, "room")
    assert dict(row) == {"id": 12, "name": "room"}


def test_missing_driver_fails_safely(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(database.DatabaseStartupError, match="driver unavailable"):
        database.prepare_configured_database(database_url="postgresql://unused.invalid/test")


def test_test_environment_blocks_envfile_production_url(tmp_path):
    from justchess import envfile

    source = tmp_path / ".env"
    source.write_text("DATABASE_URL=postgresql://production.invalid/do-not-open\n", encoding="utf-8")
    assert os.environ["DATABASE_URL"] == ""
    envfile.load(source)
    assert os.environ["DATABASE_URL"] == ""


def test_query_failure_suppresses_driver_diagnostics():
    import psycopg

    class Broken:
        def execute(self, *_args):
            raise psycopg.IntegrityError("secret capability value")

    conn = postgres.Connection(Broken(), psycopg)
    with pytest.raises(sqlite3.IntegrityError) as caught:
        conn.execute("INSERT INTO rooms VALUES (?)", ("sensitive",))
    assert str(caught.value) == "PostgreSQL constraint violation"
    assert caught.value.__suppress_context__


@pytest.fixture
def pg_database():
    """One disposable schema per test, selected exclusively by a dedicated URL."""
    url = os.environ.get("JUSTCHESS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("JUSTCHESS_TEST_DATABASE_URL is absent; real PostgreSQL verification not run")
    import psycopg
    from psycopg import sql

    schema = "justchess_test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} ").format(sql.Identifier(schema)))
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["options"] = f"-c search_path={schema}"
    scoped_url = urlunsplit(parts._replace(query=urlencode(query, quote_via=quote)))
    db = database.prepare_configured_database(database_url=scoped_url)
    try:
        yield db, scoped_url
    finally:
        db.close()
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_schema_is_idempotent_and_rejects_versions(pg_database):
    db, url = pg_database
    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('KEEP01', 1, 1)")
    again = database._prepare_postgres(url)
    with again.read() as conn:
        assert conn.execute("SELECT code FROM rooms").fetchone()[0] == "KEEP01"
    for version in (3, database.SCHEMA_VERSION + 1):
        with db.transaction() as conn:
            conn.execute("UPDATE schema_version SET version = ?", (version,))
        with pytest.raises(database.DatabaseStartupError, match="Unsupported"):
            database._prepare_postgres(url)
        with db.read() as conn:
            assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == version
            assert conn.execute("SELECT code FROM rooms").fetchone()[0] == "KEEP01"


def test_postgres_rollback_constraints_and_recovery(pg_database):
    db, _ = pg_database
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('ROLL01', 1, 1)")
            conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('ROLL01', 2, 2)")
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0
    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('KEEP01', ?, ?)",
                     (1800000000.125, 1800000000.125))
    with db.read() as conn:
        assert conn.execute("SELECT created_at FROM rooms").fetchone()[0] == 1800000000.125


def test_postgres_unversioned_schema_is_refused_unchanged(pg_database):
    db, url = pg_database
    with db.transaction() as conn:
        conn.execute("DROP TABLE schema_version")
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('KEEP01', 1, 1)")
    with pytest.raises(database.DatabaseStartupError, match="unversioned"):
        database._prepare_postgres(url)
    with db.read() as conn:
        assert conn.execute("SELECT code FROM rooms").fetchone()[0] == "KEEP01"


def test_postgres_computer_captures_and_pending_request_constraints(pg_database):
    db, _ = pg_database
    with db.transaction() as conn:
        room, _, _ = rooms.create_computer_room(conn, 1, "club", "A", lambda: "CMP001")
        game = games.create_computer_game(conn, room.code, "A", 1)
        assert rooms.get_seats(conn, room.code)["B"].is_computer
        for slot, uci in (("A", "e2e4"), ("B", "d7d5"), ("A", "e4d5")):
            game = games.apply_move(conn, game, slot, uci, game.version, 2, computer=True)
        move = games.load_moves(conn, game.game_id)[-1]
        assert (move.captured_piece, move.captured_square) == ("p", "d5")
        conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, created_at, expires_at) "
                     "VALUES (?, 'first', 1, 100)", (room.code,))
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, created_at, expires_at) "
                         "VALUES (?, 'second', 1, 100)", (room.code,))
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece, captured_square) "
                         "VALUES (?, 4, 'e7e5', 'e5', 3, 'p', 'i9')", (game.game_id,))


def _domain_scenario(db):
    now = 1800000000.125
    with db.transaction() as conn:
        room, seat, token = rooms.create_room(conn, now, lambda: "PAR001")
        game = games.create_first_game(conn, room.code, now)
        request = rooms.create_join_request(conn, room.code, None, now)
        assert request.request.request_id > 0 and seat.seat_id > 0
        # Lapse before joining; no request state is silently dropped.
        assert rooms.lapse_expired(conn, now + 10000) == 1
        joined = rooms.join_room(conn, room.code, None, now + 1)
        games.mark_playing(conn, game, now + 1)
        game = games.current_game(conn, room.code)
        moved = games.apply_move(conn, game, "A", "e2e4", game.version, now + 2)
        assert games.load_moves(conn, game.game_id)[0].uci == "e2e4"
        with pytest.raises(DomainError) as stale:
            games.apply_move(conn, moved, "B", "e7e5", game.version, now + 3)
        assert stale.value.status == 409
        notifications.save_subscription(conn, room.code, "A", "https://fcm.googleapis.com/test", "key", "auth", now)
        notifications.save_subscription(conn, room.code, "A", "https://fcm.googleapis.com/test", "new", "auth", now + 1)
        assert len(notifications.list_subscriptions(conn, room.code, "A")) == 1
        event = notifications.joined_event(room.code)
        assert notifications.claim(conn, event, now)
        assert not notifications.claim(conn, event, now)
        notifications.mark(conn, event, "sent", now)
        assert notifications.alert_status(conn, room.code, "A", event.event_key) == "sent"
    [summary] = summaries.build_summaries(db, [(room.code, token)], now + 3)
    assert summary["found"] and summary["status"] == "playing" and not summary["yourTurn"]
    assert housekeeping.run_cleanup(db, now + 10000000, hooks=(notifications.delete_room_data,), retention=1) == 1
    with db.read() as conn:
        assert not rooms.room_exists(conn, room.code)
    return summary


def test_postgres_domain_matches_sqlite(pg_database, tmp_path):
    pg, _ = pg_database
    sqlite = database.prepare_database(tmp_path / "parity.sqlite3")
    assert _domain_scenario(pg) == _domain_scenario(sqlite)


def test_postgres_identity_recovery_and_profile_parity(pg_database):
    from justchess import players
    db, _ = pg_database
    with db.transaction() as conn:
        first = players.create(conn, 1)
        room, _, token = rooms.create_room(conn, 1, lambda: "IDP001")
        games.create_first_game(conn, room.code, 1)
        players.attach(conn, first["token"], room.code, token)
        second = players.restore(conn, first["recovery"], 2)
        assert second["seats"][0]["code"] == room.code
        assert rooms.authorize_seat(conn, room.code, second["token"]).slot == "A"
        recovery = players.regenerate(conn, first["token"])
        with pytest.raises(DomainError):
            players.restore(conn, first["recovery"], 3)
        assert players.restore(conn, recovery, 3)["playerId"] == first["playerId"]
    assert summaries.build_summaries(db, [(room.code, second["token"])], 4)[0]["found"]


def test_explicit_app_path_ignores_ambient_url(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from justchess.api import create_app
    import stockfish_install

    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid.invalid/never")
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda *_args: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(db_path=tmp_path / "api.sqlite3", engine_dir=tmp_path / "engine")) as client:
        assert client.post("/api/rooms").status_code == 201
        assert client.app.state.services.db.backend == "sqlite"


def test_app_uses_configured_postgres_without_sqlite_fallback(pg_database, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from justchess.api import create_app
    import stockfish_install

    _, url = pg_database
    unused = tmp_path / "unused.sqlite3"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JUSTCHESS_DB", str(unused))
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda *_args: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(engine_dir=tmp_path / "engine")) as client:
        room = client.post("/api/rooms").json()
        assert client.app.state.services.db.backend == "postgresql"
        assert client.post(f"/api/rooms/{room['code']}/join", json={}).status_code == 200
        response = client.post(f"/api/rooms/{room['code']}/moves",
                               json={"token": room["token"], "uci": "e2e4", "version": 1})
        assert response.status_code == 200
    assert not unused.exists()


def _stand_in_scenario(db):
    """The computer stand-in on either backend: enter, take over, leave, clean up."""
    now = 1800000100.0
    with db.transaction() as conn:
        room, seat, _token = rooms.create_room(conn, now, lambda: "STD001")
        games.create_first_game(conn, room.code, now)
        rooms.set_mode(conn, room.code, seat, rooms.MODE_COMPUTER, now, level="club")
        assert rooms.is_stand_in(conn, room.code)
        game = games.current_game(conn, room.code)
        games.apply_move(conn, game, "A", "e2e4", game.version, now + 1, computer=True)
        joined = rooms.join_room(conn, room.code, None, now + 2)
        took_over = (joined.created, joined.seat.slot, rooms.get_room(conn, room.code).mode, rooms.is_stand_in(conn, room.code))
        other, seat_b, _ = rooms.create_room(conn, now, lambda: "STD002")
        games.create_first_game(conn, other.code, now)
        rooms.set_mode(conn, other.code, seat_b, rooms.MODE_COMPUTER, now)
        rooms.set_mode(conn, other.code, seat_b, rooms.MODE_WAITING, now + 1)
        left = (rooms.get_room(conn, other.code).mode, "B" in rooms.get_seats(conn, other.code), rooms.is_stand_in(conn, other.code))
        rooms.set_mode(conn, other.code, seat_b, rooms.MODE_COMPUTER, now + 2)
    assert housekeeping.run_cleanup(db, now + 10000000, hooks=(notifications.delete_room_data,), retention=1) == 2
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM room_stand_ins").fetchone()[0] == 0
    return took_over, left


def test_postgres_stand_in_matches_sqlite(pg_database, tmp_path):
    pg, _ = pg_database
    sqlite = database.prepare_database(tmp_path / "stand-in.sqlite3")
    assert _stand_in_scenario(pg) == _stand_in_scenario(sqlite) == ((True, "B", "online", False), ("waiting", False, False))


def test_postgres_connections_are_reused_only_when_healthy_idle_and_recent(pg_database, monkeypatch):
    """Reusing connections keeps Vercel requests from paying a TLS handshake and login per database step."""
    db, _ = pg_database
    with db.read() as first:
        assert first.execute("SELECT 1").fetchone()[0] == 1
    with db.read() as again:
        assert again is first, "an idle healthy connection is reused"
    with pytest.raises(RuntimeError):
        with db.transaction() as inside:
            inside.execute("SELECT 1")
            raise RuntimeError("refused inside the transaction")
    with db.transaction() as after_rollback:
        assert after_rollback is first, "a rolled-back transaction leaves the connection idle and reusable"
    with db.read() as reading:
        reading.execute("BEGIN")  # a read that leaves its transaction open is not handed out again
    with db.read() as fresh:
        assert fresh is not reading
    first.close()
    with db.read() as replacement:
        assert replacement is not first and replacement.execute("SELECT 1").fetchone()[0] == 1
    monkeypatch.setattr(database, "POOL_MAX_IDLE_SECONDS", -1.0)
    with db.read() as stale_check:
        pass
    with db.read() as newer:
        assert newer is not stale_check, "connections idle for too long are closed, not reused"
    assert db.schema_name(newer) == db.schema_name(newer) and db._schema.startswith("justchess_test_")
    db.close()
    assert db._idle == []
