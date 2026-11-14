"""SQLite connection, schema version 4 and the startup check (P2 U2 BR1.1, ADR-010).

The database path comes from ``JUSTCHESS_DB`` (default ``justchess.sqlite3`` in
the working directory). Every state change runs inside ``Database.transaction()``,
which opens its own connection and a ``BEGIN IMMEDIATE`` transaction, commits on
success and rolls back on any error.

At startup ``prepare_database()``:

- keeps a file that carries schema version 4;
- refuses to start on a file with a newer version (a newer app wrote it); the
  file is left where it is;
- moves any other file (versions 1-3, unmarked or not SQLite) aside to
  ``<name>.old`` (replacing an earlier ``.old``) and creates a fresh schema.
  No data is migrated (NFR7: no backward compatibility). A failed rename stops
  start-up with ``DatabaseStartupError``;
- creates the schema when there is no file.

Schema version 4 (entities.md) adds, over version 3:

- ``rooms.mode`` (waiting, pass_along, online, computer) and
  ``rooms.computer_level``, set if and only if the mode is computer;
- ``seats.is_computer``; ``seats.token_hash`` is null if and only if the seat
  is the computer's, which is always seat B;
- ``games.counted`` and the end reasons ``threefold_repetition``,
  ``fifty_moves`` and ``resigned``;
- ``moves.captured_piece`` (FEN letter) and ``moves.captured_square``, both
  present or both absent;
- ``join_requests``, with at most one pending request per room and rows
  deleted with their room.

New columns sit at the end of their tables so positional reads stay valid.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("justchess.db")

SCHEMA_VERSION = 4
DEFAULT_DB_NAME = "justchess.sqlite3"
BUSY_TIMEOUT_SECONDS = 5.0

# The whole version-4 schema in one script. No statement may contain a
# semicolon inside it (``_statements`` splits on them).
# Push subscriptions and alert records keep their version-3 shape. Housekeeping
# deletes them by room first; ON DELETE CASCADE is the safety net so a room
# delete is never blocked by these rows (or by join requests).
SCHEMA = """
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE rooms (
    code                 TEXT PRIMARY KEY CHECK (length(code) = 6),
    created_at           REAL NOT NULL,
    last_activity_at     REAL NOT NULL,
    wins_a               INTEGER NOT NULL DEFAULT 0 CHECK (wins_a >= 0),
    wins_b               INTEGER NOT NULL DEFAULT 0 CHECK (wins_b >= 0),
    draws                INTEGER NOT NULL DEFAULT 0 CHECK (draws >= 0),
    rematch_requested_by TEXT CHECK (rematch_requested_by IN ('A', 'B')),
    rematch_requested_at REAL,
    mode                 TEXT NOT NULL DEFAULT 'waiting'
                         CHECK (mode IN ('waiting', 'pass_along', 'online', 'computer')),
    computer_level       TEXT CHECK (computer_level IN ('beginner', 'casual', 'club', 'strong', 'maximum')),
    CHECK ((mode = 'computer') = (computer_level IS NOT NULL))
);
CREATE INDEX rooms_last_activity ON rooms (last_activity_at);

CREATE TABLE seats (
    seat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code           TEXT NOT NULL REFERENCES rooms (code),
    slot                TEXT NOT NULL CHECK (slot IN ('A', 'B')),
    token_hash          TEXT UNIQUE,
    continue_token_hash TEXT UNIQUE,
    continue_expires_at REAL,
    last_seen_at        REAL NOT NULL,
    is_computer         INTEGER NOT NULL DEFAULT 0 CHECK (is_computer IN (0, 1)),
    UNIQUE (room_code, slot),
    CHECK ((is_computer = 1) = (token_hash IS NULL)),
    CHECK (is_computer = 0 OR slot = 'B')
);

CREATE TABLE games (
    game_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code  TEXT NOT NULL REFERENCES rooms (code),
    number     INTEGER NOT NULL CHECK (number >= 1),
    white_slot TEXT NOT NULL CHECK (white_slot IN ('A', 'B')),
    fen        TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    status     TEXT NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'playing', 'finished')),
    end_reason TEXT CHECK (end_reason IN (
        'checkmate', 'stalemate', 'insufficient_material', 'fivefold_repetition',
        'seventyfive_moves', 'threefold_claimed', 'fifty_moves_claimed',
        'threefold_repetition', 'fifty_moves', 'abandoned', 'resigned')),
    result     TEXT CHECK (result IN ('1-0', '0-1', '1/2-1/2')),
    started_at REAL,
    ended_at   REAL,
    counted    INTEGER NOT NULL DEFAULT 1 CHECK (counted IN (0, 1)),
    UNIQUE (room_code, number)
);

CREATE TABLE moves (
    game_id         INTEGER NOT NULL REFERENCES games (game_id),
    ply             INTEGER NOT NULL CHECK (ply >= 1),
    uci             TEXT NOT NULL,
    san             TEXT NOT NULL,
    played_at       REAL NOT NULL,
    captured_piece  TEXT CHECK (captured_piece IS NULL
                                OR (length(captured_piece) = 1 AND instr('pnbrqPNBRQ', captured_piece) > 0)),
    captured_square TEXT CHECK (captured_square IS NULL
                                OR (length(captured_square) = 2 AND captured_square GLOB '[a-h][1-8]')),
    PRIMARY KEY (game_id, ply),
    CHECK ((captured_piece IS NULL) = (captured_square IS NULL))
);

