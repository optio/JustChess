"""Tests for justchess.db: schema version 4, the BR1.1 startup check and transactions.

P2 U2 (ADR-010, NFR7): a fresh file is created at version 4 with every table;
a version-4 file is kept as it is; version-2 and version-3 files, unmarked
files and non-SQLite files are moved to ``.old`` (replacing an earlier one)
and a fresh database is created; a version-5 file refuses to start and is not
moved; a failed rename stops start-up. The new CHECK constraints and the
one-pending-join-request index hold. Every database here lives in tmp_path.
"""

from __future__ import annotations

import logging
import sqlite3

import pytest

from justchess import db as db_module
from justchess.db import (
    SCHEMA_VERSION,
    DatabaseStartupError,
    prepare_database,
    read_schema_version,
    resolve_db_path,
)

V4_TABLES = {"schema_version", "rooms", "seats", "games", "moves", "join_requests",
             "push_subscriptions", "alert_records"}


def table_names(db) -> set[str]:
    with db.read() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row["name"] for row in rows}


def make_versioned_file(path, version: int) -> None:
    """Write a small SQLite file that only carries a schema version row (and one marker row)."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_version VALUES (?)", (version,))
    conn.execute("CREATE TABLE marker (note TEXT)")
    conn.execute("INSERT INTO marker VALUES (?)", (f"version {version} data",))
    conn.commit()
    conn.close()


def test_fresh_database_gets_schema_version_4(tmp_path, caplog):
    path = tmp_path / "fresh.sqlite3"

    with caplog.at_level(logging.INFO, logger="justchess.db"):
        db = prepare_database(path)

    assert read_schema_version(path) == SCHEMA_VERSION == 4
    assert V4_TABLES <= table_names(db)
    with db.read() as conn:
        room_columns = {row["name"] for row in conn.execute("PRAGMA table_info(rooms)")}
        move_columns = {row["name"] for row in conn.execute("PRAGMA table_info(moves)")}
    assert {"mode", "computer_level"} <= room_columns
    assert {"captured_piece", "captured_square"} <= move_columns
    assert not (tmp_path / "fresh.sqlite3.old").exists()
    assert any("Created a fresh database" in record.getMessage() for record in caplog.records)


def test_version_4_file_is_kept_as_it_is(tmp_path):
    path = tmp_path / "keep.sqlite3"
    db = prepare_database(path)
    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('ABC123', 1, 1)")

    again = prepare_database(path)

    with again.read() as conn:
        assert [tuple(row) for row in conn.execute("SELECT code, mode FROM rooms")] == [("ABC123", "waiting")]
    assert not (tmp_path / "keep.sqlite3.old").exists()


@pytest.mark.parametrize("version", [2, 3])
def test_older_versions_are_moved_aside_replacing_an_earlier_old(tmp_path, caplog, version):
    path = tmp_path / "justchess.sqlite3"
    make_versioned_file(path, version)
    (tmp_path / "justchess.sqlite3.old").write_text("an even older leftover")

    with caplog.at_level(logging.WARNING, logger="justchess.db"):
        db = prepare_database(path)

    old = tmp_path / "justchess.sqlite3.old"
    assert read_schema_version(old) == version, "the earlier .old was replaced by this file"
    kept = sqlite3.connect(old)
    assert kept.execute("SELECT note FROM marker").fetchone()[0] == f"version {version} data"
    kept.close()
    assert read_schema_version(path) == 4
    assert V4_TABLES <= table_names(db)
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0
    moved = [record.getMessage() for record in caplog.records if "moved it to" in record.getMessage()]
    assert len(moved) == 1 and f"schema version {version}" in moved[0]


def test_old_format_file_is_moved_to_old_and_replaced(tmp_path, caplog):
    path = tmp_path / "justchess.sqlite3"
    legacy = sqlite3.connect(path)
    legacy.execute("CREATE TABLE games (code TEXT PRIMARY KEY, fen TEXT NOT NULL)")
    legacy.execute("INSERT INTO games VALUES ('OLD001', 'startpos')")
    legacy.commit()
    legacy.close()
    (tmp_path / "justchess.sqlite3.old").write_text("an even older leftover")

    with caplog.at_level(logging.WARNING, logger="justchess.db"):
        db = prepare_database(path)

    old = tmp_path / "justchess.sqlite3.old"
    kept = sqlite3.connect(old)
    assert kept.execute("SELECT code FROM games").fetchone()[0] == "OLD001"  # earlier .old replaced
    kept.close()
    assert read_schema_version(path) == 4
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM games").fetchone()[0] == 0
    assert any(str(path) in record.getMessage() for record in caplog.records)


def test_non_sqlite_file_is_treated_as_unmarked(tmp_path):
    path = tmp_path / "justchess.sqlite3"
    path.write_bytes(b"this is not a database at all, just some bytes" * 4)

    prepare_database(path)

    assert (tmp_path / "justchess.sqlite3.old").read_bytes().startswith(b"this is not")
    assert read_schema_version(path) == 4


def test_newer_version_refuses_to_start_and_is_not_moved(tmp_path):
    path = tmp_path / "justchess.sqlite3"
    make_versioned_file(path, 5)

    with pytest.raises(DatabaseStartupError, match="newer than this app"):
        prepare_database(path)

    assert read_schema_version(path) == 5, "the newer file is left where it is"
    assert not (tmp_path / "justchess.sqlite3.old").exists()


def test_failed_rename_stops_startup_and_creates_nothing(tmp_path, monkeypatch):
    path = tmp_path / "justchess.sqlite3"
    make_versioned_file(path, 3)

    def refuse(_src, _dst):
        raise PermissionError("read-only folder")

    monkeypatch.setattr(db_module.os, "replace", refuse)
    with pytest.raises(DatabaseStartupError, match="could not be moved"):
        prepare_database(path)

    assert read_schema_version(path) == 3, "the old file is untouched"
    assert not (tmp_path / "justchess.sqlite3.old").exists()


def _seed_room(conn, code="CHK001", mode="waiting", level=None):
    conn.execute("INSERT INTO rooms (code, created_at, last_activity_at, mode, computer_level) VALUES (?, 1, 1, ?, ?)",
                 (code, mode, level))


def test_check_constraints_on_modes_computer_seats_and_captures(db):
    with db.transaction() as conn:
        _seed_room(conn, "CMP001", "computer", "club")
        conn.execute("INSERT INTO seats (room_code, slot, token_hash, last_seen_at) VALUES ('CMP001', 'A', 'ha', 1)")
        conn.execute("INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) "
                     "VALUES ('CMP001', 'B', NULL, 1, 1)")
        conn.execute("INSERT INTO games (room_code, number, white_slot, fen) VALUES ('CMP001', 1, 'A', 'x')")
        conn.execute("INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece, captured_square) "
                     "VALUES (1, 1, 'e2e4', 'e4', 1, NULL, NULL)")
        _seed_room(conn, "FRD001")

    refused = [
        # a computer level without computer mode, and computer mode without a level
        "INSERT INTO rooms (code, created_at, last_activity_at, mode, computer_level) VALUES ('BAD001', 1, 1, 'online', 'club')",
        "INSERT INTO rooms (code, created_at, last_activity_at, mode, computer_level) VALUES ('BAD002', 1, 1, 'computer', NULL)",
        # a computer seat with a token, a human seat without one, a computer in seat A
        "INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) VALUES ('FRD001', 'B', 'hx', 1, 1)",
        "INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) VALUES ('FRD001', 'B', NULL, 1, 0)",
        "INSERT INTO seats (room_code, slot, token_hash, last_seen_at, is_computer) VALUES ('FRD001', 'A', NULL, 1, 1)",
        # capture info is both present or both absent, and well formed
        "INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece) VALUES (1, 2, 'e7e5', 'e5', 1, 'p')",
        "INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece, captured_square) "
        "VALUES (1, 2, 'e7e5', 'e5', 1, 'x', 'e4')",
        "INSERT INTO moves (game_id, ply, uci, san, played_at, captured_piece, captured_square) "
        "VALUES (1, 2, 'e7e5', 'e5', 1, 'p', 'i9')",
    ]
    for statement in refused:
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute(statement)


def test_one_pending_join_request_per_room_and_rows_go_with_the_room(db):
    with db.transaction() as conn:
        _seed_room(conn, "JRQ001")
        conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, created_at, expires_at) "
                     "VALUES ('JRQ001', 'r1', 1, 100)")
        # answered requests do not count against the one pending request
        conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, status, created_at, expires_at) "
                     "VALUES ('JRQ001', 'r0', 'declined', 1, 100)")

    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, created_at, expires_at) "
                         "VALUES ('JRQ001', 'r2', 2, 100)")

    with db.transaction() as conn:
        conn.execute("DELETE FROM rooms WHERE code = 'JRQ001'")
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM join_requests").fetchone()[0] == 0


def test_push_subscription_and_alert_record_constraints(db):
    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('PUSH01', 1, 1)")
        conn.execute("INSERT INTO push_subscriptions (room_code, slot, endpoint, p256dh, auth, created_at) "
                     "VALUES ('PUSH01', 'A', 'https://fcm.googleapis.com/fcm/send/x', 'k', 'a', 1)")
        conn.execute("INSERT INTO push_subscriptions (room_code, slot, endpoint, p256dh, auth, created_at) "
                     "VALUES ('PUSH01', 'B', 'https://fcm.googleapis.com/fcm/send/x', 'k', 'a', 1)")  # other seat: fine
        conn.execute("INSERT INTO alert_records (room_code, slot, event_key, created_at, updated_at) "
                     "VALUES ('PUSH01', 'B', 'move:1:1', 1, 1)")
        assert conn.execute("SELECT status FROM alert_records").fetchone()[0] == "claimed"

    duplicates = [
        "INSERT INTO push_subscriptions (room_code, slot, endpoint, p256dh, auth, created_at) "
        "VALUES ('PUSH01', 'A', 'https://fcm.googleapis.com/fcm/send/x', 'k2', 'a2', 2)",
        "INSERT INTO alert_records (room_code, slot, event_key, created_at, updated_at) VALUES ('PUSH01', 'B', 'move:1:1', 2, 2)",
        "INSERT INTO alert_records (room_code, slot, event_key, status, created_at, updated_at) "
        "VALUES ('PUSH01', 'A', 'joined', 'delivered', 2, 2)",  # not a known status
        "INSERT INTO push_subscriptions (room_code, slot, endpoint, p256dh, auth, created_at) "
        "VALUES ('NOROOM', 'A', 'https://fcm.googleapis.com/fcm/send/y', 'k', 'a', 1)",  # foreign key
    ]
    for statement in duplicates:
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute(statement)


def test_transaction_rolls_back_on_exception(db):
    with pytest.raises(RuntimeError, match="boom"):
        with db.transaction() as conn:
            conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('ROLL01', 1, 1)")
            raise RuntimeError("boom")

    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('KEEP01', 1, 1)")
    with db.read() as conn:
        codes = [row[0] for row in conn.execute("SELECT code FROM rooms")]
    assert codes == ["KEEP01"]


def test_unique_room_number_and_slot_constraints(db):
    with db.transaction() as conn:
        conn.execute("INSERT INTO rooms (code, created_at, last_activity_at) VALUES ('UNIQ01', 1, 1)")
        conn.execute(
            "INSERT INTO games (room_code, number, white_slot, fen) VALUES ('UNIQ01', 1, 'A', 'x')"
        )
        conn.execute(
            "INSERT INTO seats (room_code, slot, token_hash, last_seen_at) VALUES ('UNIQ01', 'A', 'h1', 1)"
        )

    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO games (room_code, number, white_slot, fen) VALUES ('UNIQ01', 1, 'B', 'y')"
            )
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO seats (room_code, slot, token_hash, last_seen_at) VALUES ('UNIQ01', 'A', 'h2', 1)"
            )
    with pytest.raises(sqlite3.IntegrityError):  # foreign keys are enforced
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO games (room_code, number, white_slot, fen) VALUES ('NOROOM', 1, 'A', 'z')"
            )


def test_unwritable_path_fails_startup_with_clear_error(tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory")
    path = blocker / "justchess.sqlite3"

    with pytest.raises(DatabaseStartupError, match="justchess.sqlite3"):
        prepare_database(path)


def test_db_path_comes_from_environment():
    assert str(resolve_db_path({"JUSTCHESS_DB": "/data/chess.db"})) == "/data/chess.db"
    assert str(resolve_db_path({})) == "justchess.sqlite3"