CREATE TABLE join_requests (
    request_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code            TEXT NOT NULL REFERENCES rooms (code) ON DELETE CASCADE,
    requester_token_hash TEXT NOT NULL UNIQUE,
    status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'accepted', 'declined', 'lapsed')),
    created_at           REAL NOT NULL,
    expires_at           REAL NOT NULL,
    answered_at          REAL
);
CREATE UNIQUE INDEX join_requests_one_pending ON join_requests (room_code) WHERE status = 'pending';

CREATE TABLE push_subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code  TEXT NOT NULL REFERENCES rooms (code) ON DELETE CASCADE,
    slot       TEXT NOT NULL CHECK (slot IN ('A', 'B')),
    endpoint   TEXT NOT NULL CHECK (length(endpoint) BETWEEN 1 AND 1024),
    p256dh     TEXT NOT NULL CHECK (length(p256dh) BETWEEN 1 AND 200),
    auth       TEXT NOT NULL CHECK (length(auth) BETWEEN 1 AND 64),
    created_at REAL NOT NULL,
    UNIQUE (room_code, slot, endpoint)
);

CREATE TABLE alert_records (
    room_code  TEXT NOT NULL REFERENCES rooms (code) ON DELETE CASCADE,
    slot       TEXT NOT NULL CHECK (slot IN ('A', 'B')),
    event_key  TEXT NOT NULL CHECK (length(event_key) BETWEEN 1 AND 64),
    status     TEXT NOT NULL DEFAULT 'claimed' CHECK (status IN ('claimed', 'sent', 'skipped', 'failed')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (room_code, slot, event_key)
);
"""


class DatabaseStartupError(RuntimeError):
    """The database could not be opened, replaced or created at startup."""


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the database path from ``JUSTCHESS_DB``, else the default file name."""
    env = os.environ if env is None else env
    return Path(env.get("JUSTCHESS_DB") or DEFAULT_DB_NAME)


def old_path_for(path: Path) -> Path:
    """Return the ``.old`` path an outdated database is moved to."""
    return path.with_name(path.name + ".old")


def open_connection(path: Path) -> sqlite3.Connection:
    """Open a connection in manual transaction mode with foreign keys on."""
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run the block in a ``BEGIN IMMEDIATE`` transaction; roll back on any error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


class Database:
    """Opens short-lived connections to one SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        """Open a new connection; the caller closes it."""
        return open_connection(self.path)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Open a connection and run the block in one ``BEGIN IMMEDIATE`` transaction."""
        conn = self.connect()
        try:
            with transaction(conn):
                yield conn
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """Open a connection for reads only."""
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()


def read_schema_version(path: Path) -> int | None:
    """Return the schema version stored in the file, or None when unmarked or unreadable."""
    try:
        conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_SECONDS)
    except sqlite3.Error as exc:
        raise DatabaseStartupError(f"Cannot open the database file {path}: {exc}") from exc
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None
        raise DatabaseStartupError(f"Cannot read the database file {path}: {exc}") from exc
    except sqlite3.DatabaseError:
        # Not an SQLite file at all: treat it as unmarked so it is moved aside.
        return None
    finally:
        conn.close()
    try:
        return None if row is None else int(row[0])
    except (TypeError, ValueError):
        return None


def _move_aside(path: Path) -> Path:
    """Rename ``path`` to its ``.old`` name (replacing an earlier one); a failure stops start-up."""
    old = old_path_for(path)
    try:
        os.replace(path, old)
    except OSError as exc:
        raise DatabaseStartupError(
            f"The database {path} has an old format and could not be moved to {old}: {exc}"
        ) from exc
    return old


def _create_schema(path: Path) -> None:
    try:
        conn = open_connection(path)
        try:
            with transaction(conn):
                for statement in _statements(SCHEMA):
                    conn.execute(statement)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatabaseStartupError(f"Cannot create the database at {path}: {exc}") from exc


def _statements(script: str) -> list[str]:
    """Split the schema script into single statements (no semicolons inside them)."""
    return [part.strip() for part in script.split(";") if part.strip()]


def prepare_database(path: Path) -> Database:
    """Apply BR1.1 to ``path`` and return a ready ``Database``.

    Version 4 is kept; a newer version refuses to start; anything else is moved
    to ``<name>.old`` and a fresh version-4 schema is created. Raises
    ``DatabaseStartupError`` with the file name when the file cannot be opened,
    moved aside or created, so startup fails with a clear message.
    """
    path = Path(path)
    if path.exists():
        found = read_schema_version(path)
        if found == SCHEMA_VERSION:
            logger.info("Using the database %s (schema version %s)", path, SCHEMA_VERSION)
            return Database(path)
        if found is not None and found > SCHEMA_VERSION:
            raise DatabaseStartupError(
                f"The database {path} has schema version {found}, newer than this app ({SCHEMA_VERSION}); "
                "it was left unchanged"
            )
        old = _move_aside(path)
        _create_schema(path)
        logger.warning(
            "Database %s had schema version %s (expected %s); moved it to %s and created a fresh one",
            path, found if found is not None else "none", SCHEMA_VERSION, old,
        )
        return Database(path)
    _create_schema(path)
    logger.info("Created a fresh database at %s (schema version %s)", path, SCHEMA_VERSION)
    return Database(path)
